"""Offline regressions for the repaired Lawson LAS add-on.

The old package kept undefined drawable materials, used an empty culling
locator, and registered a plain PlayerStyle despite its LAS name. These tests
exercise those resource contracts, not native game loading or rendering.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import struct
import sys
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/pd2-port"))
import build_outfit as builder  # noqa: E402

dmodel, skin_repair = builder.dmodel, builder.rp
PREFIX = builder.MOD_NAME + "/"
TEX_DIR = f"{PREFIX}assets/{builder.TEX_BASE}"
UNIT_DIR = f"{PREFIX}assets/{builder.UNIT_BASE}"
FPS_DIR = f"{PREFIX}assets/{builder.UNIT_FPS}"
ICON = f"{PREFIX}assets/{builder.ICON_PATH}.texture"


@pytest.fixture(scope="module")
def source_assets():
    return builder.load_source(builder.DEFAULT_SOURCE)


@pytest.fixture(scope="module")
def pack_path(tmp_path_factory):
    out = tmp_path_factory.mktemp("las-outfit") / "lawson_outfit.zip"
    info = builder.build_pack(out_zip=out)
    assert info["runtime_verified"] is False
    return out


@pytest.fixture(scope="module")
def pack(pack_path):
    with ZipFile(pack_path) as archive:
        yield archive


def model_asset(pack, first_person=False):
    path = builder.UNIT_FPS if first_person else builder.UNIT_BASE
    return pack.read(f"{PREFIX}assets/{path}.model")


def drawable(blob, name):
    sections, _, _, _, by = skin_repair.parse_model_bytes(blob)
    md = builder._model_by_name(sections, name).obj
    gp = by[md.passthrough_id].obj
    return md, by[gp.geometry_id].obj, by[gp.topology_id].obj, by[md.skinbones_id].obj, sections, by


def test_pack_layout_integrity_and_provenance(pack):
    names = pack.namelist()
    assert len(names) == len(set(names)) == 35
    assert pack.testzip() is None
    for name in names:
        assert name.startswith(PREFIX)
        assert "\\" not in name and not PurePosixPath(name).is_absolute()
        assert ".." not in PurePosixPath(name).parts
    assert len([n for n in names if n.startswith(TEX_DIR + "/")]) == 19
    info = json.loads(pack.read(PREFIX + "BUILD_INFO.json"))
    assert info["runtime_verified"] is False
    assert info["version"] == builder.VERSION
    assert info["variant"] == "legendary-armour-skins"
    assert info["registry_key"] == "lawson" and info["las4_style_id"] == "las_lawson"
    assert info["source_sha256"] == hashlib.sha256(builder.DEFAULT_SOURCE.read_bytes()).hexdigest()
    assert info["beardlib_api_ref"] == builder.BEARDLIB_REF
    assert info["las_api_ref"] == builder.LAS_REF
    assert set(info["payload_sha256"]) == {n.removeprefix(PREFIX) for n in names} - {"BUILD_INFO.json"}
    for name, digest in info["payload_sha256"].items():
        assert hashlib.sha256(pack.read(PREFIX + name)).hexdigest() == digest
    assert "NOT a re-rig" in info["repair_scope"]


def test_manifest_is_a_real_las_hook_not_a_native_style(pack):
    root = ET.fromstring(pack.read(PREFIX + "main.xml"))
    assert root.tag == "table" and root.get("version") == builder.VERSION
    assert root.find("PlayerStyle") is None
    assert root.find("GlobalValue") is None
    assert root.find("AssetUpdates") is None
    hooks = root.find("Hooks")
    assert hooks.get("directory") == "hooks"
    assert len(hooks) == 1
    hook = hooks.find("hook")
    assert hook.get("source_file") == "lib/tweak_data/armorskinstweakdata"
    lua = pack.read(PREFIX + hooks.get("directory") + "/" + hook.get("file")).decode()
    assert "LegendaryArmours = LegendaryArmours or {}" in lua
    assert "LegendaryArmours.lawson = {" in lua
    for key in ("hide_mask", "hide_armor", "replace_all", "fps_hide_armor", "fps_replace_body"):
        assert f"{key} = true" in lua
    assert f'unit = "{builder.UNIT_BASE}"' in lua
    assert f'fps_unit = "{builder.UNIT_FPS}"' in lua
    # Registration only: let LAS own the visual hooks; do not replace game methods.
    assert "Hooks:" not in lua and "function " not in lua and "dofile" not in lua
    assert set(n for n in pack.namelist() if n.endswith(".lua")) == {PREFIX + "hooks/register_lawson.lua"}


def test_las_hook_executes_idempotently_and_preserves_other_skins(pack):
    lua51 = pytest.importorskip("lupa.lua51", reason="Optional Lua 5.1 contract execution")
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    lua.execute("LegendaryArmours = { other_skin = { unit = 'keep_me' } }")
    code = pack.read(PREFIX + "hooks/register_lawson.lua").decode()
    lua.execute(code)
    lua.execute(code)
    table = lua.globals().LegendaryArmours
    assert set(table.keys()) == {"other_skin", "lawson"}
    assert table.other_skin.unit == "keep_me"
    entry = table.lawson
    assert entry.unit == builder.UNIT_BASE and entry.fps_unit == builder.UNIT_FPS
    assert entry.category == builder.CATEGORY
    for key in ("hide_mask", "hide_armor", "replace_all", "fps_hide_armor", "fps_replace_body"):
        assert entry[key] is True


def test_all_registered_resources_exist_and_use_default_physics(pack):
    root = ET.fromstring(pack.read(PREFIX + "main.xml"))
    add = root.find("AddFiles")
    assert add.get("directory") == "assets"
    registered = set()
    units = []
    for entry in add:
        path = entry.get("path")
        assert not path.endswith((".texture", ".model", ".unit"))
        if entry.tag == "texture":
            targets = [f"{PREFIX}assets/{path}.texture"]
        else:
            assert entry.tag == "unit_mat"
            # BeardLib's unit_mat shortcut adds its own built-in default physics.
            assert entry.get("auto_cp") == "true"
            units.append(path)
            targets = [f"{PREFIX}assets/{path}.{ext}"
                       for ext in ("unit", "model", "object", "material_config")]
        assert not registered.intersection(targets)
        registered.update(targets)
    assert registered == {n for n in pack.namelist() if n.startswith(PREFIX + "assets/")}
    assert set(units) == {builder.UNIT_BASE, builder.UNIT_FPS}
    assert f"{PREFIX}assets/{root.get('image')}.texture" in registered
    assert not any(n.endswith(".cooked_physics") for n in pack.namelist())


@pytest.mark.parametrize("first_person", [False, True], ids=["TPP", "FPS"])
def test_models_prune_every_unused_drawable_chain(pack, first_person):
    blob = model_asset(pack, first_person)
    builder.validate_model(blob)
    assert skin_repair.validate_model_skinning(blob, strict_layout=True) == []
    sections, legacy, version, size, by = skin_repair.parse_model_bytes(blob)
    assert not legacy and version == 1 and size == len(blob)
    assert [s.id for s in sections] == list(range(1, len(sections) + 1))
    drawables = [s for s in sections if s.tag == "model_data"]
    wanted = builder.FPS_DRAWABLES if first_person else builder.TPP_DRAWABLES
    assert {s.obj.name_hash for s in drawables} == {dmodel.hash_str(n) for n in wanted}
    assert all(s.obj.version == 3 for s in drawables)
    assert all(a["tri_count"] > 0 for s in drawables for a in s.obj.render_atoms)
    assert not any(s.obj.name_hash == dmodel.hash_str("co_box")
                   for s in sections if s.tag == "object3D")
    chains = {sid for sec in drawables for sid in builder._chain_ids(sec.obj, by)}
    for sec in sections:
        if sec.tag in {"geometry", "topology", "passthroughGP", "topologyIP", "skinbones"}:
            assert sec.id in chains, (sec.tag, sec.id)


@pytest.mark.parametrize("first_person", [False, True], ids=["TPP", "FPS"])
def test_unit_objects_cull_against_real_bounded_geometry(pack, first_person):
    path = builder.UNIT_FPS if first_person else builder.UNIT_BASE
    blob = model_asset(pack, first_person)
    sections, _, _, _, by = skin_repair.parse_model_bytes(blob)
    models = {s.obj.name_hash: s.obj for s in sections if s.tag == "model_data"}
    root = ET.fromstring(pack.read(f"{PREFIX}assets/{path}.object"))
    assert root.tag == "dynamic_object"
    assert root.find("diesel").get("materials") == path
    assert root.find("diesel").get("orientation_object") == "root_point"
    group = root.find("graphics/graphic_group")
    assert group.get("culling_object") == "g_body"
    listed = {dmodel.hash_str(o.get("name")) for o in group.findall("object")}
    assert listed == set(models)
    assert all(o.get("enabled") == "true" for o in group.findall("object"))
    body = models[dmodel.hash_str("g_body")]
    assert by[by[body.passthrough_id].obj.geometry_id].obj.vert_count > 0
    for md in models.values():
        geo = by[by[md.passthrough_id].obj.geometry_id].obj
        for point in geo.positions:
            assert all(lo <= v <= hi for lo, v, hi in zip(body.bounds_min, point, body.bounds_max))
    unit = ET.fromstring(pack.read(f"{PREFIX}assets/{path}.unit"))
    assert unit.tag == "unit" and unit.find("object").get("file") == path
    assert unit.find("extensions/extension[@name='unit_data']").get("class") == "ScriptUnitData"


@pytest.mark.parametrize("first_person", [False, True], ids=["TPP", "FPS"])
def test_every_model_material_has_a_config_definition(pack, first_person):
    path = builder.UNIT_FPS if first_person else builder.UNIT_BASE
    blob = model_asset(pack, first_person)
    xml = ET.fromstring(pack.read(f"{PREFIX}assets/{path}.material_config"))
    definitions = {dmodel.hash_str(m.get("name")): m for m in xml.findall("material")}
    assert set(definitions) == builder.material_hashes(blob)
    sections, *_ = skin_repair.parse_model_bytes(blob)
    # Even material records not used by a render atom must not leak in from source.
    assert set(definitions) == {s.obj.name_hash for s in sections if s.tag == "material"}
    if not first_person:
        shadow = definitions[dmodel.hash_str("shadow_caster")]
        assert shadow.get("render_template") == "shadow_caster_only:SKINNED_1WEIGHT"
    else:
        for material in definitions.values():
            assert material.get("render_template") == builder.BASIC_FPS
            assert all(not v.get("name", "").startswith("contour_") for v in material.findall("variable"))
    for material in definitions.values():
        for node in material.iter():
            path = node.get("file", "")
            assert not path.startswith(builder.OLD_TEX_DIR)
            if path.startswith(builder.TEX_BASE + "/"):
                assert f"{PREFIX}assets/{path}.texture" in pack.namelist()


def test_missing_shadow_material_is_a_build_error(source_assets):
    original = ET.fromstring(source_assets[1])
    for material in list(original):
        if material.get("name") == "shadow_caster":
            original.remove(material)
    with pytest.raises(ValueError, match="Missing source material"):
        builder.material_config(ET.tostring(original), {dmodel.hash_str("shadow_caster")}, first_person=False)


def test_tpp_geometry_and_skeleton_are_not_claimed_as_a_new_rig(source_assets, pack):
    source = source_assets[0]
    target = model_asset(pack)
    old_sections, _, _, _, old_by = skin_repair.parse_model_bytes(source)
    new_sections, _, _, _, new_by = skin_repair.parse_model_bytes(target)
    for blob in (target, model_asset(pack, True)):
        sections, *_ = skin_repair.parse_model_bytes(blob)
        assert {s.obj.name_hash: (s.obj.matrix, s.obj.pos) for s in sections if s.tag == "object3D"} == {
            s.obj.name_hash: (s.obj.matrix, s.obj.pos) for s in old_sections if s.tag == "object3D"
        }
    for name in builder.TPP_DRAWABLES:
        old = builder._model_by_name(old_sections, name).obj
        new = builder._model_by_name(new_sections, name).obj
        for key in ("geometry_id", "topology_id"):
            a = old_by[getattr(old_by[old.passthrough_id].obj, key)]
            b = new_by[getattr(new_by[new.passthrough_id].obj, key)]
            assert source[a.start:a.end] == target[b.start:b.end], (name, key)
        a, b = old_by[old.skinbones_id].obj, new_by[new.skinbones_id].obj
        assert a.rotations == b.rotations and a.global_skin_transform == b.global_skin_transform
        assert [old_by[i].obj.name_hash for i in a.object_ids] == [new_by[i].obj.name_hash for i in b.object_ids]


def test_fps_keeps_stable_arm_subset_and_original_hands(source_assets, pack):
    md, geo, topo, skin, sections, _ = drawable(source_assets[0], "g_body")
    selected = builder.select_arm_verts(md, geo, topo, skin, builder._arm_bone_ids(sections))
    assert len(selected) == 1998
    fps = model_asset(pack, True)
    assert drawable(fps, "g_body")[1].positions == [geo.positions[i] for i in sorted(selected)]
    assert drawable(fps, "g_hands")[1].positions == drawable(source_assets[0], "g_hands")[1].positions


def test_arm_selector_does_not_flood_fill_a_chain():
    geo = SimpleNamespace(joints=[(0,), (1,), (1,), (1,), (1,)], weights4=lambda _: (1.0,))
    skin = SimpleNamespace(bone_mappings=[[0, 1]], object_ids=[11, 22])
    md = SimpleNamespace(render_atoms=[{"base_vertex": 0, "geo_len": 5}])
    faces = [(0, 1, 2), (1, 2, 3), (2, 3, 4)]
    for order in (faces, faces[::-1]):
        assert builder.select_arm_verts(md, geo, SimpleNamespace(faces=order), skin, {11}) == {0, 1, 2}


@pytest.mark.parametrize("ordering", ["reverse", "shuffle"])
def test_real_arm_cut_is_independent_of_face_order(source_assets, ordering):
    md, geo, topo, skin, sections, _ = drawable(source_assets[0], "g_body")
    arm_ids = builder._arm_bone_ids(sections)
    expected = builder.select_arm_verts(md, geo, topo, skin, arm_ids)
    faces = list(topo.faces)
    if ordering == "reverse":
        faces.reverse()
    else:
        random.Random(1825).shuffle(faces)
    assert builder.select_arm_verts(md, geo, SimpleNamespace(faces=faces), skin, arm_ids) == expected


def test_standard_json_and_both_icon_routes(pack):
    root = ET.fromstring(pack.read(PREFIX + "main.xml"))
    loc = root.find("Localization")
    assert loc.get("default_language") == "english"
    entry = loc.find("localization")
    data = json.loads(pack.read(f"{PREFIX}{loc.get('directory')}/{entry.get('file')}"))
    assert {f"bm_menu_{builder.CATEGORY}_armor_skins", "bm_askn_lawson", "bm_askn_lawson_desc"} == set(data)
    icon = pack.read(ICON)
    assert icon == pack.read(f"{PREFIX}assets/{builder.STYLE_ICON_PATH}.texture")
    assert icon[:4] == b"DDS " and icon[84:88] == b"DXT5"
    assert struct.unpack_from("<II", icon, 12) == (128, 128)
    assert struct.unpack_from("<I", icon, 28)[0] == 0


def test_all_19_source_textures_are_unchanged_complete_pyramids(source_assets, pack):
    for name, original in source_assets[2].items():
        blob = pack.read(f"{TEX_DIR}/{name}")
        assert blob == original
        assert struct.unpack_from("<I", blob, 8)[0] == 0x000A1007
        assert struct.unpack_from("<I", blob, 28)[0] > 1
        assert struct.unpack_from("<I", blob, 108)[0] == 0x00401008


@pytest.mark.parametrize("name", ["bonnie", "clover", "sydney", "outfit_BeardLib"])
def test_builder_refuses_to_overwrite_other_distribution_packs(name):
    path = ROOT / "dist" / f"lawson_{name}.zip"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        builder.build_pack(out_zip=path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("input_name", ["source", "icon", "reference"])
def test_builder_refuses_to_overwrite_its_inputs(input_name):
    path = {"source": builder.DEFAULT_SOURCE, "icon": builder.DEFAULT_ICON, "reference": ROOT / "2b.rar"}[input_name]
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        builder.build_pack(out_zip=path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("root", ["", "..", "../escape", "/absolute", "nested/path", "x\\other", "name:stream"])
def test_unsafe_custom_zip_roots_are_rejected(tmp_path, root):
    with pytest.raises(ValueError, match="safe top-level folder"):
        builder.build_pack(out_zip=tmp_path / "out.zip", root_folder=root)
    assert not list(tmp_path.iterdir())


def test_validation_failure_does_not_truncate_existing_output(tmp_path, monkeypatch):
    out = tmp_path / "out.zip"
    out.write_bytes(b"keep existing output")
    def fail(*args, **kwargs):
        raise ValueError("synthetic bad model")
    monkeypatch.setattr(builder, "prepare_model", fail)
    with pytest.raises(ValueError, match="synthetic bad model"):
        builder.build_pack(out_zip=out)
    assert out.read_bytes() == b"keep existing output"
    assert list(tmp_path.iterdir()) == [out]


def test_atomic_replace_failure_leaves_no_partial_archive(tmp_path, monkeypatch):
    out = tmp_path / "out.zip"
    out.write_bytes(b"keep existing output")
    def fail(*args, **kwargs):
        raise OSError("synthetic replace failure")
    monkeypatch.setattr(builder.os, "replace", fail)
    with pytest.raises(OSError, match="synthetic replace failure"):
        builder.build_pack(out_zip=out)
    assert out.read_bytes() == b"keep existing output"
    assert list(tmp_path.iterdir()) == [out]


def test_shipped_zip_is_current_and_deterministic(pack_path):
    assert (ROOT / "dist/lawson_outfit.zip").read_bytes() == pack_path.read_bytes()


def test_beardlib_archive_is_present_in_dist_and_still_a_separate_variant():
    path = ROOT / "dist/lawson_outfit_BeardLib.zip"
    assert path.is_file()
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        info = json.loads(archive.read("Lawson_Outfit_BeardLib/BUILD_INFO.json"))
        assert info["style_id"] == "lawson_beardlib"
        assert info["variant"] == "beardlib-native-player-style"
        assert info["runtime_verified"] is False
