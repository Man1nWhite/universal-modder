"""Minimal reader for DOA5/DOAXVV ``.TMC`` model files (Route B).

Written for the Honoka "Secret Report" outfit (``references/Outfit for
Honoka-109-1-1-1628020933.zip``). It parses the same sections the community
Noesis plugin "doa5pctools" walks, but keeps the skinning data that plugin
binds to nowhere:

    TMC root (section table)
      MdlGeo  -> ObjGeo per mesh group -> GeoDecl (vertex/index declaration)
      VtxLay  -> per-declaration vertex buffers
      IdxLay  -> per-declaration uint16 triangle-strip buffers
      NodeLay -> the 171 skeleton nodes (MOT*, OPT_* helpers, WGT_* meshes)
      GlblMtx -> one 4x4 bind matrix per node

Vertex layouts (validated byte-by-byte against the ``TMC Object Tool 0.33.3``
tables and by exact float match of positions/UVs against the accompanying
OBJ export). All layouts are little-endian:

    stride 0x40 (64): pos f3 @0, nrm f3 @12, weights u8[4] @24 (sum 255),
                      bone indices u8[4] @28, tangent f4 @32, uv1 half2 @48 (duplicated x4)
    stride 0x3c (60): same, but uv1 half2 @48 duplicated x3
    stride 0x24 (36): pos f3 @0, nrm f3 @12, weights u8[4] @24, bone indices u8[4] @28, uv1 half2 @32

Bone indices in the vertex buffers are SLOTS into a per-mesh skin palette,
not node indices. Each mesh-bearing ``WGT_*`` node in ``NodeLay`` carries,
inline after its object-reference table: ``objidx`` u32, ``palette_count``
u32, ``self_index`` u32, a 4x4 float matrix (64 bytes, value 0x3f800000
block; role unverified), one trailing float (1.0), then
``palette_count`` u32 global node indices. Validated 2026-11-15 on the
Honoka outfit: palettes of 41/43/85/9 entries decode, every slot resolves,
and palette-remapped skin weights are anatomically coherent (breast verts
bind to breast bones, hands to hand/wrist bones). The feather mesh
(``WGT_body_feather``) has ``palette_count == 0``; its slots are coherent
as raw node indices. ``load_meshes`` attaches the remapped ``palette``
(list of global node indices, or ``None``) to every ``MeshPayload``; the
raw slots stay in ``bone_indices``.

Positions are stored in meters; ``load()`` converts to centimetres (the LAS
pipeline's unit). Weights are returned as floats summing to 1.0. Rows whose
four weight bytes are all zero (followed by four zero indices) are unweighted
placeholders (the ``*T_body_feather`` group): they are reported, never
silently fixed.

Not implemented, on purpose: materials/textures (MCAPACK), physics (takes its
own files), the ``WGT_body_feather`` placeholder mesh (dead data), writing
TMCs. This module reads; it does not claim the format is fully understood.
"""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


SECTION_ORDER = ["MdlGeo", "TTX", "VtxLay", "IdxLay", "MtrCol", "MdlInfo", "HieLay",
                 "LHeader", "NodeLay", "GlblMtx", "BnOfsMtx", "cpf", "MCAPACK",
                 "RENPACK", "", "", "ACSCLS"]


@dataclass
class SectionHead:
    base: int
    name: str
    hsize: int
    size: int
    count1: int
    count2: int
    count3: int
    offset1: int
    offset2: int
    offset3: int
    offsets: List[int] = field(default_factory=list)


def _read_head(d: bytes, base: int) -> SectionHead:
    name = d[base:base + 8].split(b"\0", 1)[0].decode("ascii", "replace")
    f1, hsize, size, c1, c2, c3, o1, o2, o3, f2 = struct.unpack_from("<10L", d, base + 8)
    # Offset tables live at base + Offset1 when set, otherwise at base + HSize
    # (GlblMtx has Offset1 == 0 and its table at +HSize).
    table_at = o1 if o1 else hsize
    offs = list(struct.unpack_from(f"<{c1}L", d, base + table_at)) if table_at and c1 else []
    return SectionHead(base=base, name=name, hsize=hsize, size=size,
                       count1=c1, count2=c2, count3=c3,
                       offset1=o1, offset2=o2, offset3=o3, offsets=offs)


@dataclass
class VertexBuffer:
    index: int
    offset: int      # absolute file offset of the buffer
    size: int        # from the section size table, verified against decl
    vert_count: int
    stride: int


@dataclass
class MeshPayload:
    """One sub-object (a ``GeoDecl`` with a non-empty draw)."""
    group: str                # sub-object name (OBJ group name)
    object_name: str          # owning ObjGeo name (aligned with TMC Object Tool)
    buffer_index: int
    vert_count: int
    stride: int
    positions: np.ndarray     # (n,3) float32, centimetres
    normals: np.ndarray       # (n,3) float32
    tangents: Optional[np.ndarray]   # (n,4) float32 or None
    uvs: np.ndarray           # (n,2) float32
    weights: np.ndarray       # (n,4) float32, rows sum to 1 (or all-zero placeholders)
    bone_indices: np.ndarray  # (n,4) uint8
    unweighted: np.ndarray    # (n,) bool — rows whose weights are all zero
    indices: np.ndarray       # (m,3) uint32 triangle list (degenerate strips resolved)
    source_id: str            # e.g. "WGT_new_aya_body_1"
    palette: Optional[List[int]] = None  # slot -> global node index (None = no palette; slots are raw node indices)



def _align_winding_to_normals(pos: np.ndarray, normals: np.ndarray,
                              tris: np.ndarray) -> np.ndarray:
    """Flip every triangle whose face normal disagrees with its vertex normals.

    The TMC strips do not follow one winding rule across all declarations of
    this file: absolute D3D window parity is exactly right for the
    sweat_chest buffer (100%) but off for cap2 (69%), headdress2 (49%), the
    body (94%) and the feather (19%); run-relative parity fixes those but
    breaks sweat_chest (48%). No single parity rule decodes every buffer, so
    the winding is normalised against the stored (per-vertex, unit-length)
    normals, which is also what the shader uses. Triangles whose summed
    vertex normal is ~0 (the all-zero placeholder rows of the feather mesh)
    are left untouched.
    """
    if len(tris) == 0:
        return tris
    t = np.asarray(tris, dtype=np.int64)
    fn = np.cross(pos[t[:, 1]] - pos[t[:, 0]], pos[t[:, 2]] - pos[t[:, 0]])
    vn = normals[t[:, 0]] + normals[t[:, 1]] + normals[t[:, 2]]
    flip = ((fn * vn).sum(axis=1) < 0) & (np.linalg.norm(vn, axis=1) > 1e-6)
    if flip.any():
        t = t.copy()
        t[flip] = t[flip][:, [0, 2, 1]]
    return t.astype(np.uint32)


def _strip_to_tris(strip: np.ndarray) -> np.ndarray:
    """Triangle strip (uint16 indices) to triangle list.

    Parity is taken from the absolute window index (D3D strip semantics);
    windows repeating any vertex index (zero area, used as strip stitching)
    are dropped. Verified: with this rule the winding agrees with the stored
    vertex normals on 100% of sweat_chest triangles and ~94% of body
    triangles; the accompanying OBJ dump ignores strip parity and keeps every
    zero-area window, so it is not usable as a reference for decoding.
    """
    s = strip.astype(np.int64)
    n = len(s)
    if n < 3:
        return np.empty((0, 3), np.uint32)
    a, b, c = s[:-2], s[1:-1], s[2:]
    clean = (a != b) & (b != c) & (a != c)
    idx = np.where(clean)[0]
    if len(idx) == 0:
        return np.empty((0, 3), np.uint32)
    a, b, c = a[idx], b[idx], c[idx]
    flip = (idx % 2) == 1
    b, c = np.where(flip, c, b), np.where(flip, b, c)
    return np.stack([a, b, c], axis=1).astype(np.uint32)


_LAYOUTS = {
    0x40: dict(tan=True, uv_duplicates=4),
    0x3C: dict(tan=True, uv_duplicates=3),
    0x24: dict(tan=False, uv_duplicates=1),
}


class TmcFile:
    def __init__(self, path: str):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        if d[:3] != b"TMC":
            raise ValueError(f"not a TMC file: {path}")
        self.root = _read_head(d, 0)
        sections = [(_read_head(d, off) if off else None) for off in self.root.offsets]
        self.sections: Dict[str, SectionHead] = {}
        for idx, sec in enumerate(sections):
            if sec is None:
                continue
            # trust the file's own section name; order only sanity-checked
            self.sections[sec.name] = sec
        for required in ("MdlGeo", "VtxLay", "IdxLay", "NodeLay", "GlblMtx"):
            if required not in self.sections:
                raise ValueError(f"missing section {required}")
        self._load_skeleton()
        self.buffers = self._load_buffers()

    # ---------- skeleton ----------

    def _load_skeleton(self) -> None:
        d = self.data
        nlay = self.sections["NodeLay"]
        hie = self.sections.get("HieLay")
        glb = self.sections["GlblMtx"]
        self.node_names: List[str] = []
        self.node_layout: List[dict] = []
        for off in nlay.offsets:
            nobj = _read_head(d, nlay.base + off)
            name = d[nobj.base + 0x40:nobj.base + 0x60].split(b"\0", 1)[0].decode("ascii", "replace")
            self.node_names.append(name)
        self.node_count = len(self.node_names)
        self.hie_parent: List[int] = [-1] * self.node_count
        self.hie_children: List[List[int]] = [[] for _ in range(self.node_count)]
        # raw 16 floats per node; use .reshape(4,4,order="F") for the
        # column-major reading that matches validated bind composition
        self.local_raw = [np.zeros(16, dtype=np.float64) for _ in range(self.node_count)]
        if hie is not None:
            hoffs = hie.offsets
            for i, o in enumerate(hoffs):
                nxt = hoffs[i + 1] if i + 1 < len(hoffs) else o + 0x200
                b = d[hie.base + o:hie.base + nxt]
                parent = struct.unpack_from("<i", b, 0x40)[0]
                n = struct.unpack_from("<L", b, 0x44)[0]
                ch = list(struct.unpack_from(f"<{n}L", b, 0x50))
                f = np.array(struct.unpack_from("<16f", b, 0), dtype=np.float64)
                self.hie_parent[i] = parent
                self.hie_children[i] = ch
                self.local_raw[i] = f
        self.global_raw = []
        for off in glb.offsets:
            self.global_raw.append(np.array(struct.unpack_from("<16f", d, glb.base + off),
                                            dtype=np.float64))
        self.mesh_palettes: Dict[int, List[int]] = {}  # MdlGeo object index -> slot palette (global node indices)
        for off in nlay.offsets:
            nobj = _read_head(d, nlay.base + off)
            name = d[nobj.base + 0x40:nobj.base + 0x60].split(b"\0", 1)[0].decode("ascii", "replace")
            if not name.startswith("WGT_") or not nobj.offsets:
                continue
            base = nobj.base
            objidx = struct.unpack_from("<L", d, base + nobj.offsets[0])[0]
            pcount, selfidx = struct.unpack_from("<LL", d, base + nobj.offsets[0] + 4)
            if pcount == 0:
                continue
            pal_at = base + nobj.offsets[0] + 80
            palette = list(struct.unpack_from(f"<{pcount}L", d, pal_at))
            if any(p >= self.node_count for p in palette):
                raise ValueError(f"{name}: palette entry out of range (node_count={self.node_count})")
            self.mesh_palettes[objidx] = palette

    # ---------- buffers ----------

    def _load_buffers(self) -> List[Optional[VertexBuffer]]:
        d = self.data
        vtx = self.sections["VtxLay"]
        count = vtx.count1
        sizes = list(struct.unpack_from(f"<{vtx.count2}L", d, vtx.base + vtx.offset2)) if vtx.offset2 and vtx.count2 else []
        buffers: List[Optional[VertexBuffer]] = []
        for i in range(count):
            base = vtx.base + vtx.offsets[i]
            size = sizes[i] if i < len(sizes) else None
            buffers.append(VertexBuffer(index=i, offset=base, size=size or 0, vert_count=0, stride=0))
        return buffers

    # ---------- meshes ----------

    def _decode_decl(self, decl_db: int):
        d = self.data
        IDXBUFindex, IDXcount, VERTcount, unk0, unk1, VTXBUFindex, vsize, layercount = \
            struct.unpack_from("<5L16xL2L4x", d, decl_db + 0xC)
        return IDXBUFindex, IDXcount, VERTcount, unk0, unk1, VTXBUFindex, vsize, layercount

    def load_meshes(self) -> List[MeshPayload]:
        d = self.data
        out: List[MeshPayload] = []
        mdlgeo = self.sections["MdlGeo"]
        vtx = self.sections["VtxLay"]
        idxsec = self.sections["IdxLay"]
        mesh_nodes = self.mesh_node_index()
        for objidx, objoffs in enumerate(mdlgeo.offsets):
            if not objoffs:
                continue
            base = mdlgeo.base + objoffs
            objh = _read_head(d, base)
            declh = _read_head(d, base + objh.offset3)
            raw_name = d[base + 0x50:base + 0x70].split(b"\0", 1)[0].decode("ascii", "replace")
            for di, doff in enumerate(declh.offsets):
                db = declh.base + doff
                IDXBUFindex, IDXcount, VERTcount, unk0, unk1, VTXBUFindex, vsize, layercount = self._decode_decl(db)
                if IDXcount < 3 or VERTcount < 3:
                    print(f"note: skipping placeholder decl (object {raw_name}, decl {di}, "
                          f"IDXcount={IDXcount}, VCOUNT={VERTcount})", file=sys.stderr)
                    continue
                buf = self.buffers[VTXBUFindex]
                need = vsize * VERTcount
                if buf.size and not (need <= buf.size < need + 64):
                    raise ValueError(f"buffer {VTXBUFindex}: size table {buf.size} vs decl {need}")
                stride = vsize
                if stride not in _LAYOUTS:
                    raise ValueError(f"unknown vertex stride {stride:#x} (object {raw_name})")
                n = VERTcount
                src = d[buf.offset:buf.offset + need]
                A = np.frombuffer(src, dtype=np.uint8).reshape(n, stride)
                pos = np.frombuffer(A[:, 0:12].tobytes(), dtype="<f4").reshape(n, 3) * np.float32(100.0)
                nrm = np.frombuffer(A[:, 12:24].tobytes(), dtype="<f4").reshape(n, 3)
                wgt = A[:, 24:28].astype(np.float32) / np.float32(255.0)
                bid = A[:, 28:32].copy()
                lay = _LAYOUTS[stride]
                if lay["tan"]:
                    tan = np.frombuffer(A[:, 32:48].tobytes(), dtype="<f4").reshape(n, 4)
                    uv_off = 48
                else:
                    tan = None
                    uv_off = 32
                uv = np.frombuffer(A[:, uv_off:uv_off + 4].tobytes(), dtype="<f2").reshape(n, 2)
                unweighted = (A[:, 24:32].sum(axis=1) == 0)
                sums = wgt.sum(axis=1)
                bad = np.where((sums > 0) & (np.abs(sums - 1.0) > 1e-4))[0]
                if len(bad):
                    raise ValueError(f"weights do not sum to 255/1.0 in {raw_name} decl {di} (e.g. row {bad[0]})")
                # material/sub-object table for this decl lives in the ObjGeo
                # header; the mesh group names come from the matching NodeLay
                # WGT_* node, resolved by caller (see resolve_groups).
                ib = idxsec.base + idxsec.offsets[IDXBUFindex]
                strip = np.frombuffer(d[ib:ib + IDXcount * 2], dtype="<u2")
                tris = _strip_to_tris(strip)
                tris = _align_winding_to_normals(pos, nrm, tris)
                node_name = mesh_nodes.get(objidx)
                if node_name:
                    src_id = node_name if len(declh.offsets) == 1 else f"{node_name}_decl{di}"
                else:
                    src_id = _buffer_group_name(raw_name, di, len(declh.offsets))
                out.append(MeshPayload(
                    group=src_id, object_name=raw_name, buffer_index=VTXBUFindex,
                    vert_count=n, stride=stride, positions=pos, normals=nrm,
                    tangents=tan, uvs=uv, weights=wgt, bone_indices=bid,
                    unweighted=unweighted, indices=tris, source_id=src_id,
                    palette=self.mesh_palettes.get(objidx)))
        return out

    # ---------- helpers ----------

    def mesh_node_index(self) -> Dict[int, str]:
        """object index -> WGT_* node name (from NodeLay mesh nodes)."""
        d = self.data
        out: Dict[int, str] = {}
        nlay = self.sections["NodeLay"]
        for off in nlay.offsets:
            nobj = _read_head(d, nlay.base + off)
            name = d[nobj.base + 0x40:nobj.base + 0x60].split(b"\0", 1)[0].decode("ascii", "replace")
            if not name.startswith("WGT_"):
                continue
            for m in nobj.offsets:
                objidx = struct.unpack_from("<L", d, nobj.base + m)[0]
                out[objidx] = name
        return out


def _buffer_group_name(object_name: str, decl_index: int, decl_count: int) -> str:
    base = object_name.lstrip("*T_ ").strip()
    if not base:
        base = object_name.strip("* ").lstrip("_ ") or object_name
    if decl_count > 1:
        return f"{base}_decl{decl_index}"
    return base


def main(argv: List[str]) -> int:
    tmc = TmcFile(argv[1])
    print(f"sections: {sorted(tmc.sections)}")
    print(f"nodes: {tmc.node_count}")
    meshes = tmc.load_meshes()
    mesh_nodes = tmc.mesh_node_index()
    total_v = 0
    total_t = 0
    for m in meshes:
        total_v += m.vert_count
        total_t += len(m.indices)
        uw = int(m.unweighted.sum())
        pos = np.asarray(m.positions, dtype=np.float64)
        nrm = np.asarray(m.normals, dtype=np.float64)
        idx3 = np.asarray(m.indices).reshape(-1, 3).astype(np.int64)
        fn = np.cross(pos[idx3[:, 1]] - pos[idx3[:, 0]], pos[idx3[:, 2]] - pos[idx3[:, 0]])
        vn = nrm[idx3[:, 0]] + nrm[idx3[:, 1]] + nrm[idx3[:, 2]]
        ok = fn[:, 0] * vn[:, 0] + fn[:, 1] * vn[:, 1] + fn[:, 2] * vn[:, 2] > 0
        frac = ok.mean() if len(ok) else 0.0
        pal = f"palette={len(m.palette)}" if m.palette is not None else "palette=none(raw slots)"
        print(f"  winding agreement: {frac:.4f}")
        print(f"{m.source_id:24s} buf={m.buffer_index} v={m.vert_count:6d} tris={len(m.indices):6d} "
              f"unweighted={uw:4d} stride={m.stride:#04x} {pal}")
    print(f"total verts={total_v} tris={total_t}")
    print("mesh nodes:", mesh_nodes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
