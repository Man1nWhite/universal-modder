"""Offline contracts for the separate native BeardLib PlayerStyle.

No PAYDAY 2, LAS, Windows, network access or loader installation is needed.
The tests deliberately do not claim to validate the model's in-game appearance.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import random
import struct
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/pd2-port"))
import build_outfit_beardlib as builder  # noqa: E402

base, rp, dmodel = builder.base, builder.rp, builder.dmodel
PREFIX = builder.MOD_NAME + "/"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def source_assets():
    return base.load_source(builder.DEFAULT_SOURCE)


@pytest.fixture(scope="module")
def pack_path(tmp_path_factory):
    originals = (*builder.PROTECTED_ARCHIVES, ROOT / "2b.rar")
    before = {p: sha256(p) for p in originals}
    path = tmp_path_factory.mktemp("beardlib-outfit") / "lawson_outfit_BeardLib.zip"
    assert builder.build_pack(out_zip=path) == path
    assert {p: sha256(p) for p in originals} == before
    return path


@pytest.fixture(scope="module")
def pack(pack_path):
    with ZipFile(pack_path) as archive:
        yield archive


def read_asset(pack, path, extension):
    return pack.read(f"{PREFIX}assets/{path}.{extension}")


def drawable_data(blob, name):
    sections, _, _, _, by_id = rp.parse_model_bytes(blob)
    md = base._model_by_name(sections, name).obj
    gp = by_id[md.passthrough_id].obj
    return md, by_id[gp.geometry_id].obj, by_id[gp.topology_id].obj, by_id[md.skinbones_id].obj, sections, by_id


@pytest.mark.parametrize("first_person", [False, True], ids=["third-person", "first-person"])
def test_models_have_only_their_enabled_drawables_and_valid_references(pack, first_person):
    path = builder.FPS_PATH if first_person else builder.TPP_PATH
    blob = read_asset(pack, path, "model")
    builder.validate_model(blob)
    assert rp.validate_model_skinning(blob, strict_layout=True) == []
    sections, legacy, version, filesize, _ = rp.parse_model_bytes(blob)
    assert not legacy and version == 1 and filesize == len(blob)
    assert [s.id for s in sections] == list(range(1, len(sections) + 1))
    drawables = [s for s in sections if s.tag == "model_data"]
    names = builder.FPS_DRAWABLES if first_person else builder.TPP_DRAWABLES
    assert {s.obj.name_hash for s in drawables} == {dmodel.hash_str(n) for n in names}
    assert all(s.obj.version == 3 for s in drawables)


def test_zip_has_one_safe_root_and_complete_private_build_metadata(pack):
    names = pack.namelist()
    assert len(names) == len(set(names)) == 36
    assert pack.testzip() is None
    for name in names:
        assert name.startswith(PREFIX) and "\\" not in name
        assert not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
    info = json.loads(pack.read(PREFIX + "BUILD_INFO.json"))
    assert info["runtime_verified"] is False
    assert info["style_id"] == "lawson_beardlib"
    assert info["source_sha256"] == sha256(builder.DEFAULT_SOURCE)
    assert info["icon_sha256"] == sha256(builder.DEFAULT_ICON)
    assert info["beardlib_api_ref"] == builder.BEARDLIB_REF
    assert set(info["payload_sha256"]) == {n.removeprefix(PREFIX) for n in names} - {"BUILD_INFO.json"}
    for name, digest in info["payload_sha256"].items():
        assert hashlib.sha256(pack.read(PREFIX + name)).hexdigest() == digest


def test_addfiles_registers_every_asset_once_in_dependency_order(pack):
    root = ET.fromstring(pack.read(PREFIX + "main.xml"))
    assert root.tag == "table"
    add = root.find("AddFiles")
    assert add.get("directory") == "assets"
    registered = [f"{PREFIX}assets/{node.get('path')}.{node.tag}" for node in add]
    assert len(registered) == len(set(registered))
    assert set(registered) == {n for n in pack.namelist() if n.startswith(PREFIX + "assets/")}
    order = {"texture": 0, "model": 1, "object": 2, "material_config": 3, "unit": 4}
    assert [order[n.tag] for n in add] == sorted(order[n.tag] for n in add)
    for node in add:
        assert not node.get("path").endswith("." + node.tag)
    assert f"{PREFIX}assets/{root.get('image')}.texture" in registered


def test_native_style_and_body_replacement_schema(pack):
    root = ET.fromstring(pack.read(PREFIX + "main.xml"))
    style = root.find("PlayerStyle")
    assert style.get("id") == style.get("global_value") == style.get("texture_bundle_folder") == builder.STYLE_ID
    assert style.get("unit") == builder.FPS_PATH
    assert style.get("third_unit") == builder.TPP_PATH
    assert style.get("default_gloves") == "false" and style.get("exclude_glove_adapter") == "true"
    # Use global native fallback, not an incomplete hard-coded list of heisters.
    assert style.find("characters") is None
    for field in ("body_replacement", "third_body_replacement"):
        replacement = style.find(field)
        assert replacement.attrib == {p: "true" for p in builder.REPLACEMENTS}
        assert len(replacement) == 0  # Attributes are boolean fields, not nested tables.
        assert "mask" not in replacement.attrib
    assert {n.tag for n in root} == {"AddFiles", "Localization", "GlobalValue", "PlayerStyle"}
    assert root.find("GlobalValue").get("dlc") == "false"
    # No updater, Lua hooks or LAS registration code is shipped.
    assert not any(n.endswith((".lua", "mod.txt", ".dll", ".exe")) for n in pack.namelist())


def test_ids_and_asset_paths_do_not_collide_with_legacy_pack(pack):
    with ZipFile(ROOT / "dist/lawson_outfit.zip") as old:
        las_info = json.loads(old.read("Lawson_LAS/BUILD_INFO.json"))
        assert las_info["variant"] == "legendary-armour-skins"
        assert las_info["las4_style_id"] != builder.STYLE_ID
        old_assets = {n.removeprefix("Lawson_LAS/assets/") for n in old.namelist() if "/assets/" in n}
    assets = {n.removeprefix(PREFIX + "assets/") for n in pack.namelist() if "/assets/" in n}
    assert not assets & old_assets
    assert all(n.startswith((builder.UNIT_DIR + "/", f"guis/dlcs/{builder.STYLE_ID}/")) for n in assets)
    manifest = pack.read(PREFIX + "main.xml").decode()
    assert "wardrobe_mod" not in manifest and "LegendaryArmours" not in manifest
    assert "units/payday2/" not in manifest


def test_standard_json_localization_covers_native_keys(pack):
    root = ET.fromstring(pack.read(PREFIX + "main.xml"))
    localization = root.find("Localization")
    assert localization.get("default_language") == "english"
    entry = localization.find("localization")
    assert entry.get("language") == "english"
    data = json.loads(pack.read(f"{PREFIX}{localization.get('directory')}/{entry.get('file')}"))
    assert set(data) == {
        f"bm_suit_{builder.STYLE_ID}", f"bm_suit_{builder.STYLE_ID}_desc",
        f"bm_global_value_{builder.STYLE_ID}", f"menu_l_global_value_{builder.STYLE_ID}",
    }
    assert data[f"bm_suit_{builder.STYLE_ID}"] == "Miranda Lawson (BeardLib)"


@pytest.mark.parametrize("path", [builder.TPP_PATH, builder.FPS_PATH])
def test_sidecars_use_engine_schema_and_real_culling_geometry(pack, path):
    model = read_asset(pack, path, "model")
    sections, _, _, _, by_id = rp.parse_model_bytes(model)
    hashes = {getattr(s.obj, "name_hash", None) for s in sections}
    unit = ET.fromstring(read_asset(pack, path, "unit"))
    assert unit.tag == "unit" and unit.get("slot") == "1"
    assert unit.find("object").get("file") == path
    extensions = {n.get("name"): n.get("class") for n in unit.find("extensions")}
    assert extensions["unit_data"] == "ScriptUnitData"
    assert ("contour" in extensions) == (path == builder.TPP_PATH)
    obj = ET.fromstring(read_asset(pack, path, "object"))
    assert obj.tag == "dynamic_object"
    assert obj.find("diesel").get("materials") == path
    assert dmodel.hash_str(obj.find("diesel").get("orientation_object")) in hashes
    group = obj.find("graphics/graphic_group")
    assert group.get("culling_object") == "g_body"
    assert {dmodel.hash_str(n.get("name")) for n in group} == {
        s.obj.name_hash for s in sections if s.tag == "model_data"
    }
    body = base._model_by_name(sections, "g_body").obj
    for sec in sections:
        if sec.tag == "model_data":
            geo = by_id[by_id[sec.obj.passthrough_id].obj.geometry_id].obj
            for point in geo.positions:
                assert all(lo - 1e-4 <= x <= hi + 1e-4 for x, lo, hi in zip(point, body.bounds_min, body.bounds_max))
    assert all(n.get("enabled") == "true" for n in group)
    assert obj.find("bodies") is None  # No colliding character body is spawned as an outfit.


@pytest.mark.parametrize("path", [builder.TPP_PATH, builder.FPS_PATH])
def test_material_coverage_is_model_to_config_as_well_as_config_to_model(pack, path):
    blob = read_asset(pack, path, "model")
    materials = ET.fromstring(read_asset(pack, path, "material_config"))
    assert {dmodel.hash_str(m.get("name")) for m in materials} == builder.material_hashes(blob)
    assert len(materials) == len({m.get("name") for m in materials})
    if path == builder.TPP_PATH:
        shadow = next(m for m in materials if m.get("name") == "shadow_caster")
        assert shadow.get("render_template") == "shadow_caster_only:SKINNED_1WEIGHT"
    else:
        assert all(m.get("render_template") == base.BASIC_FPS for m in materials)
        assert not any(v.get("name", "").startswith("contour_") for v in materials.iter("variable"))
    for node in materials.iter():
        resource = node.get("file")
        if resource and not resource.startswith("environments/cubemaps/"):
            assert resource.startswith(builder.TEX_DIR + "/")
            assert f"{PREFIX}assets/{resource}.texture" in pack.namelist()


def test_shadow_definition_cannot_silently_be_dropped(source_assets, pack):
    model, source, textures = source_assets
    root = ET.fromstring(source)
    for material in list(root):
        if material.get("name") == "shadow_caster":
            root.remove(material)
    needed = builder.material_hashes(read_asset(pack, builder.TPP_PATH, "model"))
    with pytest.raises(ValueError, match="Missing source material"):
        builder.material_config(ET.tostring(root), needed, textures.copy(), first_person=False)


def test_tpp_geometry_topology_and_shared_skeleton_are_preserved(source_assets, pack):
    original = source_assets[0]
    src_sections, _, _, _, src_by = rp.parse_model_bytes(original)
    for path in (builder.TPP_PATH, builder.FPS_PATH):
        sections, _, _, _, _ = rp.parse_model_bytes(read_asset(pack, path, "model"))
        skeleton = {s.obj.name_hash: (s.obj.matrix, s.obj.pos) for s in sections if s.tag == "object3D"}
        assert skeleton == {s.obj.name_hash: (s.obj.matrix, s.obj.pos) for s in src_sections if s.tag == "object3D"}
    third = read_asset(pack, builder.TPP_PATH, "model")
    dst_sections, _, _, _, dst_by = rp.parse_model_bytes(third)
    for name in builder.TPP_DRAWABLES:
        src_md = base._model_by_name(src_sections, name).obj
        dst_md = base._model_by_name(dst_sections, name).obj
        src_gp, dst_gp = src_by[src_md.passthrough_id].obj, dst_by[dst_md.passthrough_id].obj
        for role in ("geometry_id", "topology_id"):
            a, b = src_by[getattr(src_gp, role)], dst_by[getattr(dst_gp, role)]
            assert original[a.start:a.end] == third[b.start:b.end], (name, role)


def test_first_person_uses_the_stable_arm_subset_and_original_hands(source_assets, pack):
    md, geo, topo, skin, sections, _ = drawable_data(source_assets[0], "g_body")
    selected = builder.select_arm_verts(md, geo, topo, skin, base._arm_bone_ids(sections))
    assert len(selected) == 1998
    fps = read_asset(pack, builder.FPS_PATH, "model")
    new_geo = drawable_data(fps, "g_body")[1]
    assert new_geo.positions == [geo.positions[i] for i in sorted(selected)]
    old_hands = drawable_data(source_assets[0], "g_hands")[1]
    hands = drawable_data(fps, "g_hands")[1]
    assert hands.positions == old_hands.positions and hands.joints == old_hands.joints
    assert len(new_geo.positions) < len(geo.positions)


def test_arm_selector_is_exactly_one_ring_not_a_face_order_flood_fill():
    geo = SimpleNamespace(joints=[(0,), (1,), (1,), (1,), (1,)], weights4=lambda _: (1.0,))
    skin = SimpleNamespace(bone_mappings=[[0, 1]], object_ids=[11, 22])
    md = SimpleNamespace(render_atoms=[{"base_vertex": 0, "geo_len": 5}])
    faces = [(0, 1, 2), (1, 2, 3), (2, 3, 4)]
    for order in (faces, faces[::-1]):
        assert builder.select_arm_verts(md, geo, SimpleNamespace(faces=order), skin, {11}) == {0, 1, 2}


@pytest.mark.parametrize("ordering", ["reverse", "shuffle"])
def test_real_arm_selection_does_not_depend_on_face_order(source_assets, ordering):
    md, geo, topo, skin, sections, _ = drawable_data(source_assets[0], "g_body")
    arm_ids = base._arm_bone_ids(sections)
    expected = builder.select_arm_verts(md, geo, topo, skin, arm_ids)
    faces = list(topo.faces)
    if ordering == "reverse":
        faces.reverse()
    else:
        random.Random(1825).shuffle(faces)
    assert builder.select_arm_verts(md, geo, SimpleNamespace(faces=faces), skin, arm_ids) == expected


@pytest.mark.parametrize("damage", ["vertex", "material", "atom_vertices", "atom_indices"])
def test_new_validator_rejects_corrupt_render_references(pack, damage):
    blob = bytearray(read_asset(pack, builder.FPS_PATH, "model"))
    sections, _, _, _, by_id = rp.parse_model_bytes(blob)
    sec = base._model_by_name(sections, "g_body")
    gp = by_id[sec.obj.passthrough_id].obj
    if damage == "vertex":
        struct.pack_into("<H", blob, by_id[gp.topology_id].start + 8, 65535)
        message = "vertex reference outside geometry"
    else:
        atom_off = sec.start + len(base._serialize_object_prefix(sec.obj)) + 16
        offset, value, message = {
            "material": (16, 999, "material outside material group"),
            "atom_vertices": (0, 65535, "vertex range outside geometry"),
            "atom_indices": (8, 999999, "index range outside topology"),
        }[damage]
        struct.pack_into("<I", blob, atom_off + offset, value)
    with pytest.raises(ValueError, match=message):
        builder.validate_model(bytes(blob))


def test_index_count_is_not_mistaken_for_uint16_vertex_limit(pack):
    blob = read_asset(pack, builder.FPS_PATH, "model")
    sections, _, _, _, by_id = rp.parse_model_bytes(blob)
    body = base._model_by_name(sections, "g_body")
    topo_sec = by_id[by_id[body.obj.passthrough_id].obj.topology_id]
    topo = topo_sec.obj
    extra_triangles = 22000
    # Repeat a valid triangle; actual vertex references remain well below 65,535.
    replacement = struct.pack("<II", topo.primitive, len(topo.faces) * 3 + extra_triangles * 3)
    replacement += struct.pack("<3H", *topo.faces[0]) * extra_triangles
    replacement += blob[topo_sec.start + 8:topo_sec.end]
    md = bytearray(blob[body.start:body.end])
    off = len(base._serialize_object_prefix(body.obj)) + 16
    struct.pack_into("<I", md, off + 4, body.obj.render_atoms[0]["tri_count"] + extra_triangles)
    for i, atom in enumerate(body.obj.render_atoms[1:], 1):
        struct.pack_into("<I", md, off + i * 20 + 8, atom["base_index"] + extra_triangles * 3)
    data = bytearray(blob[:16])
    for sec in sections:
        payload = replacement if sec.id == topo_sec.id else md if sec.id == body.id else blob[sec.start:sec.end]
        data += struct.pack("<III", sec.type, sec.id, len(payload)) + payload
    struct.pack_into("<I", data, 8, len(data))
    builder.validate_model(bytes(data))


def test_textures_keep_all_original_payloads_and_have_complete_mips(source_assets, pack):
    for name, original in source_assets[2].items():
        assert pack.read(f"{PREFIX}assets/{builder.TEX_DIR}/{name}") == original
    textures = [n for n in pack.namelist() if n.startswith(f"{PREFIX}assets/{builder.TEX_DIR}/")]
    assert len(textures) == 22  # 19 supplied + 2 alpha-derived opacity maps + a flat normal.
    for name in textures:
        blob = pack.read(name)
        size, mips, _ = builder.dds.dds_mip0_slice(blob)
        assert mips == size.bit_length()
        assert len(blob) == 128 + sum(max(1, (size >> level) // 4) ** 2 * 16 for level in range(mips))
        assert struct.unpack_from("<I", blob, 8)[0] == 0x000A1007
        assert struct.unpack_from("<I", blob, 108)[0] == 0x00401008
        with Image.open(io.BytesIO(blob)) as image:
            assert image.convert("RGBA").size == (size, size)
    icon = read_asset(pack, builder.ICON_PATH, "texture")
    assert icon[84:88] == b"DXT5"
    assert struct.unpack_from("<II", icon, 12) == (128, 128)
    assert struct.unpack_from("<I", icon, 28)[0] == 0


@pytest.mark.parametrize("source,target", [
    ("miranda_hair_d", "lawson_hair_op"),
    ("hmf_hed_promiranda_lashes", "lawson_lashes_op"),
])
def test_opacity_maps_use_supplied_alpha_not_a_vanilla_character_map(pack, source, target):
    with Image.open(io.BytesIO(read_asset(pack, builder.TEX_DIR + "/" + source, "texture"))) as image:
        alpha = np.array(image.convert("RGBA").getchannel("A"), dtype=np.int16)
    with Image.open(io.BytesIO(read_asset(pack, builder.TEX_DIR + "/" + target, "texture"))) as image:
        opacity = np.array(image.convert("RGBA"), dtype=np.int16)
    assert alpha.min() == 0 and alpha.max() == 255
    assert np.abs(opacity[:, :, 0] - alpha).mean() < 12  # Lossy BC3 RGB encoding.
    assert np.all(opacity[:, :, 3] == 255)  # Opacity shader samples grayscale, not alpha.


def test_rebuild_is_byte_deterministic_and_cli_defaults_work_from_any_directory(pack_path, tmp_path):
    out = tmp_path / "lawson_outfit_BeardLib.zip"
    result = subprocess.run(
        [sys.executable, builder.__file__, "--out", str(out)], cwd=tmp_path,
        capture_output=True, text=True, check=True,
    )
    assert "game test required" in result.stdout
    assert sha256(out) == sha256(pack_path)


@pytest.mark.parametrize("output", builder.PROTECTED_ARCHIVES + (builder.DEFAULT_ICON,))
def test_original_archives_and_inputs_cannot_be_overwritten(output):
    before = sha256(output)
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        builder.build_pack(out_zip=output)
    assert sha256(output) == before


def test_failed_zip_write_preserves_existing_output_and_cleans_temporary_files(monkeypatch, tmp_path):
    output = tmp_path / "existing.zip"
    output.write_bytes(b"previous output")

    def fail(*_args, **_kwargs):
        raise OSError("simulated disk write failure")

    monkeypatch.setattr(ZipFile, "writestr", fail)
    with pytest.raises(OSError, match="simulated disk write failure"):
        builder.build_pack(out_zip=output)
    assert output.read_bytes() == b"previous output"
    assert list(tmp_path.iterdir()) == [output]


def test_install_and_runtime_limits_are_bundled(pack):
    readme = pack.read(PREFIX + "README.txt").decode()
    assert "PAYDAY 2/assets/mod_overrides/Lawson_Outfit_BeardLib/main.xml" in readme
    assert "NOT tested in PAYDAY 2" in readme
    assert "does NOT hide the separate equipped mask" in readme
    assert "use Default gloves" in readme
    assert "Equip a vanilla outfit before removing" in readme
    credits = pack.read(PREFIX + "CREDITS.txt").decode()
    assert "redistribution" in credits and "2b.rar example is not copied" in credits
