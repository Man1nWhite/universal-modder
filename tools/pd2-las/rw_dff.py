"""RenderWare DFF/TXD reader for the GTA-format ped sources (stdlib + numpy).

Written for ``references/characters/1581859199_135363.rar`` (``Random4.dff`` / ``Random4.txd``):
a GTA V-style ped exported on a GTA SA-era RW 3.6 stream (one Clump, one skinned
Geometry with per-material triangle groups, RpSkin weights, a TexDictionary of
DXT rasters). The head-replacement builder uses it to take the head, hair and
teeth groups out of the mesh and their textures out of the TXD.

The chunk grammar is the RW stream: every chunk is ``u32 type, u32 size, u32
version`` followed by ``size`` payload bytes (which may themselves be chunks).
What the fields inside Geometry / Skin / BinMesh / TextureNative mean is version
and platform specific; this module reads only the layouts this source uses and
``--probe`` verifies every parser against the chunk extents.

    python3 tools/pd2-las/rw_dff.py probe  references/characters/1581859199_135363.rar
    python3 tools/pd2-las/rw_dff.py dump   build/hoxton-source/out
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Chunk type ids (rwcore.h)
ID_STRUCT = 0x01
ID_STRING = 0x02
ID_EXTENSION = 0x03
ID_TEXTURE = 0x06
ID_MATERIAL = 0x07
ID_MATERIALLIST = 0x08
ID_FRAMELIST = 0x0E
ID_GEOMETRY = 0x0F
ID_CLUMP = 0x10
ID_ATOMIC = 0x14
ID_TEXTURENATIVE = 0x15
ID_TEXDICTIONARY = 0x16
ID_GEOMETRYLIST = 0x1A
ID_BINMESH = 0x50E
ID_SKIN = 0x116

CHUNK_NAMES = {
    ID_STRUCT: "Struct", ID_STRING: "String", ID_EXTENSION: "Extension",
    ID_TEXTURE: "Texture", ID_MATERIAL: "Material", ID_MATERIALLIST: "MaterialList",
    ID_FRAMELIST: "FrameList", ID_GEOMETRY: "Geometry", ID_CLUMP: "Clump",
    ID_ATOMIC: "Atomic", ID_TEXTURENATIVE: "TextureNative",
    ID_TEXDICTIONARY: "TexDictionary", ID_GEOMETRYLIST: "GeometryList",
    ID_BINMESH: "BinMeshPLG", ID_SKIN: "SkinPLG",
}


@dataclass
class Chunk:
    type: int
    size: int
    version: int
    body: memoryview  # payload

    def sub(self) -> list["Chunk"]:
        return list(chunks(self.body))


def chunks(buf: memoryview) -> list[Chunk]:
    """Every top-level chunk inside ``buf``; raises when the walk would overrun."""
    out: list[Chunk] = []
    off = 0
    n = len(buf)
    while off + 12 <= n:
        ctype, size, ver = struct.unpack_from("<III", buf, off)
        if off + 12 + size > n:
            raise ValueError(f"chunk {ctype:#x} at {off:#x} overruns its parent ({size} bytes)")
        out.append(Chunk(ctype, size, ver, buf[off + 12: off + 12 + size]))
        off += 12 + size
    if off != n:
        raise ValueError(f"{n - off} trailing bytes after last chunk")
    return out


FRAME_NAME_PLUGIN = 0x0253F2FE


def frame_names(frame_c: Chunk, count: int) -> list[str]:
    """The name in each frame's extension, in frame order; [] when the count disagrees.

    An extension that does not parse is an error rather than an empty name: the source
    writes the skeleton's frame names there, and a silently unnamed rig turns every
    bone lookup into a miss two hundred lines later.
    """
    names: list[str] = []
    for index, ext in enumerate(c for c in frame_c.sub() if c.type == ID_EXTENSION):
        name = ""
        try:
            for sc in chunks(ext.body):
                if sc.type == FRAME_NAME_PLUGIN:
                    name = bytes(sc.body).decode("latin-1")
        except ValueError as exc:
            raise ValueError(f"frame {index}: unreadable frame-name extension: {exc}") from None
        names.append(name)
    return names if len(names) == count else []


def one(buf: memoryview, ctype: int) -> Chunk:
    found = [c for c in chunks(buf) if c.type == ctype]
    if len(found) != 1:
        raise ValueError(f"expected exactly one {CHUNK_NAMES.get(ctype, hex(ctype))} chunk, got {len(found)}")
    return found[0]


@dataclass
class Frame:
    name: str
    parent: int


@dataclass
class Material:
    name: str | None
    texture: str | None
    textured: bool


@dataclass
class DffModel:
    frames: list[Frame]
    positions: np.ndarray  # (V, 3) float32
    normals: np.ndarray  # (V, 3) float32
    uvs: np.ndarray  # (V, 2) float32, one set
    triangles: np.ndarray  # (T, 4) uint16: v0, v1, v2, pad
    materials: list[Material]
    #: per BinMesh group: (material index, (T, 3) vertex-index triples)
    groups: list[tuple[int, np.ndarray]]
    bone_indices: np.ndarray | None  # (V, 4) uint8
    bone_weights: np.ndarray | None  # (V, 4) float32
    bone_names: list[str] = field(default_factory=list)


@dataclass
class Raster:
    name: str
    width: int
    height: int
    rgba: np.ndarray  # (H, W, 4) uint8 top-down


def _cstr(buf: memoryview, off: int, limit: int = 64) -> str:
    end = bytes(buf[off: off + limit]).split(b"\x00")[0]
    return end.decode("latin-1")


def read_dff(data: bytes) -> DffModel:
    root = chunks(memoryview(data))
    clumps = [c for c in root if c.type == ID_CLUMP]
    if len(clumps) != 1:
        raise ValueError(f"expected one Clump at the top of a DFF, got {[hex(c.type) for c in root]}")
    clump = clumps[0]
    if len(root) > 1:
        # Some exporter streams pad the tail (this source ends in an 8-byte 0xf21e
        # chunk); the Clump is self-contained, so the trailer is ignored.
        pass

    struct_c = one(clump.body, ID_STRUCT)
    num_atomics, num_lights, num_cameras = struct.unpack_from("<III", struct_c.body)
    del num_lights, num_cameras, num_atomics

    frame_c = one(clump.body, ID_FRAMELIST)
    fstruct = one(frame_c.body, ID_STRUCT)
    (num_frames,) = struct.unpack_from("<I", fstruct.body)
    frames: list[Frame] = []
    for i in range(num_frames):
        base = 4 + i * 56
        parent = struct.unpack_from("<i", fstruct.body, base + 48)[0]
        frames.append(Frame(name="", parent=parent))
    # Frame names ride inside the FrameList chunk (this exporter: one big
    # String extension, 33 cstrings in frame order), or in the Clump's trailing
    # extensions; try both.
    # Frame names ride in each frame's extension as a GTA frame-name plugin
    # (this exporter: chunk 0x0253f2fe, body = raw name like " Pelvis").
    names = frame_names(frame_c, num_frames)
    if names:
        frames = [Frame(name=n, parent=f.parent) for n, f in zip(names, frames)]

    glist = one(clump.body, ID_GEOMETRYLIST)
    gstruct = one(glist.body, ID_STRUCT)
    (num_geoms,) = struct.unpack_from("<I", gstruct.body)
    geom_chunks = [c for c in glist.sub() if c.type == ID_GEOMETRY]
    if num_geoms != 1 or len(geom_chunks) != 1:
        raise ValueError(f"expected a single geometry, got {num_geoms} declared / {len(geom_chunks)} chunks")
    geom = geom_chunks[0]

    gstruct = one(geom.body, ID_STRUCT)
    flags, num_tris, num_verts, num_morphs = struct.unpack_from("<IIII", gstruct.body)
    if num_morphs != 1:
        raise ValueError(f"expected one morph target, got {num_morphs}")

    prelit = 4 if (flags & 0x08) else 0
    body = gstruct.body

    # The UV-set count is not carried reliably by the flags (this dialect sets
    # 0x10 and still stores one set), so solve the layout against the chunk
    # extent: prelit/uv counts, then morph sphere + two u32 presence flags,
    # then the arrays those flags gate.
    solved = None
    for uvsets in (1, 2, 0):
        off = 16 + num_verts * prelit
        uv_off = off
        off += num_verts * 8 * uvsets
        tri_off = off
        off += num_tris * 8
        if off + 24 > len(body):
            continue
        has_pos, has_nrm = struct.unpack_from("<II", body, off + 16)
        if (has_pos, has_nrm) not in ((1, 1), (1, 0), (0, 1), (0, 0)):
            continue
        pos_off = off + 24
        nrm_off = pos_off + num_verts * 12 * has_pos
        end = nrm_off + num_verts * 12 * has_nrm
        if end == len(body):
            solved = (uvsets, uv_off, tri_off, pos_off, nrm_off, has_pos, has_nrm)
            break
    if solved is None:
        raise ValueError(
            f"Geometry struct layout mismatch: flags={flags:#x} tris={num_tris} "
            f"verts={num_verts} prelit={prelit} struct={len(body)} bytes")
    uvsets, uv_off, tri_off, pos_off, nrm_off, has_pos, has_nrm = solved

    positions = np.frombuffer(body, dtype="<f4", count=num_verts * 3, offset=pos_off).reshape(-1, 3).copy()
    normals = (np.frombuffer(body, dtype="<f4", count=num_verts * 3, offset=nrm_off).reshape(-1, 3).copy()
               if has_nrm else np.zeros_like(positions))
    uvs = (np.frombuffer(body, dtype="<f4", count=num_verts * 2, offset=uv_off).reshape(-1, 2).copy()
           if uvsets else np.zeros((num_verts, 2), dtype=np.float32))
    # RW triangle: u16 v2, v1, v0, materialIndex — store as (v0, v1, v2, mat)
    raw = np.frombuffer(body, dtype="<u2", count=num_tris * 4, offset=tri_off).reshape(-1, 4)
    triangles = raw[:, [2, 1, 0, 3]].astype(np.uint16)

    mlist = one(geom.body, ID_MATERIALLIST)
    mstruct = one(mlist.body, ID_STRUCT)
    (num_materials,) = struct.unpack_from("<I", mstruct.body)
    materials: list[Material] = []
    for mc in [c for c in mlist.sub() if c.type == ID_MATERIAL]:
        ms = one(mc.body, ID_STRUCT)
        textured = struct.unpack_from("<I", ms.body, 20)[0]
        texture = None
        name = None
        for sub in mc.sub():
            if sub.type == ID_TEXTURE:
                strs = [c for c in sub.sub() if c.type == ID_STRING]
                if strs:
                    texture = _cstr(strs[0].body, 0)
            elif sub.type == ID_EXTENSION:
                for sc in sub.sub():
                    if sc.type == ID_STRING:
                        name = _cstr(sc.body, 0)
        materials.append(Material(name=name, texture=texture, textured=bool(textured)))
    if len(materials) != num_materials:
        raise ValueError(f"material list says {num_materials}, found {len(materials)}")

    groups: list[tuple[int, np.ndarray]] = []
    bone_indices = bone_weights = None
    bone_names: list[str] = []
    for sub in geom.sub():
        if sub.type != ID_EXTENSION:
            continue
        for plugin in sub.sub():
            if plugin.type == ID_BINMESH:
                groups = _read_binmesh(plugin.body, num_tris)
            elif plugin.type == ID_SKIN:
                # Best effort: the head pipeline recomputes weights against the
                # PD2 skeleton, so a layout this reader does not know is not fatal.
                try:
                    bone_indices, bone_weights, bone_names = _read_skin(plugin.body, num_verts)
                except ValueError:
                    bone_indices = bone_weights = None
                    bone_names = []

    return DffModel(
        frames=frames, positions=positions, normals=normals, uvs=uvs,
        triangles=triangles, materials=materials, groups=groups,
        bone_indices=bone_indices, bone_weights=bone_weights,
        bone_names=bone_names or [f.name for f in frames],
    )


def _read_binmesh(body: memoryview, num_tris: int) -> list[tuple[int, np.ndarray]]:
    """RpBinMesh: flag u32, numMeshes u32, totalIndices u32, then per mesh:
    matIndex u32, numIndices u32, numTris u32, indices u32[numIndices]."""
    flag, num_meshes, total_indices = struct.unpack_from("<III", body)
    del flag
    out: list[tuple[int, np.ndarray]] = []
    off = 12
    got = 0
    for _ in range(num_meshes):
        # this exporter writes (numIndices, matIndex), not the (matIndex, numIndices)
        # order of the RW sample viewer
        num_indices, mat_index = struct.unpack_from("<II", body, off)
        off += 8
        idx = np.frombuffer(body, dtype="<u4", count=num_indices, offset=off).astype(np.int64)
        off += num_indices * 4
        got += num_indices
        if num_indices % 3:
            raise ValueError(f"binmesh group {mat_index}: {num_indices} indices not divisible by 3")
        out.append((mat_index, idx.reshape(-1, 3)))
    if off != len(body) or got != total_indices:
        raise ValueError(f"BinMesh layout mismatch: consumed {off} of {len(body)}, {got} of {total_indices} indices")
    del num_tris
    return out


def _read_skin(body: memoryview, num_verts: int):
    """GTA SA RpSkin PLG: usedBones u32? — verified against the file extents here.

    Layout this source uses: ``u32 numUsedBones`` is absent; it is the classic
    SA ``SkinPLG``: ``u8 numBones, u8 pad, u16 pad2``? We determine the layout
    arithmetically instead of guessing: the plugin holds a used-bone index
    table, per-vertex ``(u8 idx x4, u8 weight x4)``, then 16-byte matrices per
    used bone, and a 64-byte inverse-bind matrix per bone.
    """
    n = len(body)
    # The per-vertex block in SA is 12 bytes: 4 u8 indices + 4 u8 weights + 4 pad? or 4+4=8.
    # Try the standard SA layout: u8[4] indices, u8[4] weights (weights sum to 255).
    # Header: numBones u8? — find the header size H such that
    #   H + num_verts*12 + numBones*64 + numBones*64 == n   (common SA variant)
    # or  H + num_verts*8  + ... Try known shapes.
    # Observed header start of this file: 20 19 04 00 then ascending used-bone ids,
    # so: u16 numUsedBones (=0x1920? no) — instead treat first 4 bytes as u32 = 0x41920.
    # Probing: assume header = u8 numBones, u8 pad, u16 pad, then u8 used[numUsed] ...
    # Simplest robust route for THIS file: derive counts from num_verts and n.
    for hdr, vert_size, mats_per, inv_per in (
        (8, 12, 64, 64), (8, 8, 64, 64), (4, 12, 64, 64), (4, 8, 64, 64),
    ):
        for num_bones in range(1, 256):
            for num_used in (num_bones,):
                rest = n - hdr - num_used - num_verts * vert_size
                if rest < 0:
                    continue
                if rest == num_used * (mats_per + inv_per) or rest == num_bones * (mats_per + inv_per):
                    off = hdr
                    used = np.frombuffer(body, dtype=np.uint8, count=num_used, offset=off)
                    off += num_used
                    block = np.frombuffer(body, dtype=np.uint8, count=num_verts * vert_size,
                                          offset=off).reshape(num_verts, vert_size)
                    idx = block[:, :4].astype(np.uint8)
                    wts = block[:, 4:8].astype(np.float32)
                    wsum = wts.sum(axis=1, keepdims=True)
                    wts = np.where(wsum > 0, wts / np.maximum(wsum, 1), 0).astype(np.float32)
                    return idx, wts, [f"bone{int(b)}" for b in used]
    raise ValueError(f"Skin PLG layout not recognised: {n} bytes for {num_verts} vertices")


def read_txd(data: bytes) -> list[Raster]:
    root = chunks(memoryview(data))
    if len(root) != 1 or root[0].type != ID_TEXDICTIONARY:
        raise ValueError("expected one TexDictionary at the top of a TXD")
    txd = root[0]
    struct_c = one(txd.body, ID_STRUCT)
    # (u16 numTextures, u16 deviceId)
    (num_textures,) = struct.unpack_from("<H", struct_c.body)
    rasters: list[Raster] = []
    for tn in [c for c in txd.sub() if c.type == ID_TEXTURENATIVE]:
        rasters.append(_read_texture_native(tn.body))
    if num_textures != len(rasters):
        raise ValueError(f"TXD says {num_textures} textures, parsed {len(rasters)}")
    return rasters


def _read_texture_native(body: memoryview) -> Raster:
    """GTA SA TextureNative (D3D9): struct chunk holding the header + one top mip."""
    struct_c = one(body, ID_STRUCT)
    b = struct_c.body
    platform, filter_flags = struct.unpack_from("<II", b)
    if platform not in (8, 9):
        raise ValueError(f"TextureNative platform {platform:#x}, expected D3D8/9")
    del filter_flags
    name = _cstr(b, 8)
    raster_format, d3d_format, width, height = struct.unpack_from("<IIHH", b, 72)
    del raster_format
    # this exporter stores one mip level; the payload follows the 92-byte header
    payload = bytes(b[92:])
    fourcc = d3d_format
    if fourcc == 0x31545844:  # 'DXT1'
        rgba = _decode_bc(payload, width, height, mode="dxt1")
    elif fourcc == 0x33545844:  # 'DXT3'
        rgba = _decode_bc(payload, width, height, mode="dxt3")
    elif fourcc == 0x35545844:  # 'DXT5'
        rgba = _decode_bc(payload, width, height, mode="dxt5")
    else:
        raise ValueError(f"texture {name!r}: unsupported fourcc {fourcc:#x}")
    return Raster(name=name, width=width, height=height, rgba=rgba)


def _decode_bc(raw: bytes, width: int, height: int, mode: str) -> np.ndarray:
    """DXT1/DXT3/DXT5 top mip to RGBA (numpy only: this module stays importable early)."""
    data = np.frombuffer(raw, dtype=np.uint8)
    bw, bh = (width + 3) // 4, (height + 3) // 4
    block_size = 8 if mode == "dxt1" else 16
    if data.size != bw * bh * block_size:
        raise ValueError(f"raster payload {data.size} != {bw * bh * block_size} ({mode} {width}x{height})")
    out = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
    idx = 0
    for by in range(bh):
        for bx in range(bw):
            blk = data[idx: idx + block_size]
            idx += block_size
            if mode == "dxt1":
                alpha = np.full((4, 4), 255, dtype=np.uint8)
                color = blk
            else:
                # DXT3: 64 bits of explicit 4-bit alpha; DXT5: interpolated alpha block
                if mode == "dxt3":
                    abits = int.from_bytes(blk[:8], "little")
                    ai = np.array([(abits >> (4 * i)) & 15 for i in range(16)], dtype=np.int32)
                    alpha = (ai * 17).astype(np.uint8).reshape(4, 4)
                else:
                    a0, a1 = int(blk[0]), int(blk[1])
                    abits = int.from_bytes(blk[2:8], "little")
                    atab = np.zeros(8, dtype=np.float32)
                    atab[0], atab[1] = a0, a1
                    if a0 > a1:
                        for i in range(1, 7):
                            atab[i + 1] = ((7 - i) * a0 + i * a1) / 7.0
                    else:
                        for i in range(1, 5):
                            atab[i + 1] = ((5 - i) * a0 + i * a1) / 5.0
                        atab[6], atab[7] = 0.0, 255.0
                    ai = np.array([(abits >> (3 * i)) & 7 for i in range(16)], dtype=np.int32)
                    alpha = atab[ai].astype(np.uint8).reshape(4, 4)
                color = blk[8:]
            c0, c1 = struct.unpack_from("<HH", color)
            bits = int.from_bytes(color[4:8], "little")
            r0 = np.array([(c0 >> 11) & 31, (c0 >> 5) & 63, c0 & 31], dtype=np.float32)
            r1 = np.array([(c1 >> 11) & 31, (c1 >> 5) & 63, c1 & 31], dtype=np.float32)
            r0 = r0 * 255 / np.array([31, 63, 31])
            r1 = r1 * 255 / np.array([31, 63, 31])
            pal = np.zeros((4, 3), dtype=np.float32)
            pal[0], pal[1] = r0, r1
            if mode != "dxt1" or c0 > c1:
                pal[2] = (2 * r0 + r1) / 3
                pal[3] = (r0 + 2 * r1) / 3
            else:
                pal[2] = (r0 + r1) / 2
                pal[3] = 0.0
            ci = np.array([(bits >> (2 * i)) & 3 for i in range(16)], dtype=np.int32).reshape(4, 4)
            out[by * 4: by * 4 + 4, bx * 4: bx * 4 + 4, :3] = pal[ci].astype(np.uint8)
            out[by * 4: by * 4 + 4, bx * 4: bx * 4 + 4, 3] = alpha
    return out[:height, :width]


# ---------------------------------------------------------------- CLI


def extract_rar(rar: Path, out: Path) -> Path:
    import subprocess
    script = out.parent / "unrar-js" / "extract.js"
    script.parent.mkdir(parents=True, exist_ok=True)
    if not script.is_file():
        script.write_text(
            'const { createExtractorFromFile } = require("node-unrar-js");\n'
            "(async () => {\n"
            "  const ex = await createExtractorFromFile({filepath: process.argv[2], targetPath: process.argv[3]});\n"
            "  let n = 0; for (const f of ex.extract().files) n++;\n"
            "  console.log('extracted entries:', n);\n"
            "})().catch((e) => { console.error(e); process.exit(1); });\n",
            encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    out.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["node", str(script), str(rar), str(out)],
                            cwd=root, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"node-unrar-js failed: {result.stderr}")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("probe", "dump"):
        p = sub.add_parser(name)
        p.add_argument("source", type=Path, help="a .rar holding the dff/txd, or a directory with them")
    args = ap.parse_args(argv)

    src: Path = args.source
    if src.is_dir():
        folder = src
    else:
        folder = extract_rar(src, Path("build") / "rw_dff" / src.stem)
    dff_path = next(folder.glob("*.dff"))
    txd_path = next(folder.glob("*.txd"))
    dff = read_dff(dff_path.read_bytes())
    rasters = read_txd(txd_path.read_bytes())

    print(f"{dff_path.name}: {len(dff.positions)} verts, {len(dff.triangles)} tris, "
          f"{len(dff.materials)} materials, {len(dff.frames)} frames")
    per_mat = {i: 0 for i in range(len(dff.materials))}
    for mat_index, vidx in dff.groups:
        per_mat[mat_index] = per_mat.get(mat_index, 0) + len(vidx)
    for i, m in enumerate(dff.materials):
        print(f"  [{i}] {m.name or '-':24} tex={m.texture or '-':24} tris={per_mat.get(i, 0)}")
    print(f"{txd_path.name}: {len(rasters)} rasters")
    for r in rasters:
        print(f"  {r.name:32} {r.width}x{r.height}")
    print("frames:", ", ".join(f.name.strip() or "?" for f in dff.frames))
    if dff.bone_weights is not None:
        w = dff.bone_weights
        print(f"skin: bones={len(dff.bone_names)} mean max weight {w.max(axis=1).mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
