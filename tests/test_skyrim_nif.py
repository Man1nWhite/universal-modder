"""Tests for the Skyrim SE NIF reader in tools/skyrim-nif.

The fixtures are built here, byte by byte, so the suite runs offline and stays
meaningful if the user-supplied archives are absent: a synthetic 20.2.0.7 file
exercises the header/block table, node hierarchy, a BSTriShape with inline
vertex data, a skinned shape whose geometry lives in NiSkinPartition, the
material/alpha blocks, and the byte-exact error paths.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "skyrim-nif"))

import nif  # noqa: E402


# ---------------------------------------------------------------------------
# a tiny NIF writer, only for the fields the reader cares about
# ---------------------------------------------------------------------------
def _s32(s: str) -> bytes:
    raw = s.encode("cp1252")
    return struct.pack("<I", len(raw)) + raw


class NifBuilder:
    def __init__(self, stream_version: int = 100, user_version: int = 12):
        self.stream_version = stream_version
        self.user_version = user_version
        self.blocks: list[tuple[str, bytes]] = []
        self.strings: list[str] = []

    def add(self, type_name: str, payload: bytes) -> int:
        self.blocks.append((type_name, payload))
        return len(self.blocks) - 1

    def string_id(self, s: str) -> int:
        if s not in self.strings:
            self.strings.append(s)
        return self.strings.index(s)

    # -- helpers for the common blocks -----------------------------------
    def node(self, name: str, children: list[int], translation=(0.0, 0.0, 0.0),
             rotation=None, scale: float = 1.0) -> int:
        rot = rotation or (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        p = struct.pack("<I", self.string_id(name))          # NiObjectNET name
        p += struct.pack("<I", 0)                            # extra data array
        p += struct.pack("<I", 0xFFFFFFFF)                   # controller
        p += struct.pack("<I", 0x0000020E)                   # NiAVObject flags
        p += struct.pack("<3f", *translation)
        p += struct.pack("<9f", *rot)
        p += struct.pack("<f", scale)
        p += struct.pack("<I", 0xFFFFFFFF)                   # collision
        p += struct.pack("<I", len(children)) + b"".join(struct.pack("<I", c) for c in children)
        p += struct.pack("<I", 0)                            # effect refs
        return self.add("NiNode", p)

    def texture_set(self, paths: list[str]) -> int:
        p = struct.pack("<I", len(paths)) + b"".join(_s32(t) for t in paths)
        return self.add("BSShaderTextureSet", p)

    def shader(self, name: str, tex_ref: int, shader_type: int = 1,
               flags1: int = 0x80400203, flags2: int = 0x00000081) -> int:
        p = struct.pack("<I", shader_type)                   # NiObjectNET preamble
        p += struct.pack("<I", self.string_id(name))
        p += struct.pack("<I", 0)                            # extra data array
        p += struct.pack("<I", 0xFFFFFFFF)                   # controller
        p += struct.pack("<II", flags1, flags2)
        p += struct.pack("<2f", 0.0, 0.0)                    # uv offset
        p += struct.pack("<2f", 1.0, 1.0)                    # uv scale
        p += struct.pack("<I", tex_ref)
        p += struct.pack("<3f", 0.0, 0.0, 0.0)               # emissive colour
        p += struct.pack("<f", 1.0)                          # emissive multiple
        p += struct.pack("<I", 3)                            # texture clamp mode
        p += struct.pack("<f", 1.0)                          # alpha
        p += struct.pack("<f", 0.0)                          # refraction strength
        p += struct.pack("<f", 10.0)                         # glossiness
        p += struct.pack("<3f", 1.0, 1.0, 1.0)               # specular colour
        p += struct.pack("<f", 1.0)                          # specular strength
        p += struct.pack("<f", 0.3)                          # soft lighting
        p += struct.pack("<f", 2.0)                          # rimlight power
        if shader_type == 1:                                 # environment map
            p += struct.pack("<f", 1.0)
        elif shader_type == 5:                               # skin tint
            p += struct.pack("<3f", 0.0, 0.0, 0.0)
            if self.stream_version >= 130:
                p += struct.pack("<f", 1.0)
        return self.add("BSLightingShaderProperty", p)

    def alpha(self, flags: int = 4844, threshold: int = 128) -> int:
        p = struct.pack("<I", self.string_id(""))
        p += struct.pack("<I", 0)
        p += struct.pack("<I", 0xFFFFFFFF)
        p += struct.pack("<HB", flags, threshold)
        return self.add("NiAlphaProperty", p)

    @staticmethod
    def vertex_blob(verts, uvs, normals, weights=None, bones=None) -> bytes:
        """BSVertexData: pos 12 + bitangentX 4 | uv half2 | normal 3 + bitangentY |
        weights half4 + bone indices 4 (only when skinned)."""
        out = bytearray()
        for i in range(len(verts)):
            out += struct.pack("<3f", *verts[i])
            out += struct.pack("<f", 0.0)                    # bitangent X
            out += struct.pack("<2e", *uvs[i])
            n = np.clip((np.asarray(normals[i]) + 1.0) * 127.5, 0, 255).astype(np.uint8)
            out += bytes(int(v) for v in n) + b"\x00"
            if weights is not None:
                out += struct.pack("<4e", *weights[i])
                out += bytes(int(b) for b in bones[i])
        return bytes(out)

    def shape(self, name: str, verts, uvs, normals, tris, skin_ref=0xFFFFFFFF,
              shader_ref=0xFFFFFFFF, alpha_ref=0xFFFFFFFF, data_size=None,
              weights=None, bones=None, skinned=False) -> int:
        # vertex flags: position | uv | normal (+skinned), always full precision;
        # main vertex size 16 bytes (position + bitangentX) in bits 8-15.
        desc = 0x1 | 0x2 | 0x8 | 0x400
        if skinned:
            desc |= 0x40
        desc |= 4 << 8
        desc |= desc << 44
        blob = b"" if skinned else self.vertex_blob(verts, uvs, normals)
        if data_size is None:
            data_size = len(blob)
        p = struct.pack("<I", self.string_id(name))
        p += struct.pack("<I", 0)
        p += struct.pack("<I", 0xFFFFFFFF)
        p += struct.pack("<I", 0x0000020E)
        p += struct.pack("<3f", 0.0, 0.0, 0.0)                   # translation
        p += struct.pack("<9f", 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        p += struct.pack("<f", 1.0)
        p += struct.pack("<I", 0xFFFFFFFF)                       # collision
        p += struct.pack("<3f", 0.0, 0.0, 0.0)                   # bounding centre
        p += struct.pack("<f", 1.0)                              # radius
        p += struct.pack("<III", skin_ref, shader_ref, alpha_ref)
        p += struct.pack("<Q", desc)
        # SSE (user 12 / stream 100): u16 triangle count, u16 vertex count, u32 size
        p += struct.pack("<HHI", len(tris), len(verts), data_size)
        if data_size:
            p += blob
            p += np.asarray(tris, "<u2").tobytes()
        p += struct.pack("<I", 0)                                # particle data size
        return self.add("BSTriShape", p)

    def skin(self, bone_refs: list[int], parts: list[tuple[int, int]],
             data_ref: int, partition_ref: int) -> int:
        p = struct.pack("<III", data_ref, partition_ref, 0xFFFFFFFF)
        p += struct.pack("<I", len(bone_refs))
        p += b"".join(struct.pack("<I", b) for b in bone_refs)
        p += struct.pack("<I", len(parts))
        for flags, part_id in parts:
            p += struct.pack("<HH", flags, part_id)
        return self.add("BSDismemberSkinInstance", p)

    def partition(self, verts, uvs, normals, weights, bones, tris,
                  part_bones: list[int]) -> int:
        desc = 0x1 | 0x2 | 0x8 | 0x40 | 0x400
        desc |= 4 << 8
        desc |= (desc & 0xFFFFFF) << 44
        blob = self.vertex_blob(verts, uvs, normals, weights, bones)
        p = struct.pack("<I", 1)                                 # partitions
        p += struct.pack("<I", len(blob))
        p += struct.pack("<I", 32)                               # vertex size
        p += struct.pack("<Q", desc)
        p += blob
        p += struct.pack("<5H", len(verts), len(tris), len(part_bones), 0, 4)
        p += b"".join(struct.pack("<H", b) for b in part_bones)
        p += struct.pack("<B", 1) + np.arange(len(verts), dtype="<u2").tobytes()
        p += struct.pack("<B", 1) + np.zeros((len(verts), 4), "<f4").tobytes()
        p += struct.pack("<B", 1)                                # has faces
        p += np.asarray(tris, "<u2").tobytes()
        p += struct.pack("<B", 0)                                # has bone indices
        p += struct.pack("<BB", 0, 0)                            # lod, global VB
        p += struct.pack("<Q", desc)
        p += np.asarray(tris, "<u2").tobytes()                   # trueTriangles
        return self.add("NiSkinPartition", p)

    def build(self) -> bytes:
        types: list[str] = []
        type_indices: list[int] = []
        for type_name, _payload in self.blocks:
            if type_name not in types:
                types.append(type_name)
            type_indices.append(types.index(type_name))

        head = b"Gamebryo File Format, Version 20.2.0.7\n"
        head += struct.pack("<I", 0x14020007)
        head += struct.pack("<B", 1)                             # little endian
        head += struct.pack("<I", self.user_version)
        head += struct.pack("<I", len(self.blocks))
        head += struct.pack("<I", self.stream_version)
        head += struct.pack("<B", 0) + b""                       # creator (empty)
        head += struct.pack("<B", 0)                             # export info 1
        head += struct.pack("<B", 0)                             # export info 2
        head += struct.pack("<H", len(types))
        for t in types:
            head += _s32(t)
        for idx in type_indices:
            head += struct.pack("<H", idx)
        for _name, payload in self.blocks:
            head += struct.pack("<I", len(payload))
        head += struct.pack("<I", len(self.strings))
        head += struct.pack("<I", max((len(s) for s in self.strings), default=0))
        for s in self.strings:
            head += _s32(s)
        head += struct.pack("<I", 0)                             # groups
        body = b"".join(payload for _name, payload in self.blocks)
        footer = struct.pack("<I", 1) + struct.pack("<I", 0)     # one root
        return head + body + footer


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
QUAD = dict(
    verts=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 20.0), (0.0, 0.0, 20.0)],
    uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    normals=[(0.0, -1.0, 0.0)] * 4,
    tris=[(0, 1, 2), (0, 2, 3)],
)


@pytest.fixture
def static_nif() -> bytes:
    b = NifBuilder()
    tex = b.texture_set(["textures\\exampleauthor\\outfit\\skirt_diffa.dds",
                         "textures\\exampleauthor\\outfit\\skirt_norm.dds",
                         "", "", "textures\\exampleauthor\\outfit\\bloodfree_e.dds"])
    shader = b.shader("mtr_skirt", tex, shader_type=1)
    alpha = b.alpha(4844, 128)
    mesh = b.shape("0_Skirt", QUAD["verts"], QUAD["uvs"], QUAD["normals"], QUAD["tris"],
                   shader_ref=shader, alpha_ref=alpha)
    b.node("Scene Root", [mesh])
    return b.build()


@pytest.fixture
def skinned_nif() -> bytes:
    b = NifBuilder()
    pelvis = b.node("NPC Pelvis [Pelv]", [])
    thigh = b.node("NPC L Thigh [LThg]", [], translation=(-6.62, 0.0, 68.91))
    b.node("Scene Root", [pelvis, thigh])
    weights = [(0.75, 0.25, 0.0, 0.0)] * 4
    bone_ids = [(0, 1, 0, 0)] * 4
    part = b.partition(QUAD["verts"], QUAD["uvs"], QUAD["normals"], weights, bone_ids,
                       QUAD["tris"], [0, 1])
    skin = b.skin([pelvis, thigh], [(0, 52)], data_ref=0xFFFFFFFF, partition_ref=part)
    tex = b.texture_set(["textures\\exampleauthor\\outfit\\jacket_diffa.dds"])
    shader = b.shader("mtr_jacket", tex, shader_type=1)
    b.shape("0_Jacket", QUAD["verts"], QUAD["uvs"], QUAD["normals"], QUAD["tris"],
            skin_ref=skin, shader_ref=shader, data_size=0, skinned=True,
            weights=weights, bones=bone_ids)
    return b.build()


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
def test_header_and_version(static_nif):
    f = nif.parse(static_nif, "static.nif")
    assert f.version == "20.2.0.7"
    assert (f.user_version, f.stream_version) == (12, 100)


def test_node_hierarchy(static_nif):
    f = nif.parse(static_nif, "static.nif")
    names = f.node_names()
    assert "Scene Root" in names
    assert f.shade() == "static mesh (no skinning)"


def test_static_geometry(static_nif):
    f = nif.parse(static_nif, "static.nif")
    (shape,) = f.shapes
    assert shape.name == "0_Skirt"
    assert shape.num_vertices == 4
    assert shape.num_triangles == 2
    np.testing.assert_allclose(shape.vertices[:, 2], [0, 0, 20, 20])
    np.testing.assert_allclose(shape.uvs, np.array(QUAD["uvs"], np.float32))
    assert shape.weights is None


def test_materials_and_alpha(static_nif):
    f = nif.parse(static_nif, "static.nif")
    (shape,) = f.shapes
    assert shape.shader_type == 1
    assert (shape.alpha_flags, shape.alpha_threshold) == (4844, 128)
    assert shape.textures[0].endswith("skirt_diffa.dds")
    assert shape.textures[3] == ""


def test_geometry_from_skin_partition(skinned_nif):
    """The SSE case that matters: shape.dataSize == 0, data lives in the partition."""
    f = nif.parse(skinned_nif, "skinned.nif")
    (shape,) = f.shapes
    assert f.shade() == "skinned mesh"
    assert shape.num_vertices == 4
    assert shape.num_triangles == 2
    assert shape.bones == ["NPC Pelvis [Pelv]", "NPC L Thigh [LThg]"]
    assert shape.body_parts == [52]
    np.testing.assert_allclose(shape.weights.sum(axis=1), 1.0, atol=1e-6)
    assert set(shape.bone_weights()) == {"NPC Pelvis [Pelv]", "NPC L Thigh [LThg]"}


def test_world_transform_composition(static_nif):
    b = NifBuilder()
    child = b.node("child", [], translation=(1.0, 2.0, 3.0))
    root = b.node("root", [child], translation=(10.0, 0.0, 0.0))
    f = nif.parse(b.build(), "tree.nif")
    world = f.nodes[child].world_matrix(f.nodes)
    np.testing.assert_allclose(world[:3, 3], [11.0, 2.0, 3.0], atol=1e-6)
    assert nodes_are_linked(f, root, child)


def nodes_are_linked(f, parent, child) -> bool:
    return f.nodes[child].parent == parent


def test_rejects_non_nif():
    with pytest.raises(nif.NifError):
        nif.parse(b"not a nif at all", "x.nif")


def test_truncated_header_is_reported():
    with pytest.raises(nif.NifError):
        nif.parse(b"Gamebryo File Format, Version 20.2.0.7\n\x07\x00", "cut.nif")


def test_bone_weight_ranking():
    """`bone_weights` must rank by total vertex weight, not by bone index."""
    b = NifBuilder()
    a = b.node("A", [])
    c = b.node("C", [])
    b.node("Scene Root", [a, c])
    weights = [(0.9, 0.1, 0.0, 0.0), (0.9, 0.1, 0.0, 0.0),
               (0.2, 0.8, 0.0, 0.0), (0.2, 0.8, 0.0, 0.0)]
    bones = [(0, 1, 0, 0)] * 4
    part = b.partition(QUAD["verts"], QUAD["uvs"], QUAD["normals"], weights, bones,
                       QUAD["tris"], [0, 1])
    skin = b.skin([a, c], [(0, 32)], data_ref=0xFFFFFFFF, partition_ref=part)
    b.shape("0_Test", QUAD["verts"], QUAD["uvs"], QUAD["normals"], QUAD["tris"],
            skin_ref=skin, data_size=0, skinned=True, weights=weights, bones=bones)
    f = nif.parse(b.build(), "w.nif")
    (shape,) = f.shapes
    ranked = list(shape.bone_weights().items())
    assert ranked[0][0] in ("A", "C")
    assert ranked == sorted(ranked, key=lambda kv: -kv[1])
    # half-float weights: 4 vertices x 1.0 total each, to fp16 precision
    assert sum(shape.bone_weights().values()) == pytest.approx(4.0, abs=2e-3)


def test_skeleton_map_covers_garment_bones():
    """Every bone named in the map must exist in the PD2 target or a fold target."""
    import json

    data = json.loads((ROOT / "tools" / "skyrim-nif" / "skeleton_map.json").read_text())
    target = set(json.loads(
        (ROOT / "tools" / "pd2-las" / "las_target_skeleton.json").read_text())["skeleton"])
    for source, dest in data["map"].items():
        assert dest in target, f"{source} -> {dest} is not a PD2 deform bone"
    for source, dest in data["fold"].items():
        if source == "comment":
            continue
        assert dest in target, f"fold {source} -> {dest} is not a PD2 deform bone"
    assert data["drop"]["fallback_target"] in target


# ---------------------------------------------------------------------------
# legacy geometry: the `_g` collision NIFs use NiTriShape + NiTriShapeData
# ---------------------------------------------------------------------------
def _legacy_shape(b: NifBuilder, name: str, data_ref: int,
                  shader_ref: int = 0xFFFFFFFF) -> int:
    p = struct.pack("<I", b.string_id(name))          # NiObjectNET name
    p += struct.pack("<I", 0)                        # extra data array
    p += struct.pack("<I", 0xFFFFFFFF)               # controller
    p += struct.pack("<I", 0x0000020E)               # flags
    p += struct.pack("<3f", 0.0, 0.0, 0.0)           # translation
    p += struct.pack("<9f", 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    p += struct.pack("<f", 1.0)                      # scale
    p += struct.pack("<I", 0xFFFFFFFF)               # collision
    p += struct.pack("<I", data_ref)                 # data ref
    p += struct.pack("<I", 0xFFFFFFFF)               # skin ref
    p += struct.pack("<I", 0)                        # material names
    p += struct.pack("<I", 0)                        # active material
    p += struct.pack("<B", 0)                        # defaultMatNeedsUpdateFlag
    p += struct.pack("<I", shader_ref)               # shader property
    p += struct.pack("<I", 0xFFFFFFFF)               # alpha property
    p += struct.pack("<I", 0)                        # particle data size
    return b.add("NiTriShape", p)


def _legacy_data(b: NifBuilder, verts, uvs, normals, tris) -> int:
    n = len(verts)
    p = struct.pack("<I", 0)                         # groupID
    p += struct.pack("<H", n)
    p += struct.pack("<BB", 0, 0)                    # keep/compress flags
    p += struct.pack("<B", 1) + np.asarray(verts, "<f4").tobytes()
    p += struct.pack("<H", 0x0001)                   # data flags: one UV set
    p += struct.pack("<I", 0)                        # material CRC (stream > 34)
    p += struct.pack("<B", 1) + np.asarray(normals, "<f4").tobytes()
    p += struct.pack("<3f", 0.0, 0.0, 10.0)          # bounds centre
    p += struct.pack("<f", 20.0)                     # bounds radius
    p += struct.pack("<B", 0)                        # no vertex colours
    p += np.asarray(uvs, "<f4").tobytes()
    p += struct.pack("<H", 0x4000)                   # consistency flags (static)
    p += struct.pack("<I", 0xFFFFFFFF)               # additional data
    p += struct.pack("<H", len(tris))                # numTriangles
    p += struct.pack("<I", len(tris) * 3)            # numTrianglePoints
    p += struct.pack("<B", 1) + np.asarray(tris, "<u2").tobytes()
    p += struct.pack("<H", 0)                        # no match groups
    return b.add("NiTriShapeData", p)


@pytest.fixture
def legacy_nif() -> bytes:
    b = NifBuilder()
    data = _legacy_data(b, QUAD["verts"], QUAD["uvs"], QUAD["normals"], QUAD["tris"])
    shape = _legacy_shape(b, "0_Skirt", data)
    b.node("Scene Root", [shape])
    return b.build()


def test_legacy_nitrishape_geometry(legacy_nif):
    """`_g` NIFs store geometry in a separate NiTriShapeData block, not inline."""
    f = nif.parse(legacy_nif, "g.nif")
    (shape,) = f.shapes
    assert shape.name == "0_Skirt"
    assert shape.num_vertices == 4
    assert shape.num_triangles == 2
    np.testing.assert_allclose(shape.vertices, np.array(QUAD["verts"], np.float32))
    np.testing.assert_allclose(shape.uvs, np.array(QUAD["uvs"], np.float32))
    assert f.shade() == "static mesh (no skinning)"


# ---------------------------------------------------------------------------
# nifly cross-check bridge (needs the compiled library; skipped otherwise)
# ---------------------------------------------------------------------------
import nifly_bridge  # noqa: E402


def _nifly_lib():
    try:
        nifly_bridge.load()
    except nifly_bridge.NiflyUnavailable as exc:
        pytest.skip(f"nifly not built: {exc}")
    return True


def test_nifly_bridge_reads_synthetic_file(legacy_nif):
    """The ctypes bridge must decode the same bytes the Python reader does."""
    _nifly_lib()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "g.nif"
        path.write_bytes(legacy_nif)
        with nifly_bridge.NiflyFile(path) as f:
            assert "loaded" in f.status.lower(), f.status
            (shape,) = f.shapes()
            assert shape["name"] == "0_Skirt"
            np.testing.assert_allclose(shape["vertices"],
                                       np.array(QUAD["verts"], np.float32))
            assert len(shape["triangles"]) == 2


def test_nifly_bridge_rejects_missing_file(tmp_path):
    """A missing file is a bad argument (ValueError), not a missing library."""
    _nifly_lib()
    with pytest.raises(ValueError, match="failed to load"):
        nifly_bridge.NiflyFile(tmp_path / "nope.nif")


@pytest.mark.skipif(not (ROOT / "4.zip").exists(), reason="4.zip absent")
def test_crosscheck_against_nifly():
    """Full audit: nif.py and nifly must agree on every user-supplied mesh."""
    _nifly_lib()
    import crosscheck

    report = crosscheck.run(ROOT)
    passed, failed = crosscheck.summarize(report)
    assert passed > 0
    failing = [(f["file"], c["check"]) for f in report["files"]
               for c in f["checks"] if not c["ok"]]
    assert not failing, f"{failed} failing checks: {failing[:5]}"
