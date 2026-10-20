"""Tests for the pd2-las pipeline against the tracked L4D2 source zip.

These are offline structural tests: they prove the VPK/MDL/VVD/VTX/VTF readers
work on the real source assets and that the LAS scaffold matches the 2B
registration contract. They are not an engine test.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE_ZIP = REPO / "l4d2_miranda_lawson_1.zip"
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

pytestmark = pytest.mark.skipif(
    not SOURCE_ZIP.is_file(), reason="source zip l4d2_miranda_lawson_1.zip not present"
)

VPK_INNER = "miranda_rochelle.vpk"


@pytest.fixture(scope="module")
def arc():
    from vpk import VpkArchive

    return VpkArchive.from_zip(SOURCE_ZIP, VPK_INNER)


@pytest.fixture(scope="module")
def tpp(arc):
    from source_model import load_model

    return load_model(
        arc.read("models/survivors/survivor_producer.mdl"),
        arc.read("models/survivors/survivor_producer.vvd"),
        arc.read("models/survivors/survivor_producer.dx90.vtx"),
    )


@pytest.fixture(scope="module")
def fps(arc):
    from source_model import load_model

    return load_model(
        arc.read("models/weapons/arms/v_arms_producer_new.mdl"),
        arc.read("models/weapons/arms/v_arms_producer_new.vvd"),
        arc.read("models/weapons/arms/v_arms_producer_new.dx90.vtx"),
    )


class TestVpk:
    def test_entry_inventory(self, arc):
        paths = {e.path for e in arc.entries}
        assert len(paths) == 25
        assert "addoninfo.txt" in paths
        assert "models/survivors/survivor_producer.mdl" in paths
        assert "models/weapons/arms/v_arms_producer_new.mdl" in paths
        assert "materials/models/miranda/miranda_body.vmt" in paths

    def test_read_crc_checked(self, arc):
        data = arc.read("addoninfo.txt")
        assert data.startswith(b'"AddonInfo"')

    def test_missing_entry_rejected(self, arc):
        from vpk import VpkError

        with pytest.raises(VpkError):
            arc.read("no/such/file.txt")

    def test_traversal_rejected(self, arc):
        from vpk import VpkError, _safe_rel_path

        with pytest.raises(VpkError):
            _safe_rel_path("../evil")
        with pytest.raises(VpkError):
            _safe_rel_path("/abs/path")
        with pytest.raises(VpkError):
            _safe_rel_path("C:/windows/path")

    def test_extract_layout(self, arc, tmp_path):
        written = arc.extract(tmp_path / "out")
        assert len(written) == 25
        assert (tmp_path / "out" / "models/survivors/survivor_producer.mdl").is_file()
        with open(tmp_path / "out" / "addoninfo.txt", "rb") as fh:
            assert fh.read().startswith(b'"AddonInfo"')


class TestSourceModel:
    def test_body_bones_and_geometry(self, tpp):
        assert tpp.name == "miranda.smd"
        assert len(tpp.bones) == 104
        assert tpp.bones[0].name == "ValveBiped.Bip01_Pelvis"
        assert tpp.bones[0].parent == -1
        names = {b.name for b in tpp.bones}
        assert {"ValveBiped.Bip01_Spine", "ValveBiped.Bip01_Head1"} <= names or \
            {"ValveBiped.Bip01_Spine", "ValveBiped.Bip01_Head"} <= names
        assert len(tpp.vertices) == 9874
        assert tpp.triangle_count > 15000
        assert tpp.materials == [
            "miranda_hair",
            "eyeball_r",
            "eyeball_l",
            "miranda_face",
            "miranda_head",
            "miranda_body",
            "phy",
        ]

    def test_mesh_material_coverage(self, tpp):
        by_mat = {m.material: len(m.triangle_indices) // 3 for m in tpp.meshes}
        assert set(by_mat) == {
            "miranda_hair",
            "eyeball_r",
            "eyeball_l",
            "miranda_face",
            "miranda_head",
            "miranda_body",
        }
        assert by_mat["miranda_body"] > 5000

    def test_vertex_weights_valid(self, tpp):
        for v in tpp.vertices[::500]:
            assert 1 <= len(v.weights) <= 3
            total = sum(w for _, w in v.weights)
            assert 0.99 <= total <= 1.01
            for bone, w in v.weights:
                assert 0 <= bone < len(tpp.bones)
                assert 0.0 < w <= 1.0

    def test_parent_indices_in_range(self, tpp):
        for i, b in enumerate(tpp.bones):
            assert b.parent == -1 or 0 <= b.parent < i

    def test_arms_model(self, fps):
        assert fps.name == "miranda_arms.smd"
        assert len(fps.bones) > 30
        assert fps.triangle_count > 2000
        assert fps.materials == ["miranda_body"]

    def test_triangle_indices_in_range(self, tpp, fps):
        for model in (tpp, fps):
            n = len(model.vertices)
            for mesh in model.meshes:
                assert all(0 <= i < n for i in mesh.triangle_indices)


class TestVtf:
    STEMS = [
        "miranda_body_color",
        "miranda_body_normal",
        "miranda_face_color",
        "miranda_face_normal",
        "miranda_head_color",
        "miranda_head_normal",
        "miranda_eyes",
    ]

    def test_all_material_textures_parse(self, arc):
        from vtf import parse_vtf

        for stem in self.STEMS:
            img = parse_vtf(arc.read(f"materials/models/miranda/{stem}.vtf"))
            assert img.format_name == "DXT5"
            assert img.mipmap_count >= 8
            assert img.width == img.height

    def test_dds_sizes_and_magic(self, arc):
        from vtf import parse_vtf, to_dds

        img = parse_vtf(arc.read("materials/models/miranda/miranda_body_color.vtf"))
        assert (img.width, img.height, img.mipmap_count) == (1024, 1024, 11)
        dds = to_dds(img)
        assert dds[:4] == b"DDS "
        expected = 128 + 1024 * 1024 + 262144 + 65536 + 16384 + 4096 + 1024 + 256 + 64 + 16 + 16 + 16
        assert len(dds) == expected

    def test_mip_order_largest_first(self, arc):
        """The clean mip 0 must be the file-tail slice (VTF stores smallest first)."""
        from vtf import parse_vtf, to_dds

        img = parse_vtf(arc.read("materials/models/miranda/miranda_face_color.vtf"))
        dds = to_dds(img)
        body = dds[128:]
        mip0 = body[: 1024 * 1024]
        assert mip0 == img.data[-1024 * 1024 :]

    def test_png_preview(self, arc):
        from vtf import parse_vtf, to_png

        img = parse_vtf(arc.read("materials/models/miranda/miranda_eyes.vtf"))
        png = to_png(img)
        assert png.startswith(b"\x89PNG")
        assert (img.width, img.height) == (128, 128)


class TestDdsEncode:
    def test_bc3_roundtrip_solid(self):
        import numpy as np

        from dds_encode import rgba_to_bc3_dds

        rgba = np.zeros((8, 8, 4), dtype=np.uint8)
        rgba[..., 0] = 200
        rgba[..., 1] = 120
        rgba[..., 2] = 90
        rgba[..., 3] = 255
        dds = rgba_to_bc3_dds(rgba)
        assert dds[:4] == b"DDS "
        assert len(dds) == 128 + 4 * 16  # 2x2 blocks

        import io

        from PIL import Image

        im = Image.open(io.BytesIO(dds))
        im.load()
        out = np.asarray(im.convert("RGBA"))
        # naive endpoints quantize to 565; allow ~8 per channel
        assert abs(int(out[0, 0, 0]) - 200) <= 8
        assert abs(int(out[0, 0, 1]) - 120) <= 8
        assert abs(int(out[0, 0, 3]) - 255) <= 2


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    import numpy as np

    from dds_encode import rgba_to_bc3_dds
    from las_pack import write_pack

    out = tmp_path_factory.mktemp("packout")
    textures = {
        "miranda_body_df.texture": b"DDS fake",
        "miranda_body_nm.texture": b"DDS fake",
    }
    icon = rgba_to_bc3_dds(np.zeros((16, 16, 4), dtype=np.uint8))
    return write_pack(out, textures, icon, {"note": "test"}, models_present=False)


class TestLasScaffold:
    def test_layout(self, pack):
        assert (pack / "main.xml").is_file()
        assert (pack / "hooks" / "miranda_las.lua").is_file()
        assert (pack / "localization" / "english.txt").is_file()
        assert (pack / "WIP_DO_NOT_INSTALL.txt").is_file()
        assert (
            pack / "assets/units/miranda/skins/miranda/miranda.unit"
        ).is_file()
        assert (
            pack / "assets/units/miranda/skins/miranda/fps_miranda.object"
        ).is_file()

    def test_hook_matches_2b_contract(self, pack):
        lua = (pack / "hooks" / "miranda_las.lua").read_text()
        assert "LegendaryArmours = LegendaryArmours or {}" in lua
        assert "la.miranda = {" in lua
        assert 'unit = "units/miranda/skins/miranda/miranda"' in lua
        assert 'fps_unit = "units/miranda/skins/miranda/fps_miranda"' in lua
        for flag in (
            "hide_mask",
            "hide_armor",
            "replace_all",
            "fps_hide_armor",
            "fps_replace_body",
        ):
            assert f"{flag} = true" in lua

    def test_main_xml_registration(self, pack):
        xml = (pack / "main.xml").read_text()
        assert 'source_file="lib/tweak_data/armorskinstweakdata"' in xml
        assert '<hook file="miranda_las.lua"' in xml
        assert '<df_nm path="units/miranda/skins/miranda/miranda_body"/>' in xml
        assert '<texture path="units/miranda/skins/miranda/miranda_eyes"/>' in xml
        assert '<unit_mat path="units/miranda/skins/miranda/miranda"/>' in xml
        assert '<unit_mat path="units/miranda/skins/miranda/fps_miranda"/>' in xml
        assert 'image="guis/dlcs/miranda/armor_skins/miranda"' in xml

    def test_localization_keys(self, pack):
        loc = json.loads((pack / "localization" / "english.txt").read_text())
        assert loc["bm_menu_miranda_armor_skins"] == "Miranda Lawson"
        assert loc["bm_askn_miranda"] == "Miranda Lawson"
        assert "bm_askn_miranda_desc" in loc

    def test_build_info_hashes(self, pack):
        info = json.loads((pack / "BUILD_INFO.json").read_text())
        assert info["models_present"] is False
        assert info["runtime_verified"] is False
        assert info["registration"]["table"] == "LegendaryArmours.miranda"
        digest = hashlib.sha256((pack / "main.xml").read_bytes()).hexdigest()
        assert info["payload_sha256"]["main.xml"] == digest

    def test_build_info_records_template_hashes(self, pack):
        """Build-input hashes must persist in BUILD_INFO (override merge)."""
        import las_pack

        las_pack.refresh_build_info(
            pack, templates={"2b.model": "a" * 64, "fps_2b.model": "b" * 64}
        )
        info = json.loads((pack / "BUILD_INFO.json").read_text())
        assert info["templates"] == {"2b.model": "a" * 64, "fps_2b.model": "b" * 64}
        digest = hashlib.sha256((pack / "main.xml").read_bytes()).hexdigest()
        assert info["payload_sha256"]["main.xml"] == digest

    def test_source_zip_hash_recorded(self):
        """The repo source zip hash must match what the last build recorded."""
        inv_path = REPO / "build" / "pd2-las" / "source_inventory.json"
        if not inv_path.is_file():
            pytest.skip("build output not present")
        inv = json.loads(inv_path.read_text())
        digest = hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
        assert inv["source_zip_sha256"] == digest

    def test_inventory_stage_always_persists(self, tmp_path):
        """--stage inventory must write source_inventory.json (with models),
        not only dump JSON to stdout — otherwise the build leaves no record."""
        import build_las

        rc = build_las.main(["--stage", "inventory", "--out", str(tmp_path)])
        assert rc == 0
        inv = json.loads((tmp_path / "source_inventory.json").read_text())
        assert inv["source_zip_sha256"] == hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
        assert "third_person" in inv["models"]
        assert inv["models"]["third_person"]["triangles"] > 0

    def test_material_config_weight_classes(self, pack):
        """Guide contract: contour template + unique on TPP skins, fps depth scaling."""
        tpp_cfg = (
            pack / "assets/units/miranda/skins/miranda/miranda.material_config"
        ).read_text()
        fps_cfg = (
            pack / "assets/units/miranda/skins/miranda/fps_miranda.material_config"
        ).read_text()
        # root header per guide: version="3" + group
        for cfg in (tpp_cfg, fps_cfg):
            assert cfg.startswith('<materials version="3" group="')
        # third-person skins: CONTOUR template, unique="true", contour variables
        for name in ("mtr_body", "mtr_face", "mtr_head", "mtr_hair"):
            assert f'name="{name}" unique="true"' in tpp_cfg, name
        assert tpp_cfg.count(
            'render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"'
        ) == 4
        assert tpp_cfg.count('name="contour_color"') == 4
        assert tpp_cfg.count('name="contour_opacity"') == 4
        # eyes: diffuse-only 3 weights; shadow: 2B contract
        assert 'name="mtr_eyes" render_template="generic:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS"' in tpp_cfg
        assert 'name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT"' in tpp_cfg
        # fps: guide fps example exactly, no contour
        assert (
            'name="mtr_body" render_template="generic:DEPTH_SCALING:DIFFUSE_TEXTURE:'
            'NORMALMAP:SKINNED_3WEIGHTS"' in fps_cfg
        )
        assert "CONTOUR" not in fps_cfg
        # texture paths carry no file extension (guide)
        for cfg in (tpp_cfg, fps_cfg):
            for line in cfg.splitlines():
                if "_texture file=" in line:
                    assert ".texture" not in line and ".dds" not in line, line

    def test_refresh_build_info_sees_models(self, pack, tmp_path):
        """refresh_build_info flips models_present and re-hashes the tree."""
        import shutil

        from las_pack import refresh_build_info

        clone = tmp_path / "Miranda_LAS"
        shutil.copytree(pack, clone)
        unit = clone / "assets/units/miranda/skins/miranda"
        (unit / "miranda.model").write_bytes(b"fake model")
        (unit / "fps_miranda.model").write_bytes(b"fake fps model")
        (clone / "WIP_DO_NOT_INSTALL.txt").unlink()
        refresh_build_info(clone)
        info = json.loads((clone / "BUILD_INFO.json").read_text())
        assert info["models_present"] is True
        assert "WIP_DO_NOT_INSTALL.txt" not in info["payload_sha256"]
        for rel in (
            "assets/units/miranda/skins/miranda/miranda.model",
            "assets/units/miranda/skins/miranda/fps_miranda.model",
        ):
            digest = hashlib.sha256((clone / rel).read_bytes()).hexdigest()
            assert info["payload_sha256"][rel] == digest

    def test_zip_pack_layout(self, pack, tmp_path):
        import shutil
        import zipfile

        from las_pack import refresh_build_info, zip_pack

        clone = tmp_path / "Miranda_LAS"
        shutil.copytree(pack, clone)
        refresh_build_info(clone)
        out = zip_pack(clone)
        assert out.name == "Miranda_LAS.zip"
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        assert "Miranda_LAS/main.xml" in names
        assert "Miranda_LAS/BUILD_INFO.json" in names
        assert all(n.startswith("Miranda_LAS/") for n in names)
        # reproducible: a second pack of identical content is byte-identical
        clone2 = tmp_path / "copy" / "Miranda_LAS"
        clone2.parent.mkdir()
        shutil.copytree(clone, clone2)
        out2 = zip_pack(clone2)
        assert out.read_bytes() == out2.read_bytes()

    def test_reference_archive_untouched(self):
        ref = REPO / "2b.rar"
        if ref.is_file():
            # 2b.rar is the contract reference; the pipeline must not rewrite it.
            assert zipfile.is_zipfile(ref) is False

    def test_tracked_miranda_las_pack(self):
        """The built Miranda_LAS.zip deliverable is tracked in dist/ and self-consistent."""
        build_zip = REPO / "build" / "pd2-las" / "Miranda_LAS.zip"
        dist_zip = REPO / "dist" / "Miranda_LAS.zip"
        build_sha = REPO / "build" / "pd2-las" / "Miranda_LAS.zip.sha256"
        dist_sha = REPO / "dist" / "Miranda_LAS.zip.sha256"
        for p in (build_zip, dist_zip, build_sha, dist_sha):
            assert p.is_file(), f"missing tracked deliverable: {p}"
        raw = dist_zip.read_bytes()
        assert build_zip.read_bytes() == raw
        digest = hashlib.sha256(raw).hexdigest()
        assert build_sha.read_text().split()[0] == digest
        assert dist_sha.read_text().split()[0] == digest
        with zipfile.ZipFile(dist_zip) as z:
            info = json.loads(z.read("Miranda_LAS/BUILD_INFO.json"))
            assert info["models_present"] is True
            assert "WIP_DO_NOT_INSTALL.txt" not in info["payload_sha256"]
            assert len(info["payload_sha256"]) == 19
            for rel, expected in info["payload_sha256"].items():
                actual = hashlib.sha256(z.read(f"Miranda_LAS/{rel}")).hexdigest()
                assert actual == expected, rel

    def test_tracked_joy_head_replacement_packs(self):
        """Both Joy head-replacement mod_overrides packs in dist/ are tracked and valid."""
        import diesel_model as dm

        for zip_name, prefix in (
            ("Miranda_L4D2_over_Joy.zip", "Miranda L4D2 over Joy"),
            ("Miranda_Romance_over_Joy.zip", "Miranda Romance over Joy"),
        ):
            zp = REPO / "dist" / zip_name
            sp = REPO / "dist" / f"{zip_name}.sha256"
            assert zp.is_file(), f"missing {zp}"
            assert sp.is_file(), f"missing {sp}"
            raw = zp.read_bytes()
            assert sp.read_text().split()[0] == hashlib.sha256(raw).hexdigest()
            unit_dir = f"{prefix}/units/pd2_dlc_joy/characters/npc_criminals_joy_1"
            icon_path = f"{prefix}/guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture"
            with zipfile.ZipFile(zp) as z:
                names = set(z.namelist())
                assert icon_path in names
                assert len(z.read(icon_path)) == 65664
                m_bytes = z.read(f"{unit_dir}/npc_criminal_joy_1.model")
                assert m_bytes == z.read(f"{unit_dir}/npc_criminal_joy_1_menu.model")
                mf = dm.ModelFile.read(m_bytes)
                for did, gid, tid in ((120, 228, 229), (121, 233, 234)):
                    md = dm.decode_model_data(mf.by_id(did).payload)
                    geo = dm.decode_geometry(mf.by_id(gid).payload)
                    topo = dm.decode_topology(mf.by_id(tid).payload)
                    assert len(md["atoms"]) == 2
                    assert geo["vert_count"] > 4000
                    assert len(topo["indices"]) == sum(a["tri_count"] for a in md["atoms"]) * 3

    def test_tracked_clover_bonnie_sydney_head_replacement_packs(self):
        """Clover, Bonnie, and Sydney head-replacement mod_overrides packs in dist/ are tracked and valid."""
        import diesel_model as dm

        specs = [
            (
                "Miranda_L4D2_over_Clover.zip",
                "Miranda L4D2 over Clover",
                "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
                "g_head_fem1",
                "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture",
            ),
            (
                "Miranda_Romance_over_Clover.zip",
                "Miranda Romance over Clover",
                "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
                "g_head_fem1",
                "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture",
            ),
            (
                "Miranda_L4D2_over_Bonnie.zip",
                "Miranda L4D2 over Bonnie",
                "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
                "g_head",
                "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture",
            ),
            (
                "Miranda_Romance_over_Bonnie.zip",
                "Miranda Romance over Bonnie",
                "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
                "g_head",
                "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture",
            ),
            (
                "Miranda_L4D2_over_Sydney.zip",
                "Miranda L4D2 over Sydney",
                "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
                "g_head",
                "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture",
            ),
            (
                "Miranda_Romance_over_Sydney.zip",
                "Miranda Romance over Sydney",
                "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
                "g_head",
                "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture",
            ),
        ]
        for zip_name, prefix, model_rel, head_draw, icon_rel in specs:
            zp = REPO / "dist" / zip_name
            sp = REPO / "dist" / f"{zip_name}.sha256"
            assert zp.is_file(), f"missing {zp}"
            assert sp.is_file(), f"missing {sp}"
            raw = zp.read_bytes()
            assert sp.read_text().split()[0] == hashlib.sha256(raw).hexdigest()
            with zipfile.ZipFile(zp) as z:
                names = set(z.namelist())
                assert f"{prefix}/{icon_rel}" in names
                assert len(z.read(f"{prefix}/{icon_rel}")) == 65664
                mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
                md_by_hash = {
                    dm.decode_model_data(s.payload)["name_hash"]: s
                    for s in mf.by_type(dm.MODEL_DATA)
                }
                md = dm.decode_model_data(md_by_hash[dm.hash64(head_draw)].payload)
                pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
                topo = dm.decode_topology(mf.by_id(pg["topology"]).payload)
                mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
                sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
                assert len(md["atoms"]) == 2
                assert len(mg["material_ids"]) == 2
                assert len(sb["maps"]) == 3
                assert geo["vert_count"] > 4000
                assert len(topo["indices"]) == sum(a["tri_count"] for a in md["atoms"]) * 3

    def test_tracked_pack_specular_alpha_and_pd2_normal_layout(self):
        """Diffuse alpha carries attenuated specular (< 80) and normal maps use PD2 layout."""
        import numpy as np

        build_zip = REPO / "build" / "pd2-las" / "Miranda_LAS.zip"
        with zipfile.ZipFile(build_zip) as z:
            for stem in ("miranda_body_df", "miranda_face_df", "miranda_head_df", "miranda_eyes"):
                raw = z.read(f"Miranda_LAS/assets/units/miranda/skins/miranda/{stem}.texture")
                blocks = np.frombuffer(raw[128:], dtype=np.uint8).reshape(-1, 16)
                assert int(blocks[:, 0].max()) <= 72, f"{stem} alpha too glossy: {blocks[:, 0].max()}"
                assert float(blocks[:, 0].mean()) < 35.0, f"{stem} mean alpha too high"
            for stem in ("miranda_body_nm", "miranda_face_nm", "miranda_head_nm"):
                raw = z.read(f"Miranda_LAS/assets/units/miranda/skins/miranda/{stem}.texture")
                blocks = np.frombuffer(raw[128:], dtype=np.uint8).reshape(-1, 16)
                c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
                c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
                assert np.all(((c0 >> 11) & 31) == 31), f"{stem} red channel not 255"
                assert np.all((c0 & 31) == 0), f"{stem} blue channel not 0"
                assert np.all(c0 >= c1), f"{stem} has c0 < c1"
                assert int(blocks[:, 0].max()) - int(blocks[:, 1].min()) > 16, f"{stem} alpha flat"


