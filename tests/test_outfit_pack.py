"""The LAS outfit pack (dist/lawson_outfit.zip) must look like a working
Wardrobe Mod / Legendary Armour Skins pack: the Jack Cooper pack layout,
well-formed sidecars whose object/material names resolve in the shipped
models, a co_box + root_point pair in both models, arms-only first-person
geometry on the standard heister skeleton, a no-mip 128x128 DXT5 icon, and
textures taken from the repaired (full-pyramid) sources.
"""
import importlib.util
import re
import struct
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dmodel = _load("pd2_outfit_dmodel", "tools/pd2-port/dmodel.py")
skin_repair = _load("pd2_outfit_repair", "tools/pd2-port/repair_skin_palettes.py")
build_outfit = _load("pd2_outfit_builder", "tools/pd2-port/build_outfit.py")

ROOT_FOLDER = "Lawson_LAS"
TEX_DIR = f"{ROOT_FOLDER}/assets/units/wardrobe_mod/armor_skins/textures"
UNIT_DIR = f"{ROOT_FOLDER}/assets/units/wardrobe_mod/armor_skins/lawson"
FPS_DIR = f"{ROOT_FOLDER}/assets/units/wardrobe_mod/armor_skins/lawson_fps"
ICON = (
    f"{ROOT_FOLDER}/assets/guis/dlcs/wardrobe_mod/textures/pd2/blackmarket/"
    "icons/player_styles/lawson.texture"
)


def _model_has_name(blob: bytes, name: str) -> bool:
    sections, *_ = skin_repair.parse_model_bytes(blob)
    h = dmodel.hash_str(name)
    return any(getattr(s.obj, "name_hash", None) == h for s in sections)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    try:
        import PIL  # noqa: F401
    except ImportError:
        pytest.skip("Pillow required to build the outfit pack")
    out = tmp_path_factory.mktemp("outfit") / "lawson_outfit.zip"
    build_outfit.build_pack(
        ROOT / "dist" / "lawson_clover.zip",
        out,
        ROOT / "Lawson model" / "Miranda_face_d.png",
    )
    return ZipFile(out)


@pytest.fixture(scope="module")
def tpp_model(pack):
    return pack.read(f"{UNIT_DIR}/lawson.model")


@pytest.fixture(scope="module")
def fps_model(pack):
    return pack.read(f"{FPS_DIR}/lawson_fps.model")


# ---------------------------------------------------------------- layout
def test_pack_layout(pack):
    names = set(pack.namelist())
    required = {
        f"{ROOT_FOLDER}/main.xml",
        f"{ROOT_FOLDER}/localization/english.txt",
        f"{ROOT_FOLDER}/README.txt",
        ICON,
        f"{UNIT_DIR}/lawson.model",
        f"{UNIT_DIR}/lawson.unit",
        f"{UNIT_DIR}/lawson.object",
        f"{UNIT_DIR}/lawson.material_config",
        f"{FPS_DIR}/lawson_fps.model",
        f"{FPS_DIR}/lawson_fps.unit",
        f"{FPS_DIR}/lawson_fps.object",
        f"{FPS_DIR}/lawson_fps.material_config",
    }
    assert required <= names
    assert names == required | {f"{TEX_DIR}/{n}" for n in
                                {p.split("/")[-1] for p in names if p.startswith(TEX_DIR)}}
    # exactly the 19 repaired source textures
    tex = [n for n in names if n.startswith(TEX_DIR)]
    assert len(tex) == 19


# ---------------------------------------------------------------- models
def test_models_valid(tpp_model, fps_model):
    for blob in (tpp_model, fps_model):
        assert skin_repair.validate_model_skinning(blob, strict_layout=True) == []
        sections, legacy, version, _fs, _by = skin_repair.parse_model_bytes(blob)
        assert legacy is False and version == 1


def test_models_have_co_box_and_root(tpp_model, fps_model):
    for blob in (tpp_model, fps_model):
        assert _model_has_name(blob, "root_point")
        assert _model_has_name(blob, "co_box")


def test_fps_model_is_arms_only(fps_model):
    sections, *_rest, by_id = skin_repair.parse_model_bytes(fps_model)
    drawables = [
        s for s in sections
        if s.tag == "model_data" and getattr(s.obj, "version", 3) != 6
    ]
    names = {s.obj.name_hash for s in drawables}
    assert names == {dmodel.hash_str("g_body"), dmodel.hash_str("g_hands")}
    # head/hair must be gone
    for gone in ("g_head_fem1", "g_hair_cloth1", "s_body"):
        assert not _model_has_name(fps_model, gone)
    # arms are a strict subset of the full body
    total = 0
    for s in drawables:
        md = s.obj
        pg = by_id[md.passthrough_id].obj
        total += by_id[pg.geometry_id].obj.vert_count
    assert 3000 < total < 12000


def test_fps_keeps_heister_skeleton(fps_model):
    for bone in ("Hips", "Spine2", "LeftArm", "LeftHand", "RightHand",
                 "LeftHandIndex1", "a_weapon_left_front", "aim"):
        assert _model_has_name(fps_model, bone), bone


# ---------------------------------------------------------------- sidecars
def test_object_names_resolve_in_models(pack, tpp_model, fps_model):
    for folder, blob in ((UNIT_DIR, tpp_model), (FPS_DIR, fps_model)):
        base = folder.split("/")[-1]
        xml = pack.read(f"{folder}/{base}.object").decode()
        root = ET.fromstring(xml)
        group = root.find(".//graphic_group")
        assert group.get("culling_object") == "co_box"
        for obj in root.iter("object"):
            assert _model_has_name(blob, obj.get("name")), obj.get("name")


def test_material_configs_resolve(pack, tpp_model, fps_model):
    names = set(pack.namelist())
    for folder, blob in ((UNIT_DIR, tpp_model), (FPS_DIR, fps_model)):
        base = folder.split("/")[-1]
        xml = pack.read(f"{folder}/{base}.material_config").decode()
        root = ET.fromstring(xml)
        mats = [m.get("name") for m in root.iter("material")]
        assert mats
        for mat in mats:
            assert _model_has_name(blob, mat), mat
        for f in re.findall(r'file="(units/wardrobe_mod/[^"]+)"', xml):
            assert f"{ROOT_FOLDER}/assets/{f}.texture" in names, f


def test_fps_materials_use_depth_scaling(pack):
    xml = pack.read(f"{FPS_DIR}/lawson_fps.material_config").decode()
    root = ET.fromstring(xml)
    for mat in root.iter("material"):
        assert mat.get("render_template", "").startswith("generic:DEPTH_SCALING:")
        for var in mat.iter("variable"):
            assert not var.get("name", "").startswith("contour_")


def test_main_xml_references_resolve(pack):
    names = set(pack.namelist())
    xml = pack.read(f"{ROOT_FOLDER}/main.xml").decode()
    root = ET.fromstring(xml)
    style = root.find(".//PlayerStyle")
    assert style.get("id") == "lawson"
    assert style.get("third_unit").endswith("/lawson/lawson")
    assert style.get("unit").endswith("/lawson_fps/lawson_fps")
    chars = {c.tag for c in style.find("characters")}
    assert {"bodhi", "chains", "bonnie", "female_1"} <= chars
    # every registered path exists on disk (extension-less like vanilla packs)
    assert f"{ROOT_FOLDER}/assets/{style.get('third_unit')}.model" in names
    assert f"{ROOT_FOLDER}/assets/{style.get('unit')}.model" in names
    addfiles = root.find(".//AddFiles")
    for tex in addfiles.iter("texture"):
        assert f"{ROOT_FOLDER}/assets/{tex.get('path')}.texture" in names, tex.get("path")
    for um in addfiles.iter("unit_mat"):
        assert f"{ROOT_FOLDER}/assets/{um.get('path')}.model" in names, um.get("path")
    assert root.get("image").endswith("/player_styles/lawson")
    assert f"{ROOT_FOLDER}/assets/{root.get('image')}.texture" in names
    for path in re.findall(r'(?:path|image)="((?:units|guis)/[^"]+)"', xml):
        assert not path.endswith(".texture"), "AddFiles paths must be extension-less"


def test_localization_keys(pack):
    txt = pack.read(f"{ROOT_FOLDER}/localization/english.txt").decode()
    for key in ("bm_suit_lawson", "menu_l_global_value_lawson", "bm_suit_lawson_desc"):
        assert f'"{key}"' in txt


# ---------------------------------------------------------------- assets
def test_icon_is_dxt5_no_mips(pack):
    blob = pack.read(ICON)
    assert blob[:4] == b"DDS "
    flags = struct.unpack_from("<I", blob, 8)[0]
    h, w = struct.unpack_from("<II", blob, 12)
    mips = struct.unpack_from("<I", blob, 28)[0]
    assert (w, h) == (128, 128)
    assert flags == 0x00081007 and mips == 0
    assert blob[84:88] == b"DXT5"


def test_textures_are_repaired_pyramids(pack):
    for name in (f"{TEX_DIR}/vixen_d.texture", f"{TEX_DIR}/miranda_body_d.texture"):
        blob = pack.read(name)
        flags = struct.unpack_from("<I", blob, 8)[0]
        mips = struct.unpack_from("<I", blob, 28)[0]
        caps = struct.unpack_from("<I", blob, 108)[0]
        assert flags == 0x000A1007, name
        assert mips > 1, name
        assert caps == 0x00401008, name


def test_shipped_zip_is_current():
    """dist/lawson_outfit.zip must exist and carry the same payload as a fresh build."""
    shipped = ROOT / "dist" / "lawson_outfit.zip"
    if not shipped.exists():
        pytest.skip("dist/lawson_outfit.zip not built yet")
    try:
        import PIL  # noqa: F401
    except ImportError:
        pytest.skip("Pillow required")
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "fresh.zip"
        build_outfit.build_pack(
            ROOT / "dist" / "lawson_clover.zip",
            out,
            ROOT / "Lawson model" / "Miranda_face_d.png",
        )
        with ZipFile(shipped) as a, ZipFile(out) as b:
            assert sorted(a.namelist()) == sorted(b.namelist())
            for n in a.namelist():
                assert a.read(n) == b.read(n), n
