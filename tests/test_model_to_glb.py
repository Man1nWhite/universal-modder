"""`model_to_glb.py`: a Diesel `.model` becomes a glTF 2.0 `.glb` plus its `.dds`.

The conversion is built on four measured conventions (`AGENTS.md` invariants 2-4,
plus this fork's render convention for v), and each one has a way of being wrong
that a viewer shows and a byte comparison does not. These tests pin them on a
synthetic unit: coordinates and units, the UV flip, the shared vertex buffer
behind RenderAtom indices, `ALPHA_MASKED` → `alphaMode: MASK`, the DDS copy, and
both skinning contracts (bind matrices compose to the identity; a palette that is
one bone short is repaired to the rig the writer intended and says so).

Nothing here reads a tracked pack: the fixtures are written by the same codecs the
builders write with, so the test needs no game assets and no 2B templates.
"""
from __future__ import annotations

import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import dds_encode as de  # noqa: E402
import diesel_model as dm  # noqa: E402
import model_to_glb as mtg  # noqa: E402

COMPONENT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16,
             5125: np.uint32, 5126: np.float32}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

#: a 150-160 cm quad in diesel space: (x, y, z) cm, z up
VERTS = [(0.0, 0.0, 150.0), (10.0, 0.0, 150.0), (10.0, 10.0, 160.0), (0.0, 10.0, 160.0)]
NORMALS = [(0.0, 0.0, 1.0)] * 4
#: diesel uv0 is bottom-up: v = 1 is the top row of the image
UV0 = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
INDICES = [0, 1, 2, 0, 2, 3]


def _ibm(translation) -> tuple:
    """A row-vector inverse bind matrix: `p @ M` moves p by `translation`."""
    m = np.eye(4)
    m[3, :3] = translation
    return tuple(float(v) for v in m.flatten())


def _bone_world(translation) -> tuple:
    m = np.eye(4)
    m[3, :3] = translation
    return tuple(float(v) for v in m.flatten())


def _translate_inverse(translation) -> tuple:
    """`inverse` of the row-vector world matrix that translates by `translation`."""
    return _ibm(tuple(-t for t in translation))


def build_model(*, blendindices=None, weights=None, objects=(7, 9), root=7,
                diffuse=True) -> bytes:
    """A two-material quad drawable with a two-bone skin, as the builders write one."""
    blendindices = blendindices or [(0, 0, 0, 0), (0, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 0)]
    weights = weights or [(0.75, 0.25, 0.0), (0.75, 0.25, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    geom = {
        "vert_count": len(VERTS),
        "headers": [{"item_size": 3, "enum_type": dm.POSITION0},
                    {"item_size": 2, "enum_type": dm.TEXCOORD0},
                    {"item_size": 7, "enum_type": dm.BLENDINDICES0},
                    {"item_size": 3, "enum_type": dm.BLENDWEIGHT0},
                    {"item_size": 3, "enum_type": dm.NORMAL0},
                    {"item_size": 3, "enum_type": dm.UV_DIRECTION_V0},
                    {"item_size": 3, "enum_type": dm.UV_DIRECTION_U0}],
        "verts": VERTS, "uv0": UV0, "normals": NORMALS,
        "blendindices": blendindices, "blendweights": weights,
        "uvdir_v": [(0.0, 0.0, 1.0)] * 4, "uvdir_u": [(1.0, 0.0, 0.0)] * 4,
        "name_hash": dm.hash64("g_test.DieselGeometry"), "remaining": b"",
    }
    topo = {"primitive": 3, "indices": INDICES, "items2": b"",
            "name_hash": dm.hash64("g_test.Topology"), "remaining": b""}
    md = {
        "name_hash": dm.hash64("g_test"), "anims": [],
        "matrix": tuple(np.eye(4).flatten().tolist()), "pos": (0.0, 0.0, 0.0), "parent": 0,
        "version": 3, "passthroughgp": 142, "topologyip": 143,
        "atoms": [{"base_vertex": 0, "tri_count": len(INDICES) // 3, "base_index": 0,
                   "slice_len": len(VERTS), "material_id": 0}],
        "matgroup": 144, "lightset": 0, "props": 0,
        "bounds_min": tuple(min(v[i] for v in VERTS) for i in range(3)),
        "bounds_max": tuple(max(v[i] for v in VERTS) for i in range(3)),
        "bounding_radius": 10.0, "bounding_int": 0, "skinbones": 145, "remaining": b"",
    }
    skin = {
        "maps": [list(range(len(objects)))],
        "root": root,
        "objects": list(objects),
        "rotations": [_translate_inverse((0.0, 0.0, 150.0 + 10.0 * i))
                      for i in range(len(objects))],
        "global": _bone_world((0.0, 0.0, 150.0)),
        "remaining": b"",
    }
    materials = ["mtr_test"] + (["mtr_plain"] if diffuse else [])
    mat_sections = [
        dm.Section(dm.MATERIAL, 150 + i, dm.encode_material(
            {"name_hash": dm.hash64(name), "skipped": bytes(48), "items": [],
             "remaining": b""}))
        for i, name in enumerate(materials)
    ]
    sections = [
        dm.Section(dm.CUSTOM_HASHLIST, 1, dm.encode_custom_hashlist(
            {"names": ["g_test", "mtr_test", "mtr_plain", "boneA", "boneB"], "remaining": b""})),
        dm.Section(dm.SKINBONES, 145, dm.encode_skinbones(skin)),
        dm.Section(dm.GEOMETRY, 140, dm.encode_geometry(geom)),
        dm.Section(dm.TOPOLOGY, 141, dm.encode_topology(topo)),
        dm.Section(dm.PASSTHROUGH_GP, 142, dm.encode_passthroughgp(
            {"geometry": 140, "topology": 141, "remaining": b""})),
        dm.Section(dm.TOPOLOGY_IP, 143, dm.encode_topologyip({"topology": 141, "remaining": b""})),
        dm.Section(dm.MATERIAL_GROUP, 144, dm.encode_material_group(
            {"material_ids": [150 + i for i in range(len(materials))], "remaining": b""})),
        *mat_sections,
        dm.Section(dm.MODEL_DATA, 146, dm.encode_model_data(md)),
        # a second drawable's palette carries the root bone, as the suit's body does
        dm.Section(dm.SKINBONES, 147, dm.encode_skinbones(
            {"maps": [[0]], "root": root, "objects": [root],
             "rotations": [_translate_inverse((0.0, 0.0, 150.0))],
             "global": _bone_world((0.0, 0.0, 150.0)), "remaining": b""})),
    ]
    return dm.ModelFile(sections).write()


def build_texture(tmp_path: Path, colour=(200, 120, 80, 18)) -> bytes:
    """An 8x8 BC3 DDS, the shape a PAYDAY 2 `.texture` takes."""
    rgba = np.zeros((8, 8, 4), np.uint8)
    rgba[:, :] = colour
    dds = de.rgba_to_bc3_dds(rgba)
    return dds


def build_unit(tmp_path: Path, model_bytes: bytes, dds: bytes | None) -> Path:
    unit = tmp_path / "units" / "test" / "test_unit"
    unit.mkdir(parents=True)
    (unit / "test_unit.model").write_bytes(model_bytes)
    (unit / "test_unit.object").write_text(
        '<dynamic_object><graphics><graphic_group name="character">'
        '<object name="g_test" enabled="true" /></graphic_group></graphics></dynamic_object>')
    (unit / "mtr_test.material_config").write_text(
        '<materials version="3" group="test_unit">'
        '<material version="2" unique="true" name="mtr_test" '
        'render_template="generic:ALPHA_MASKED:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">'
        '<diffuse_texture file="units/test/shared/test_df"/>'
        '<bump_normal_texture file="units/test/shared/test_nm"/>'
        '<variable value="0.05" type="scalar" name="alpha_ref"/>'
        "</material></materials>")
    if dds is not None:
        shared = tmp_path / "units" / "test" / "shared"
        shared.mkdir(parents=True)
        (shared / "test_df.texture").write_bytes(dds)
        (shared / "test_nm.texture").write_bytes(dds)
    return unit


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2
    assert total == len(data)
    jlen, jtype = struct.unpack_from("<II", data, 12)
    assert jtype == 0x4E4F534A
    js = json.loads(data[20:20 + jlen])
    blen, btype = struct.unpack_from("<II", data, 20 + jlen)
    assert btype == 0x004E4942
    blob = data[20 + jlen + 8:20 + jlen + 8 + blen]
    assert blen == js["buffers"][0]["byteLength"]
    return js, blob


def accessor(js: dict, blob: bytes, index: int) -> np.ndarray:
    acc = js["accessors"][index]
    view = js["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count, width = acc["count"], WIDTH[acc["type"]]
    flat = np.frombuffer(blob, dtype=COMPONENT[acc["componentType"]],
                         count=count * width, offset=start)
    return flat.reshape(count, width) if width > 1 else flat


def convert(tmp_path: Path, model_bytes: bytes, dds: bytes | None, *extra: str):
    unit = build_unit(tmp_path, model_bytes, dds)
    out = tmp_path / "out"
    rc = mtg.main([str(unit / "test_unit.model"), "-o", str(out), "--skin", *extra])
    assert rc == 0
    glb = out / "test_unit.glb"
    assert glb.is_file()
    return glb, out


def test_positions_units_and_axes(tmp_path):
    """Diesel cm/z-up becomes glTF m/y-up: p_gltf = (x, z, -y) / 100."""
    glb, _ = convert(tmp_path, build_model(), build_texture(tmp_path))
    js, blob = read_glb(glb)
    prim = js["meshes"][0]["primitives"][0]
    pos = accessor(js, blob, prim["attributes"]["POSITION"])
    expected = np.array([[v[0] / 100, v[2] / 100, -v[1] / 100] for v in VERTS], np.float32)
    assert np.allclose(pos, expected, atol=1e-6)
    assert js["accessors"][prim["attributes"]["POSITION"]]["min"] == pytest.approx(
        expected.min(axis=0).tolist(), abs=1e-6)

    nrm = accessor(js, blob, prim["attributes"]["NORMAL"])
    assert np.allclose(nrm, [[0.0, 1.0, 0.0]] * 4, atol=1e-6)   # +Z diesel is +Y glTF


def test_uvs_are_flipped_for_a_top_left_image_origin(tmp_path):
    """glTF samples from the top-left; diesel's uv0 is bottom-up."""
    glb, _ = convert(tmp_path, build_model(), build_texture(tmp_path))
    js, blob = read_glb(glb)
    uv = accessor(js, blob, js["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"])
    assert np.allclose(uv, np.array(UV0, np.float32) * [1.0, -1.0] + [0.0, 1.0], atol=1e-6)


def test_render_atom_indices_stay_global_and_share_one_vertex_buffer(tmp_path):
    """AGENTS.md invariant 2: atoms index the drawable's geometry, so one buffer serves all."""
    glb, _ = convert(tmp_path, build_model(), build_texture(tmp_path))
    js, blob = read_glb(glb)
    prim = js["meshes"][0]["primitives"][0]
    assert list(accessor(js, blob, prim["indices"])) == INDICES
    assert len(accessor(js, blob, prim["attributes"]["POSITION"])) == len(VERTS)


def test_alpha_masked_material_keeps_its_cutout_and_its_dds(tmp_path):
    """The template's ALPHA_MASKED and alpha_ref survive; `.texture` is written as `.dds`."""
    dds = build_texture(tmp_path)
    glb, out = convert(tmp_path, build_model(), dds)
    js, blob = read_glb(glb)
    mat = js["materials"][0]
    assert mat["name"] == "mtr_test"
    assert mat["alphaMode"] == "MASK" and mat["alphaCutoff"] == pytest.approx(0.05)
    assert "baseColorTexture" in mat["pbrMetallicRoughness"]
    assert "normalTexture" in mat

    dds_file = out / "textures" / "test_df.dds"
    assert dds_file.read_bytes() == dds            # a PD2 .texture is a DDS buffer
    assert (out / "textures" / "test_nm.dds").is_file()

    image = js["images"][0]
    view = js["bufferViews"][image["bufferView"]]
    raw = blob[view["byteOffset"]:view["byteOffset"] + view["byteLength"]]
    png = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))
    assert png.shape == (8, 8, 3)
    assert np.abs(png.astype(int) - [200, 120, 80]).max() <= 8    # BC3 5:6:5 endpoints


def test_normal_map_is_unswizzled_for_gltf(tmp_path):
    """DXT5nm (X in alpha, Y in green) becomes tangent-space RGB with z rebuilt."""
    rgba = np.zeros((8, 8, 4), np.uint8)
    rgba[..., 3] = 191          # x = +0.5
    rgba[..., 1] = 64           # y = -0.5
    dds = de.rgba_to_bc3_dds(rgba)
    glb, out = convert(tmp_path, build_model(), dds)
    js, blob = read_glb(glb)
    normal_index = js["materials"][0]["normalTexture"]["index"]
    image_index = js["textures"][normal_index]["source"]
    view = js["bufferViews"][js["images"][image_index]["bufferView"]]
    raw = blob[view["byteOffset"]:view["byteOffset"] + view["byteLength"]]
    rgb = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(float) / 255.0
    assert rgb[..., 0].mean() == pytest.approx(0.75, abs=0.06)     # (x + 1) / 2
    assert rgb[..., 1].mean() == pytest.approx(0.25, abs=0.06)     # (y + 1) / 2
    assert rgb[..., 2].mean() == pytest.approx(0.5 + np.sqrt(0.5) / 2, abs=0.06)


def test_skin_binds_every_joint_to_the_rest_pose(tmp_path):
    """W @ IB must be the identity: the mesh stays in its bind pose when posed."""
    glb, _ = convert(tmp_path, build_model(), build_texture(tmp_path))
    js, blob = read_glb(glb)
    skin = js["skins"][0]
    ibm = accessor(js, blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4).astype(np.float64)
    for k, node_index in enumerate(skin["joints"]):
        world = np.array(js["nodes"][node_index]["matrix"], np.float64).reshape(4, 4)
        assert np.abs(world @ ibm[k] - np.eye(4)).max() < 1e-5

    prim = js["meshes"][0]["primitives"][0]
    joints = accessor(js, blob, prim["attributes"]["JOINTS_0"])
    weights = accessor(js, blob, prim["attributes"]["WEIGHTS_0"]).astype(np.float64)
    assert joints.max() < len(skin["joints"])
    assert np.allclose(weights.sum(axis=1), 1.0, atol=1e-5)
    assert list(weights[0]) == pytest.approx([0.75, 0.25, 0.0, 0.0], abs=1e-5)


def test_a_palette_one_bone_short_is_repaired_and_reported(tmp_path):
    """A stray BLENDINDICES value exactly one past the palette means the palette lost
    its first bone (the head packs' offset); that bone is the skin root."""
    model = build_model(
        objects=(9, 10),
        blendindices=[(1, 2, 0, 0)] * 4,
        weights=[(0.5, 0.5, 0.0)] * 4,
    )
    glb, _ = convert(tmp_path, model, build_texture(tmp_path))
    js, blob = read_glb(glb)
    assert len(js["skins"][0]["joints"]) == 3        # root 7 + 9 + 10
    warnings = " ".join(js["extras"].get("warnings", []))
    assert "one bone short" in warnings
    prim = js["meshes"][0]["primitives"][0]
    joints = accessor(js, blob, prim["attributes"]["JOINTS_0"])
    assert joints.max() < 3


def test_a_stray_index_that_is_not_a_shift_is_dropped(tmp_path):
    """Only an exact one-past-the-end shift is a repairable palette; anything else is data
    the model cannot describe, so its weight goes rather than landing on a wrong bone."""
    model = build_model(blendindices=[(0, 5, 0, 0)] * 4)
    glb, _ = convert(tmp_path, model, build_texture(tmp_path))
    js, blob = read_glb(glb)
    assert len(js["skins"][0]["joints"]) == 2
    warnings = " ".join(js["extras"].get("warnings", []))
    assert "not in the 2-bone palette" in warnings


def test_a_missing_texture_is_a_placeholder_not_a_crash(tmp_path):
    """Most of a shared unit's textures are not in a pack; the export says so."""
    glb, out = convert(tmp_path, build_model(), None)
    js, blob = read_glb(glb)
    mat = js["materials"][0]
    assert "baseColorTexture" not in mat["pbrMetallicRoughness"]
    assert len(mat["pbrMetallicRoughness"]["baseColorFactor"]) == 4
    assert not (out / "textures").exists() or not list((out / "textures").glob("*.dds"))


def test_drawable_filter_exports_only_what_was_asked_for(tmp_path, capsys):
    """`--drawable` is how a user isolates the replaced head from the other 40 drawables.

    A name the unit does not have is a mistake, not an empty export: it is reported
    and no file is left behind to be opened by accident.
    """
    unit = build_unit(tmp_path, build_model(), build_texture(tmp_path))
    out = tmp_path / "out"
    assert mtg.main([str(unit / "test_unit.model"), "-o", str(out),
                     "--drawable", "g_test"]) == 0
    js, _ = read_glb(out / "test_unit.glb")
    assert [n["name"] for n in js["nodes"]] == ["g_test"]

    out2 = tmp_path / "out2"
    assert mtg.main([str(unit / "test_unit.model"), "-o", str(out2),
                     "--drawable", "g_other"]) == 0
    assert not (out2 / "test_unit.glb").exists()
    assert "no drawable named g_other" in capsys.readouterr().err
