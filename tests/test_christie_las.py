"""Offline structural tests for dist/Christie_LAS.zip (DOA5 Christie, body-only).

The pack is built by tools/pd2-las/build_christie_las.py from
references/Christie.zip. "Without head" means: no head geometry in the models
(g_head/g_head_lod1 dropped), no head drawable in the object XMLs, and the LAS
hook registers replace_body (not replace_all) so LAS keeps the heister's own
head — the police-uniform style LAS contract.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIST_ZIP = REPO / "dist" / "Christie_LAS.zip"
SOURCE_ZIP = REPO / "references" / "Christie.zip"
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

pytestmark = pytest.mark.skipif(
    not DIST_ZIP.is_file(), reason="dist/Christie_LAS.zip not built"
)

UNIT = "Christie_LAS/assets/units/christie/skins/christie"


@pytest.fixture(scope="module")
def zf():
    return zipfile.ZipFile(DIST_ZIP)


def test_sha256_sidecar(zf):
    digest = hashlib.sha256(DIST_ZIP.read_bytes()).hexdigest()
    sidecar = (REPO / "dist" / "Christie_LAS.zip.sha256").read_text()
    assert digest in sidecar


def test_zip_is_reproducible_shape(zf):
    for info in zf.infolist():
        assert info.date_time == (2020, 1, 1, 0, 0, 0)


def test_hook_registers_headless_contract(zf):
    lua = zf.read("Christie_LAS/hooks/christie_las.lua").decode()
    assert "la.christie = {" in lua
    assert "replace_body = true" in lua
    assert "replace_all" not in lua          # would claim the head; pack has none
    for flag in ("hide_mask", "hide_armor", "fps_hide_armor", "fps_replace_body"):
        assert f"{flag} = true" in lua
    assert 'unit = "units/christie/skins/christie/christie"' in lua
    assert 'fps_unit = "units/christie/skins/christie/fps_christie"' in lua


def test_models_have_no_head_drawables(zf):
    import diesel_model as dm
    import las_outfit_pack as lop

    for stem in ("christie", "fps_christie"):
        data = zf.read(f"{UNIT}/{stem}.model")
        mf = dm.ModelFile.read(data)
        assert mf.write() == data                       # byte round-trip
        drawables = lop.model_drawables(data)
        assert "g_body" in drawables
        assert "g_head" not in drawables
        assert "g_head_lod1" not in drawables
        obj = zf.read(f"{UNIT}/{stem}.object").decode()
        assert "g_head" not in obj


def test_material_config_names_match_model(zf):
    import diesel_model as dm

    for stem in ("christie", "fps_christie"):
        mf = dm.ModelFile.read(zf.read(f"{UNIT}/{stem}.model"))
        model_hashes = {dm.decode_material(s.payload)["name_hash"]
                        for s in mf.by_type(dm.MATERIAL)}
        cfg = zf.read(f"{UNIT}/{stem}.material_config").decode()
        names = re.findall(r'<material name="([^"]+)"', cfg)
        assert names, stem
        for n in names:
            assert dm.hash64(n) in model_hashes, f"{stem}: {n} not in model"
        # every mtr_* the model carries is declared in the config
        hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
        model_names = {n for n in hl if n.startswith("mtr_")} | {"shadow_caster"}
        for n in model_names:
            assert n in names, f"{stem}: model material {n} missing from config"


def test_main_xml_registers_every_texture_and_unit(zf):
    main = zf.read("Christie_LAS/main.xml").decode()
    names = {i.filename for i in zf.infolist()}
    for stem in ("christie_body", "christie_c02_01", "christie_c02_02",
                 "christie_c02_05"):
        assert f'<df_nm path="units/christie/skins/christie/{stem}"/>' in main
        assert f"{UNIT}/{stem}_df.texture" in names
        assert f"{UNIT}/{stem}_nm.texture" in names
    assert '<unit_mat path="units/christie/skins/christie/christie"/>' in main
    assert '<unit_mat path="units/christie/skins/christie/fps_christie"/>' in main
    assert '<texture path="guis/dlcs/christie/armor_skins/christie"/>' in main


def test_build_info_records_headless_and_provenance(zf):
    info = json.loads(zf.read("Christie_LAS/BUILD_INFO.json"))
    assert info["headless"] is True
    assert info["source_zip_sha256"] == hashlib.sha256(
        SOURCE_ZIP.read_bytes()).hexdigest()
    assert info["registration"]["table"] == "LegendaryArmours.christie"
    assert "replace_all" not in info["registration"]["flags"]
    # payload hashes match the zipped files
    for rel, digest in info["payload_sha256"].items():
        assert hashlib.sha256(zf.read("Christie_LAS/" + rel)).hexdigest() == digest


def test_source_loader_reads_all_bodygroup_models():
    from build_christie_las import load_christie

    with zipfile.ZipFile(SOURCE_ZIP) as z:
        model = load_christie(z)
    assert len(model.bones) == 98
    assert len(model.vertices) == 21979           # VVD LOD0: all bodygroup models
    mats = {m.material for m in model.meshes}
    # head-carried materials exist in the source and are dropped by the build
    assert {"cri_face_base", "cri_glasses_base", "cri_hair0_base"} <= mats
    # body materials the pack keeps
    assert {"cri_body_base", "cri_02_01_base", "cri_02_02_base",
            "cri_02_05_base"} <= mats
