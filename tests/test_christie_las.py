"""Offline structural tests for the Christie LAS packs (DOA5, body-only).

Packs built by tools/pd2-las/build_christie_las.py from references/Christie.zip:

- dist/Christie_LAS.zip          — full body incl. Christie's own hands
- dist/Christie_LAS_No_hands.zip — hands cut at the wrist + glove adapter hook,
  so the in-game (changeable) gloves show through the sleeves

"Without head" means: no head geometry in the models (g_head/g_head_lod1
dropped), no head drawable in the object XMLs, and the LAS hook registers
replace_body (not replace_all) so LAS keeps the heister's own head — the
police-uniform style LAS contract. The base pack was checked in game on
2026-11-05 (heister head renders, outfit textures fixed via specular-alpha
attenuation from the normal map).
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
SOURCE_ZIP = REPO / "references" / "Christie.zip"
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

pytestmark = pytest.mark.skipif(
    not SOURCE_ZIP.is_file(), reason="references/Christie.zip not present"
)

PACKS = {
    "base": ("dist/Christie_LAS.zip", "Christie_LAS", "christie", False),
    "nohands": ("dist/Christie_LAS_No_hands.zip", "Christie_LAS_No_hands",
                "christie_no_hands", True),
    "slim": ("dist/Christie_LAS_Slim.zip", "Christie_LAS_Slim",
             "christie_slim", False),
}


def _zf(which: str) -> zipfile.ZipFile:
    path = REPO / PACKS[which][0]
    if not path.is_file():
        pytest.skip(f"{path.name} not built")
    return zipfile.ZipFile(path)


@pytest.mark.parametrize("which", sorted(PACKS))
class TestPack:
    def test_sha256_sidecar(self, which):
        _zf(which)
        dist_zip = REPO / PACKS[which][0]
        digest = hashlib.sha256(dist_zip.read_bytes()).hexdigest()
        sidecar = Path(str(dist_zip) + ".sha256").read_text()
        assert digest in sidecar

    def test_zip_is_reproducible_shape(self, which):
        for info in _zf(which).infolist():
            assert info.date_time == (2020, 1, 1, 0, 0, 0)

    def test_hook_registers_headless_contract(self, which):
        _, pack_dir, item_id, glove = PACKS[which]
        lua = _zf(which).read(f"{pack_dir}/hooks/{item_id}_las.lua").decode()
        assert f"la.{item_id} = {{" in lua
        assert "replace_body = true" in lua
        assert "replace_all" not in lua      # would claim the head; pack has none
        for flag in ("hide_mask", "hide_armor", "fps_hide_armor", "fps_replace_body"):
            assert f"{flag} = true" in lua
        assert f'unit = "units/{item_id}/skins/{item_id}/{item_id}"' in lua
        assert f'fps_unit = "units/{item_id}/skins/{item_id}/fps_{item_id}"' in lua
        main = _zf(which).read(f"{pack_dir}/main.xml").decode()
        if glove:
            assert f"{item_id}_glove_adapter.lua" in main
            hook = _zf(which).read(
                f"{pack_dir}/hooks/{item_id}_glove_adapter.lua").decode()
            assert 'ps.default_glove_id = "heist_default"' in hook
            assert "ps.glove_adapter = {}" in hook
        else:
            assert "glove_adapter" not in main

    def test_models_have_no_head_drawables(self, which):
        import diesel_model as dm
        import las_outfit_pack as lop

        _, pack_dir, item_id, _g = PACKS[which]
        unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
        for stem in (item_id, f"fps_{item_id}"):
            data = _zf(which).read(f"{unit}/{stem}.model")
            mf = dm.ModelFile.read(data)
            assert mf.write() == data                   # byte round-trip
            drawables = lop.model_drawables(data)
            assert "g_body" in drawables
            assert "g_head" not in drawables
            assert "g_head_lod1" not in drawables
            obj = _zf(which).read(f"{unit}/{stem}.object").decode()
            assert "g_head" not in obj

    def test_material_config_names_match_model(self, which):
        import diesel_model as dm

        _, pack_dir, item_id, _g = PACKS[which]
        unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
        for stem in (item_id, f"fps_{item_id}"):
            mf = dm.ModelFile.read(_zf(which).read(f"{unit}/{stem}.model"))
            model_hashes = {dm.decode_material(s.payload)["name_hash"]
                            for s in mf.by_type(dm.MATERIAL)}
            cfg = _zf(which).read(f"{unit}/{stem}.material_config").decode()
            names = re.findall(r'<material name="([^"]+)"', cfg)
            assert names, stem
            for n in names:
                assert dm.hash64(n) in model_hashes, f"{stem}: {n} not in model"
            hl = dm.decode_custom_hashlist(
                mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
            for n in {n for n in hl if n.startswith("mtr_")} | {"shadow_caster"}:
                assert n in names, f"{stem}: model material {n} missing from config"

    def test_main_xml_registers_every_texture_and_unit(self, which):
        _, pack_dir, item_id, _g = PACKS[which]
        zf = _zf(which)
        main = zf.read(f"{pack_dir}/main.xml").decode()
        names = {i.filename for i in zf.infolist()}
        unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
        for role in ("body", "c02_01", "c02_02", "c02_05"):
            assert f'<df_nm path="units/{item_id}/skins/{item_id}/{item_id}_{role}"/>' in main
            assert f"{unit}/{item_id}_{role}_df.texture" in names
            assert f"{unit}/{item_id}_{role}_nm.texture" in names
        assert f'<unit_mat path="units/{item_id}/skins/{item_id}/{item_id}"/>' in main
        assert f'<unit_mat path="units/{item_id}/skins/{item_id}/fps_{item_id}"/>' in main
        assert f'<texture path="guis/dlcs/{item_id}/armor_skins/{item_id}"/>' in main

    def test_textures_have_full_vanilla_mip_chains(self, which):
        """Vanilla PD2 DXT5 .texture files carry the full mip pyramid
        (flags 0x000A1007, caps 0x00401008, mips = log2(size)+1); the source
        VTFs ship mip 0 only, so the build must expand them."""
        import struct

        _, pack_dir, item_id, _g = PACKS[which]
        zf = _zf(which)
        unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
        for role in ("body", "c02_01", "c02_02", "c02_05"):
            for kind in ("df", "nm"):
                d = zf.read(f"{unit}/{item_id}_{role}_{kind}.texture")
                flags = struct.unpack_from("<I", d, 8)[0]
                caps = struct.unpack_from("<I", d, 108)[0]
                mips = struct.unpack_from("<I", d, 28)[0]
                size = struct.unpack_from("<I", d, 16)[0]
                assert flags == 0x000A1007, f"{role}_{kind}: flags {flags:#x}"
                assert caps == 0x00401008, f"{role}_{kind}: caps {caps:#x}"
                assert mips == size.bit_length(), f"{role}_{kind}: {mips} mips"

    def test_diffuse_alpha_is_specular_not_full_gloss(self, which):
        """PD2 reads diffuse alpha as gloss; Source leaves it 255. The build
        attenuates it from the normal map's alpha, so endpoints must be well
        below 255 on average (raw Source value would be exactly 255)."""
        import numpy as np

        _, pack_dir, item_id, _g = PACKS[which]
        zf = _zf(which)
        unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
        for role in ("body", "c02_01", "c02_02", "c02_05"):
            d = zf.read(f"{unit}/{item_id}_{role}_df.texture")
            blocks = np.frombuffer(d[128:], dtype=np.uint8).reshape(-1, 16)
            assert float(blocks[:, 0].mean()) < 128, \
                f"{role}: diffuse alpha endpoints still near full gloss"

    def test_build_info_records_headless_and_provenance(self, which):
        _, pack_dir, item_id, glove = PACKS[which]
        zf = _zf(which)
        info = json.loads(zf.read(f"{pack_dir}/BUILD_INFO.json"))
        assert info["headless"] is True
        assert info["source_zip_sha256"] == hashlib.sha256(
            SOURCE_ZIP.read_bytes()).hexdigest()
        assert info["registration"]["table"] == f"LegendaryArmours.{item_id}"
        assert "replace_all" not in info["registration"]["flags"]
        assert (info["hands"] == "glove_adapter") == glove
        for rel, digest in info["payload_sha256"].items():
            assert hashlib.sha256(zf.read(f"{pack_dir}/" + rel)).hexdigest() == digest

    def test_build_info_runtime_flag(self, which):
        _, pack_dir, _item, _g = PACKS[which]
        info = json.loads(_zf(which).read(f"{pack_dir}/BUILD_INFO.json"))
        assert info["runtime_verified"] is True   # in-game check 2026-11-05


def test_nohands_pack_has_fewer_verts():
    """The no-hands variant must actually drop hand-dominated geometry."""
    import diesel_model as dm

    counts = {}
    for which in ("base", "nohands"):
        _, pack_dir, item_id, _g = PACKS[which]
        mf = dm.ModelFile.read(
            _zf(which).read(f"{pack_dir}/assets/units/{item_id}/skins/"
                            f"{item_id}/{item_id}.model"))
        hl = dm.decode_custom_hashlist(
            mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
        for s in mf.by_type(dm.MODEL_DATA):
            md = dm.decode_model_data(s.payload)
            name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
            if name == "g_body" and md.get("version") == 3:
                gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
                counts[which] = len(geo["verts"])
    assert counts["nohands"] < counts["base"]


def _g_body_bounds(which: str):
    import numpy as np
    import diesel_model as dm

    _, pack_dir, item_id, _g = PACKS[which]
    mf = dm.ModelFile.read(
        _zf(which).read(f"{pack_dir}/assets/units/{item_id}/skins/"
                        f"{item_id}/{item_id}.model"))
    hl = dm.decode_custom_hashlist(
        mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
        if name == "g_body" and md.get("version") == 3:
            gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            v = np.array(geo["verts"])
            return np.ptp(v[:, 0]), np.ptp(v[:, 1]), np.ptp(v[:, 2])
    raise AssertionError("no g_body drawable")


def test_slim_pack_is_thinner_but_same_height():
    """The slim variant scales x/y by ~0.8 about the body axis and leaves z."""
    bx, by, bz = _g_body_bounds("base")
    sx, sy, sz = _g_body_bounds("slim")
    assert 0.75 < sx / bx < 0.85, f"slim x ratio {sx / bx:.3f}"
    assert 0.75 < sy / by < 0.85, f"slim y ratio {sy / by:.3f}"
    assert abs(sz - bz) < 0.01, "height must be unchanged"


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
