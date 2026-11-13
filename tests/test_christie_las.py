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

import functools
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE_ZIP = REPO / "references" / "Christie.zip"
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
sys.path.insert(0, str(REPO / "tools" / "pd2-port"))

pytestmark = pytest.mark.skipif(
    not SOURCE_ZIP.is_file(), reason="references/Christie.zip not present"
)

DIST = Path(os.environ.get("CHRISTIE_DIST", REPO / "dist")).resolve()
PACKS = {
    "base": (DIST / "Christie_LAS.zip", "Christie_LAS", "christie", False),
    "slim": (DIST / "Christie_LAS_Slim.zip", "Christie_LAS_Slim",
             "christie_slim", True),   # slim also cuts the hands (glove adapter)
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

    def test_normal_map_and_diffuse_mip0_meet_audit_criteria(self, which):
        """A08 acceptance criteria on the built packs (normal maps + diffuse mip-0).

        Normal map: clean DXT5, 0 misordered blocks, R=255/B=0 on every mip,
        alpha <- source R (mean err < 1.0), green <- 255 - source G (max err <= 2).
        Diffuse mip-0: RGB lossless vs the source VTF mip 0.
        """
        import struct

        import numpy as np

        from vtf import parse_vtf, to_dds

        import dds as pd2_dds

        _, pack_dir, item_id, _g = PACKS[which]
        zf = _zf(which)
        unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
        vtf_bytes = {}
        with zipfile.ZipFile(SOURCE_ZIP) as src_zf:
            for name in src_zf.namelist():
                if name.endswith(".vtf"):
                    vtf_bytes[name.rsplit("/", 1)[-1][:-4]] = src_zf.read(name)

        mat_of = {"body": "cri_body_base", "c02_01": "cri_02_01_base",
                  "c02_02": "cri_02_02_base", "c02_05": "cri_02_05_base"}

        def source_rgba(mat, kind):
            blob = vtf_bytes.get(f"{mat}_{kind}") or vtf_bytes.get(
                f"{mat.replace('_base', '')}_{kind}")
            if blob is None:
                return None
            dds_b = to_dds(parse_vtf(blob))
            size, _mips, mip0 = pd2_dds.dds_mip0_slice(dds_b)
            return pd2_dds.decode_dxt5(bytes(mip0), size, size)

        for role in ("body", "c02_01", "c02_02", "c02_05"):
            mat = mat_of[role]
            nm_key = f"{unit}/{item_id}_{role}_nm.texture"
            df_key = f"{unit}/{item_id}_{role}_df.texture"
            nm_blob = zf.read(nm_key)
            df_blob = zf.read(df_key)

            assert pd2_dds.validate_dxt5_texture(nm_blob) == [], \
                f"{role}_nm: invalid DXT5"
            _m, _h, _flags, _hw, w, _p, _d, _mi = struct.unpack_from(
                "<4s7I", nm_blob, 0)
            mip0_len = max(1, w // 4) ** 2 * 16
            assert pd2_dds.misordered_blocks(
                nm_blob[128:128 + mip0_len], w) == [], \
                f"{role}_nm: misordered blocks"
            nsize, nmips, nmip0 = pd2_dds.dds_mip0_slice(nm_blob)
            nrgba = pd2_dds.decode_dxt5(bytes(nmip0), nsize, nsize)
            pos = 128
            for lvl in range(nmips):
                ls = max(1, nsize >> lvl)
                blen = max(1, ls // 4) ** 2 * 16
                for bo in range(pos, pos + blen, 16):
                    c0 = struct.unpack_from("<H", nm_blob, bo + 8)[0]
                    assert ((c0 >> 11) & 31) == 31 and (c0 & 31) == 0, \
                        f"{role}_nm: mip{lvl} block not R=255/B=0"
                pos += blen
            src_nm = source_rgba(mat, "nrm")
            assert src_nm is not None, f"{role}: no source nrm VTF"
            src_r = src_nm[..., 0].astype(np.float64)
            src_g = src_nm[..., 1].astype(np.float64)
            a_err = float(np.mean(
                np.abs(nrgba[..., 3].astype(np.float64) - src_r)))
            assert a_err < 1.0, \
                f"{role}_nm: alpha vs R mean_err={a_err:.3f}"
            g_err = float(np.max(
                np.abs(nrgba[..., 1].astype(np.float64) - (255 - src_g))))
            assert g_err <= 2.0, \
                f"{role}_nm: G vs 255-G max_err={g_err:.1f}"

            dsize, _dmips, dmip0 = pd2_dds.dds_mip0_slice(df_blob)
            dra = pd2_dds.decode_dxt5(bytes(dmip0), dsize, dsize)
            src_df = source_rgba(mat, "base")
            assert src_df is not None, f"{role}: no source base VTF"
            assert dra.shape == src_df.shape, f"{role}_df: size mismatch"
            assert np.array_equal(dra[..., :3], src_df[..., :3]), \
                f"{role}_df: mip-0 RGB not lossless"

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

    def test_arm_loop_balance_no_one_sided_mouth(self, which, tmp_path):
        """Adapter pack must not ship a one-sided arm opening.

        For every material, arm-region boundary loops must appear on both
        sides or neither (``(L == 0) == (R == 0)``). A material with loops on
        exactly one side is the bare-arm ring the adapter pack must not show
        (§6 of the arm-skin-stub glove-adapter repair plan).
        """
        import preview_textured as pt
        import build_models as bm

        model_path = tmp_path / f"{PACKS[which][2]}.model"
        model_path.write_bytes(_zf(which).read(_model_rel(which)))

        out = {}
        for m in pt.material_meshes(model_path):
            V, F = m["vertices"], m["triangles"]
            loops = bm.boundary_loops([tuple(int(x) for x in t) for t in F])
            L = R = 0
            for lp in loops:
                idx = [i for i in lp if i < len(V)]
                if len(idx) < 6:
                    continue
                P = V[idx]
                if np.abs(P[:, 0]).max() < 33.0:
                    continue
                if P[:, 0].mean() < 0:
                    L += 1
                else:
                    R += 1
            if L or R:
                out[m["material"]] = (L, R)
        bad = [k for k, (L, R) in out.items() if (L == 0) != (R == 0)]
        assert not bad, f"{which}: one-sided arm openings: {bad}"


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


# PD2 animation-chain segment names; rest-space joint coordinates come from
# each candidate's shipped inverse binds, not from the old 72-degree template.
_P2_SEGMENTS = {"Arm": ("Arm", "ForeArm"), "ForeArm": ("ForeArm", "Hand"),
                "UpLeg": ("UpLeg", "Leg"), "Leg": ("Leg", "Foot")}


def _g_body_geo_dom(which: str):
    """(verts, dominant-bone name + weight per vertex) of the pack's g_body."""
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
            skel = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
            break
    id_name = {}
    for s in mf.by_type(dm.OBJECT3D):
        o = dm.decode_object3d(s.payload)
        id_name[s.id] = next((n for n in hl if dm.hash64(n) == o["name_hash"]), "")
    pal = [id_name.get(i, "") for i in skel["objects"]]
    v = np.array(geo["verts"], float)
    dom = []
    for bi, bw in zip(geo["blendindices"], geo["blendweights"]):
        k = int(np.argmax(bw))
        dom.append((pal[bi[k]], float(bw[k])))
    return v, dom


def _principal_radius(which: str, bone: str, side: str,
                      lo: float = 0.20, hi: float = 0.40) -> float:
    """Principal cross-section radius (sqrt of largest PCA eigenvalue of the
    perpendicular offsets) of unblended mid-segment verts (weight > 0.99)."""
    import numpy as np

    v, dom = _g_body_geo_dom(which)
    a0, b0 = _P2_SEGMENTS[bone]
    template = _rest_template(which)

    def J(n):
        world = template.worlds[template.name_id[f"{side}{n}"]]
        return np.array(world[12:15], float)

    a, b = J(a0), J(b0)
    u = (b - a) / np.linalg.norm(b - a)
    L = float(np.linalg.norm(b - a))
    sel = [i for i, (nm, w) in enumerate(dom)
           if nm == f"{side}{bone}" and w > 0.99 and lo * L <= float(u @ (v[i] - a)) <= hi * L]
    assert len(sel) >= 15, f"{side}{bone}: only {len(sel)} unblended mid-segment verts"
    pts = np.array([v[i] for i in sel])
    t = (pts - a) @ u
    r = (pts - a) - np.outer(t, u)
    lam = np.linalg.eigvalsh(np.cov(r.T))
    return float(np.sqrt(lam[-1]))


def test_slim_cross_section_ratios():
    """Slim acceptance (2026-11-06 rebalance): in unblended mid-segment slices
    the principal radius ratio slim/base must be 0.90 +/- 0.02 for legs, 0.80
    +/- 0.02 for the forearm, and ~0.736 for the upper arm -- the 0.80 segment
    scale with the bicep tuck active across the whole slice (SEGMENT_SPECS /
    BICEP_TUCK in build_christie_las; 25% arms was rebalanced to 20% + a
    10% belly tuck after the in-game check: at 25% the sleeves read
    stick-thin next to the 0.90 torso/legs, and the biceps sat off-axis)."""
    # slices avoid fade zones: forearm elbow fade ends at 6/22.5 = 0.27L,
    # the wrist fade starts at ~(22.5-8)/22.5 = 0.64L, and the widened
    # elbow blend reaches 9 cm past the joint = 0.60L
    slices = {"Arm": (0.35, 0.65), "ForeArm": (0.30, 0.55),
              "UpLeg": (0.30, 0.60), "Leg": (0.30, 0.60)}
    for bone, target in (("Arm", 0.736), ("ForeArm", 0.80),
                         ("UpLeg", 0.90), ("Leg", 0.90)):
        lo, hi = slices[bone]
        for side in ("Left", "Right"):
            rb = _principal_radius("base", bone, side, lo, hi)
            rs = _principal_radius("slim", bone, side, lo, hi)
            assert abs(rs / rb - target) <= 0.02, (
                f"{side}{bone}: radius ratio {rs / rb:.3f}, expected {target} +/- 0.02")


def test_slim_pack_same_height_and_ground():
    """v4 acceptance: final min z, max z and total height of the slim pack
    must match the base pack (height preserved, ground position unchanged)."""
    for which in ("base", "slim"):
        v, _dom = _g_body_geo_dom(which)
        zmin, zmax = float(v[:, 2].min()), float(v[:, 2].max())
        if which == "base":
            bz = (zmin, zmax)
        else:
            assert abs(zmin - bz[0]) < 0.01, f"slim min z {zmin:.3f} != base {bz[0]:.3f}"
            assert abs(zmax - bz[1]) < 0.01, f"slim max z {zmax:.3f} != base {bz[1]:.3f}"
    # slim also cuts the hands, so its vertex count drops vs the base pack
    assert _g_body_verts("slim") < _g_body_verts("base")
    bx, by, _bz = _g_body_bounds("base")
    _sx, sy, _sz = _g_body_bounds("slim")
    assert sy < by, "slim y extent must shrink (hands cut + torso scale)"


def test_arm_fit_translation_causes_no_vertex_spikes():
    """fix_arm_fits only translates the Arm/ForeArm/Hand bone fits, so blended
    shoulder verts must not spike: z extent stays near the base pack's."""
    for which in ("base", "slim"):
        _, _, bz = _g_body_bounds(which)
        assert bz < 175.0, f"{which} g_body z extent {bz:.1f} cm looks spiked"


def _g_body_verts(which: str) -> int:
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
            return len(dm.decode_geometry(mf.by_id(gp["geometry"]).payload)["verts"])
    raise AssertionError("no g_body drawable")


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


# --- math regression locks (review: convention + straighten hardening) ---

def test_mat_row_convention_associativity():
    """dm storage is row-vector: v.(a.b) == (v.a).b exactly."""
    import numpy as np
    import diesel_model as dm
    import build_models as bm

    R = np.array([[0.36, -0.48, 0.8], [0.8, 0.6, 0.0], [-0.48, 0.64, 0.6]])
    a = bm._make_sim_mat(1.1, R, (1, 2, 3), (4, 5, 6))
    b = bm._make_sim_mat(0.9, R.T, (0, 0, 0), (-1, 2, 0))
    v = np.array([1.0, -2.0, 3.0, 1.0])
    lhs = v @ np.array(dm.mat_mul(a, b)).reshape(4, 4)
    rhs = (v @ np.array(a).reshape(4, 4)) @ np.array(b).reshape(4, 4)
    assert float(np.abs(lhs - rhs).max()) < 1e-9


def test_umeyama_recovers_known_similarity():
    """_umeyama_fit must invert a known row-convention similarity to ~0 err."""
    import numpy as np
    import diesel_model as dm
    import build_models as bm

    rng = np.random.default_rng(0)
    P = rng.normal(size=(8, 3)) * 20
    th = 0.7
    Rz = np.array([[np.cos(th), -np.sin(th), 0],
                   [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    Ry = np.array([[np.cos(0.3), 0, np.sin(0.3)], [0, 1, 0],
                   [-np.sin(0.3), 0, np.cos(0.3)]])
    Rc = Rz @ Ry
    s_true, t_true = 1.13, np.array([5.0, -3.0, 11.0])
    Q = s_true * (P @ Rc.T) + t_true
    m = bm._umeyama_fit([tuple(p) for p in P], [tuple(q) for q in Q], [1.0] * 8)
    err = max(np.linalg.norm(np.array(dm.mat_apply_point(m, tuple(p))) - q)
              for p, q in zip(P, Q))
    assert err < 1e-6, f"umeyama round-trip err {err}"


def test_rodrigues_shortest_arc_maps_u_to_w_without_twist():
    import numpy as np
    import build_models as bm

    u = np.array([1.0, 2.0, 3.0])
    w = np.array([-2.0, 0.5, 1.0])
    R = bm._rodrigues_arc(u, w)
    un, wn = u / np.linalg.norm(u), w / np.linalg.norm(w)
    assert np.linalg.norm(R @ un - wn) < 1e-12
    # zero axial twist: rotation axis is perpendicular to u
    axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    assert abs(float(axis @ un)) < 1e-9


def test_hinge_axis_extraction_is_unit_and_parallel():
    """vee(R - R^T) = 2 sin(th) . axis; after normalization it must be a unit
    vector parallel to the true rotation axis (build_models asserts this)."""
    import numpy as np

    axis_true = np.array([0.2, -0.5, 0.84])
    axis_true /= np.linalg.norm(axis_true)
    th = 0.3
    K = np.array([[0, -axis_true[2], axis_true[1]],
                  [axis_true[2], 0, -axis_true[0]],
                  [-axis_true[1], axis_true[0], 0]])
    R = np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * (K @ K)
    hinge = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    ax = hinge / np.linalg.norm(hinge)
    assert abs(np.linalg.norm(ax) - 1.0) < 1e-12
    assert min(np.linalg.norm(ax - axis_true), np.linalg.norm(ax + axis_true)) < 1e-9


def test_axial_stretch_is_affine_not_similarity():
    """The _axial_mat 3x3 has singular values {lam, s_core, s_core}: a rank-1
    axial stretch, not a similarity. Locks the corrected doc wording."""
    import numpy as np
    import build_models as bm

    s_core, lam = 1.02, 1.11
    ds = np.array([20.0, 0.0, 0.0])
    dt = np.array([22.0, 3.0, 0.0])
    v = dt / np.linalg.norm(dt)
    r_seg = bm._rodrigues_arc(ds, dt)
    S = s_core * np.eye(3) + (lam - s_core) * np.outer(v, v)
    A = S @ r_seg
    sv = np.linalg.svd(A, compute_uv=False)
    assert abs(sv[0] - max(lam, s_core)) < 1e-9
    assert abs(sv[1] - min(lam, s_core)) < 1e-9
    assert abs(sv[2] - min(lam, s_core)) < 1e-9
    assert abs(np.linalg.det(A) - lam * s_core ** 2) < 1e-9


def test_forearm_centerline_straight_in_base_pack():
    """straighten_segments v3 lock: the bind-pose forearm is straight *within*
    its segment - the cross-section centres must lie on one line.

    Measured with the Kasa circle fit of ``segment_fit`` rather than a median of
    the raw perp offsets: a median of a ring's vertex offsets answers "where is
    the average vertex", which swings by several cm when a lace seam or the
    elbow crease lands in the slab (it reports 3.4 cm on the reference 2B body,
    whose forearm is visibly straight). Slabs sit inside [0.3L, 0.7L], away
    from the elbow/wrist fades and blend zones. What this locks is *shape*:
    the centring pass translates slabs, so it cannot bend the segment, and the
    line fit is invariant to the overall offset.
    """
    import numpy as np
    import segment_fit as sf

    tpl = _rest_template("base")
    geom = sf.limb_geom(tpl)
    v, dom = _g_body_geo_dom("base")
    for side in ("Left", "Right"):
        bone = f"{side}ForeArm"
        a, u, L, _child = geom[bone]
        m = np.array([nm == bone and w > 0.5 for nm, w in dom])
        ts = (v[m] - a) @ u
        perp = (v[m] - a) - np.outer(ts, u)
        keep = (ts >= 0.30 * L) & (ts <= 0.70 * L)
        if keep.sum() < 30:
            pytest.skip(f"{bone}: only {int(keep.sum())} mid-segment verts")
        pts, tt = perp[keep], ts[keep]
        tmp = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = np.cross(u, tmp); e1 /= np.linalg.norm(e1)
        e2 = np.cross(u, e1)
        centres, cts = [], []
        for t0 in np.arange(0.30 * L, 0.70 * L, 2.0):
            mm = (tt >= t0) & (tt < t0 + 2.0)
            if mm.sum() < 8:
                continue
            c2, _r, _res = sf._kasa_circle(pts[mm] @ np.stack([e1, e2], axis=1))
            centres.append(c2)
            cts.append(float(tt[mm].mean()))
        assert len(centres) >= 4, f"{bone}: only {len(centres)} usable slabs"
        cs, cts = np.array(centres), np.array(cts)
        A = np.stack([np.ones_like(cts), cts], axis=1)
        coef, *_ = np.linalg.lstsq(A, cs, rcond=None)
        resid = np.linalg.norm(cs - (coef[0] + np.outer(cts, coef[1])), axis=1)
        assert resid.max() <= 1.2, (
            f"{bone}: centreline kinks {resid.max():.2f} cm off a straight line "
            f"(reference 2B: 0.4 cm)")
        # and the drift itself must be small: a straight but slanted forearm
        # would still point the bone at the sleeve edge
        drift = float(np.linalg.norm(coef[1]) * (cts.max() - cts.min()))
        assert drift <= 1.5, f"{bone}: centreline drifts {drift:.2f} cm over the sampled span"


# ---------------------------------------------------------------------------
# mesh-vs-skeleton fit: the limb tube has to sit ON the bone that drives it
# ---------------------------------------------------------------------------
# Reference numbers come from PD2's own fitted 2B body (the pack template),
# measured through the same code path (tools/pd2-las/segment_fit.py):
#   forearm cross-section circle centres: 0.4 - 1.2 cm off the ForeArm axis
#   upper arm / thigh:                    ~2 - 5 cm (deltoid mass; the blazer
#                                         hem flares 10 cm and is weighted to
#                                         UpLeg on purpose)
# Before the centring pass the shipped pack measured 1.6 -> 3.3 cm along the
# forearm (a drift toward the wrist) and the slim pack 3.8 - 4.0 cm.
_FOREARM_MAX_SLICE = 2.5      # cm, worst slab centre off the ForeArm axis
_FOREARM_MAX_DRIFT = 2.0      # cm, change in that offset along the segment
_CUFF_MAX = 1.5               # cm, sleeve ring centroid to the Hand pivot -
                              # the 2B reference's own cuff is 1.5 cm out
_CUT_CUFF_MAX = 2.4           # same, for the hand-cut pack (cuff stretched past
                              # the joint, so it is legitimately a little looser)
_CREASE_MAX = 3.5             # cm, elbow crease centroid to the ForeArm pivot
#: p90 arm thickness in the 2 cm band around the elbow, against the 2B
#: reference's 7.03 cm. The source arm simply is thicker at the joint than 2B's
#: (8.16 cm before ``trim_elbows``, 6.8 cm either side of it), so the pack is
#: held to "no worse than the reference, plus a little" rather than to parity.
_ELBOW_MAX_THICKNESS = 7.4    # cm


def _templates() -> Path:
    """The 2B reference pack (references/2b.rar), where extract_2b.py unpacks it."""
    import extract_2b

    if not extract_2b.present():
        pytest.skip(extract_2b.MISSING)
    return extract_2b.TEMPLATES


def _rest_template(which: str):
    """PD2 animation hierarchy with this pack's encoded authoring rest worlds."""
    from dataclasses import replace
    import build_models as bm

    template = bm.load_template(_templates() / "2b.model")
    _, pack_dir, item_id, _g = PACKS[which]
    with _zf(which) as zf:
        data = zf.read(f"{pack_dir}/assets/units/{item_id}/skins/"
                       f"{item_id}/{item_id}.model")
    drawn = bm.read_drawable(data, "g_body")
    worlds = dict(template.worlds)
    for name, world in drawn.get("rest_worlds", {}).items():
        if name in template.name_id:
            worlds[template.name_id[name]] = world
    return replace(template, worlds=worlds)


def _fit_report(which: str, fps: bool = False) -> dict:
    """segment_fit report for a built pack, against the PD2 bind skeleton."""
    import build_models as bm

    tpl = bm.load_template(_templates() / "2b.model")
    _, pack_dir, item_id, _g = PACKS[which]
    unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
    stem = f"fps_{item_id}" if fps else item_id
    with _zf(which) as zf:
        data = zf.read(f"{unit}/{stem}.model")
    return bm.segment_fit_report(data, tpl)


@pytest.mark.parametrize("which", sorted(PACKS))
@pytest.mark.parametrize("fps", [False, True], ids=["tpp", "fps"])
def test_limb_tubes_sit_on_their_bones(which, fps):
    """Both units: the forearm tube must wrap its bone axis.

    This is the diagnostic the preview overlays were showing by eye: with the
    tube off-axis the ``Arm``/``ForeArm`` bone runs along the edge of the
    sleeve instead of down the middle, and the offset grows toward the wrist.
    """
    rep = _fit_report(which, fps)
    segs = rep["segments"]
    for bone in ("LeftForeArm", "RightForeArm"):
        r = segs[bone]
        assert r["max"] <= _FOREARM_MAX_SLICE, (
            f"{which}/{'fps' if fps else 'tpp'} {bone}: worst cross-section "
            f"centre is {r['max']:.2f} cm off the bone axis "
            f"(limit {_FOREARM_MAX_SLICE})")
        assert r["drift"] <= _FOREARM_MAX_DRIFT, (
            f"{which}/{'fps' if fps else 'tpp'} {bone}: centre drifts "
            f"{r['drift']:.2f} cm along the segment (limit {_FOREARM_MAX_DRIFT})")


def _arm_radii_at_elbow(which: str, side: str = "Left") -> np.ndarray:
    """Inner (p10) and outer (p90) radii in the 2 cm elbow band.

    Measured along the encoded rest chain: its two segments meet at 12 degrees,
    so any window picked by one segment's axial coordinate catches the other
    one's cross-section too. Both tails matter: an outer-thickness limit alone
    allowed a corrective to pinch the inner elbow.
    """
    import numpy as np
    import segment_fit as sf

    tpl = _rest_template(which)
    chain = [sf.joint_pos(tpl, f"{side}{n}") for n in ("Arm", "ForeArm", "Hand")]
    s_joint = float(np.linalg.norm(chain[1] - chain[0]))
    v, dom = _g_body_geo_dom(which)
    m = np.array([nm in (f"{side}Arm", f"{side}ForeArm") and w > 0.2
                  for nm, w in dom])
    pts = v[m]
    best = np.full(len(pts), np.inf)
    arc = np.zeros(len(pts))
    acc = 0.0
    for a, b in zip(chain[:-1], chain[1:]):
        ab = b - a
        L = float(np.linalg.norm(ab))
        u = ab / L
        t = np.clip((pts - a) @ u, 0.0, L)
        d = np.linalg.norm(pts - (a + np.outer(t, u)), axis=1)
        better = d < best
        best = np.where(better, d, best)
        arc = np.where(better, t + acc, arc)
        acc += L
    band = (np.abs(arc - s_joint) < 2.0) & (best < 12)
    assert band.sum() >= 8, f"{which}: only {int(band.sum())} verts at the elbow"
    return np.percentile(best[band], [10, 90])


@pytest.mark.parametrize("which", sorted(PACKS))
def test_elbow_is_not_puffier_than_the_reference(which):
    """The elbow must not be the widest part of the arm.

    The DOA source thickens at the joint: 8.16 cm (p90) in the 2 cm band around
    the elbow against 6.8-7.3 cm either side of it, where PD2's own 2B body has
    7.03 cm there and 6.0-6.7 cm either side. ``trim_elbows`` squeezes the
    cross-section about the arm chain, which brings it to 7.18 cm without
    moving the crease (the crease test above still passes).
    """
    got = _arm_radii_at_elbow(which)[1]
    assert got <= _ELBOW_MAX_THICKNESS, (
        f"{which}: arm is {got:.2f} cm thick at the elbow (limit "
        f"{_ELBOW_MAX_THICKNESS}; 2B reference 7.03, was 8.16 before the trim)")


@pytest.mark.parametrize("which", sorted(PACKS))
@pytest.mark.parametrize("side", ("Left", "Right"))
def test_elbow_inner_sleeve_does_not_collapse(which, side):
    """The joint must retain a continuous sleeve, not just a valid outer bound.

    The rejected multi-pose corrective passed topology, normal, seam and outer
    thickness checks but visibly pinched both elbows in the bottom skeleton
    render. Its inner (p10) radius fell to 3.83 cm from the stable sleeve's
    4.35 cm. Check both arms and both packs so that failure cannot return
    unnoticed behind another aggregate fold metric.
    """
    got = _arm_radii_at_elbow(which, side)[0]
    assert got >= 4.0, (
        f"{which} {side}: inner elbow radius collapsed to {got:.2f} cm "
        "(minimum 4.00; stable sleeve approximately 4.35)")


@pytest.mark.parametrize("which", sorted(PACKS))
def test_elbow_creases_bend_at_the_pivot(which):
    """PD2 rotates about the ForeArm pivot; the mesh's crease has to be there."""
    rep = _fit_report(which)
    for joint in ("LeftForeArm", "RightForeArm"):
        assert rep["joints"][joint] <= _CREASE_MAX, (
            f"{which} {joint}: crease is {rep['joints'][joint]:.2f} cm from the "
            f"pivot (limit {_CREASE_MAX})")


@pytest.mark.parametrize("which", sorted(PACKS))
def test_forearm_tube_is_coaxial_with_the_bone(which):
    """The sleeve axis, not just the sleeve middle, has to be on the bone.

    Locks the 2026-11-06 rewrite of ``centre_segments``: the old pass faded the
    correction out toward the wrist (``smoothstep((L-t)/6)`` is 0.12 at the
    mouth) and moved each vertex by its own skin weight, so the *stacked*
    layers of a cross-section slid through each other. Both left the sleeve
    leaning: the slab centre walked from 1.6 cm at the elbow to 3.3 cm at the
    wrist and the cuff ring sat 2.2 cm off the ``Hand`` pivot. The pass is now
    weight-saturated and corrects to the mouth, which puts the drift under
    1.1 cm and the cuff under 1.5 cm on both packs.
    """
    for key in sorted(PACKS):
        rep = _fit_report(key)
        drifts = [rep["segments"][f"{s}ForeArm"]["drift"] for s in ("Left", "Right")]
        assert max(drifts) <= _FOREARM_MAX_DRIFT, (
            f"{key}: forearm centreline still drifts {max(drifts):.2f} cm along "
            f"the segment (limit {_FOREARM_MAX_DRIFT}) - the mouth is not being "
            f"corrected")


@pytest.mark.parametrize("which", sorted(PACKS))
def test_sleeve_end_surrounds_the_glove_spawn(which):
    """Where the in-game glove spawns: the sleeve opening must sit on it.

    The slim pack cuts the hands at the wrist and stretches the sleeve past the
    joint, so its cuff has to enclose the ``Hand`` pivot rather than float away
    from it.
    """
    rep = _fit_report(which)
    limit = _CUT_CUFF_MAX if PACKS[which][3] else _CUFF_MAX
    for key, d in rep["cuffs"].items():
        assert d is not None, f"{which}: no cuff ring found for {key}"
        assert d <= limit, f"{which} {key}: cuff is {d:.2f} cm from the pivot"


#: Known defect, not fixed: each slim sleeve is still open just past the elbow
#: (52-56 % of the way from shoulder to wrist, z 125.3-126.6 cm), where the two
#: rims carry no paired vertices for ``stitch_sleeve_seams`` to bridge
#: (tools/pd2-las/MODLOG.md, 2026-11-11). Leak in cm2 by (pack, side), measured
#: on the tracked zip.
#:
#: For these cases ``test_sleeve_tube_is_closed_along_its_length`` is an expected
#: failure, so the suite is green with a known defect in it. Four things keep
#: that from becoming a place to hide one (docs/pd2-las/DECISIONS.md, D18):
#:   * the expectation is strict: the day a sleeve closes, its case turns red
#:     (XPASS) until its entry here is deleted;
#:   * only an AssertionError is expected: a measurement that breaks still fails;
#:   * ``test_known_sleeve_leak_does_not_grow`` fails if a leak gets worse;
#:   * tools/pd2-port/check_skip_budget.py fails on any expected failure that is
#:     not one of these.
KNOWN_SLEEVE_LEAK_CM2 = {("slim", -1): 6.70, ("slim", 1): 4.95}


@functools.lru_cache(maxsize=None)
def _sleeve_leak(which: str, side: int) -> dict:
    """``diagnose_mesh.sleeve_slit_area`` of one sleeve (-1 left, +1 right) of a pack."""
    import build_models as bm
    import diagnose_mesh as dg

    path = REPO / PACKS[which][0]
    _zf(which).close()                      # skip cleanly when not built
    pack_dir, item_id = PACKS[which][1], PACKS[which][2]
    template = bm.load_template(_templates() / "2b.model")
    p = dg.load(path, pack_dir, item_id)
    joints = dg.joints_of(path, item_id, template)
    return dg.sleeve_slit_area(p, joints, side)


def _sleeve_cases():
    """(side, which) for every sleeve of every pack; the known-open ones are expected to fail."""
    for which in sorted(PACKS):
        for side in (-1, 1):
            known = KNOWN_SLEEVE_LEAK_CM2.get((which, side))
            marks = () if known is None else pytest.mark.xfail(
                raises=AssertionError, strict=True,
                reason=f"known defect: this sleeve is still open ({known:.2f} cm2 leak, "
                       "KNOWN_SLEEVE_LEAK_CM2)")
            yield pytest.param(side, which, marks=marks)


@pytest.mark.parametrize("side, which", list(_sleeve_cases()))
def test_sleeve_tube_is_closed_along_its_length(which, side):
    """The sleeve's zero-width seam must be stitched shut, not just merged.

    Both packs ship the upper sleeve as a tube whose lengthwise seam is a
    *slit*: the two rims carry separate vertices, so the surface is open even
    though the gap between them is 0 cm (docs/audits/2026-11-07-christie-slim-
    diagnosis.md, item 2). A ray cast radially from the shoulder->wrist bone
    chain therefore escapes through it: 35.1 cm2 on the slim left sleeve, 5.0
    on the slim right, 21.5 on the base left, 0.0 on the base right (whose
    slit happens to sit under an overlapping layer). In game that reads as a
    dark stripe down the sleeve. `stitch_sleeve_seams` closes the tube, and a
    closed tube leaks nothing at all.

    The base pack is there. The slim pack is not: its two cases are expected
    failures, see ``KNOWN_SLEEVE_LEAK_CM2``.
    """
    s = _sleeve_leak(which, side)
    name = "left" if side < 0 else "right"
    assert s["cm2"] < 1.0, (
        f"{which} {name} sleeve leaks {s['cm2']:.2f} cm2 of ray samples "
        f"through its seam (s, z, cm2: {s['slices'][:3]}); the stitch pass "
        "is not closing the slit")


@pytest.mark.parametrize("which, side", sorted(KNOWN_SLEEVE_LEAK_CM2))
def test_known_sleeve_leak_does_not_grow(which, side):
    """An expected failure may get better, never worse.

    ``xfail`` accepts any failure of the assertion above, so on its own it
    would also accept the slit reopening down the whole sleeve (35.1 cm2 before
    the stitch pass). This holds each known-open sleeve to the leak recorded
    for it, with half a square centimetre of slack for a grazing ray or two:
    one more open slice adds about 1.65 cm2.
    """
    leak = _sleeve_leak(which, side)
    known = KNOWN_SLEEVE_LEAK_CM2[(which, side)]
    name = "left" if side < 0 else "right"
    assert leak["cm2"] <= known + 0.5, (
        f"{which} {name} sleeve leaks {leak['cm2']:.2f} cm2, more than the "
        f"{known:.2f} cm2 recorded as its known defect (s, z, cm2: "
        f"{leak['slices'][:6]}): the seam got worse")


@pytest.mark.parametrize("which", sorted(PACKS))
def test_sleeve_gloss_mask_stays_on_the_sleeve(which):
    """The specular attenuation may only land on texels the sleeve samples.

    The first pass punched a 24-texel disc around every arm-weighted vertex.
    Measured off the shipped packs, that mask reached **3.2 %** of the leg
    faces' UV area over **151** faces, 123 of them at z 0-20 cm - the boots
    (docs/audits/2026-11-07-christie-slim-diagnosis.md, item 6). The block
    quantisation of that edge is what the screenshots show as stair-stepped
    blotches on the trousers.

    ``sleeve_uv_mask`` rasterises the sleeve's own UV triangles and clips the
    feather to that footprint, so the only faces it can still reach are ones
    whose UVs genuinely sit inside a sleeve island. ``retouch_sleeve_gloss``
    then attenuates mip 0 and rebuilds the pyramid from it, so the mask edge
    cannot grow with distance; both are pinned here.
    """
    import build_christie_las as bcl
    import diagnose_mesh as dg

    pd2_dds = bcl.pd2_dds

    path = REPO / PACKS[which][0]
    pack_dir, item_id = PACKS[which][1], PACKS[which][2]
    zf = _zf(which)
    try:
        name = next(n for n in zf.namelist()
                    if n.endswith(f"{item_id}_c02_01_df.texture"))
        blob = zf.read(name)
    finally:
        zf.close()

    p = dg.load(path, pack_dir, item_id)
    faces, fmat, uvs, verts = p["faces"], p["fmat"], p["uv"], p["verts"]
    arm_w = p["w"]["arm"]
    role = "mtr_c02_01"
    sleeve = [fi for fi in np.where(fmat == role)[0]
              if float(arm_w[faces[fi]].mean()) > bcl.SLEEVE_BONE_SHARE]
    assert len(sleeve) > 500, f"{which}: only {len(sleeve)} sleeve faces found"

    mask = bcl.sleeve_uv_mask(uvs, [faces[fi] for fi in sleeve],
                              feather_texels=bcl.SLEEVE_FEATHER_TEXELS)

    def centroid(fi: int) -> tuple[float, float]:
        c = bcl.uv_to_texel_frac(uvs[faces[fi]].mean(axis=0))
        return float(c[0]), float(c[1])

    def uva(fi) -> float:
        t = uvs[faces[fi]]
        return 0.5 * abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1])
                         - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1]))

    def coverage(indices) -> tuple[float, int, float]:
        """(area share, count, max z) of the masked faces among ``indices``."""
        total_area = sum(uva(fi) for fi in indices)
        if total_area <= 0.0:
            return 0.0, 0, 0.0
        hit_area = 0.0
        count = 0
        zs = []
        for fi in indices:
            x, y = centroid(fi)
            if mask[int(np.clip(y * 1023, 0, 1023)),
                    int(np.clip(x * 1023, 0, 1023))] > 0.05:
                hit_area += uva(fi)
                count += 1
                zs.append(float(verts[faces[fi], 2].mean()))
        return hit_area / total_area, count, max(zs) if zs else 0.0

    covered, _sleeve_count, _ = coverage(sleeve)
    assert covered >= 0.99, f"{which}: mask misses {1 - covered:.1%} of the sleeve"

    # Gate 1 -- the trousers and the seat must be untouched. The shipped pack
    # darkened 402 of the 630 faces at z in [20, 60) cm before this was fixed.
    leg_w = p["w"]["leg"]
    trouser = [fi for fi in np.where(fmat == role)[0]
               if float(leg_w[faces[fi]].mean()) > 0.5
               and float(arm_w[faces[fi]].mean()) < 0.1
               and 20.0 < float(verts[faces[fi], 2].mean()) < 60.0]
    assert trouser, f"{which}: no trouser faces found to gate"
    t_share, t_count, _ = coverage(trouser)
    assert t_count == 0, (
        f"{which}: gloss mask reaches {t_count} trouser faces at z in [20, 60) cm")

    # Gate 2 -- DOA5 shares the boot / ankle-strap islands with the sleeve cuff
    # trim, so a few feathered faces are expected, but every leg-weighted hit
    # must be down at the boot.
    leg = [fi for fi in np.where(fmat == role)[0]
           if float(leg_w[faces[fi]].mean()) > 0.5
           and float(arm_w[faces[fi]].mean()) < 0.1]
    share, count, max_z = coverage(leg)
    assert share < 0.010, (
        f"{which}: mask covers {share:.2%} of the leg-only UV area over "
        f"{count} faces (fixed expectation 0.79% / 34; the buggy mask scores "
        f"37.33% / 627 with 564 of them above z=20 cm)")
    assert count <= 60, f"{which}: mask touches {count} leg-only faces"
    assert max_z < 20.0, (
        f"{which}: a leg-weighted face at z={max_z:.1f} cm is attenuated")

    # Texture check: sleeve vs trouser specular alpha in the shipped mip 0.
    size, mips, mip0 = pd2_dds.dds_mip0_slice(blob)
    assert size == 1024 and mips == 11
    alpha = pd2_dds.decode_dxt5(mip0, size, size)[..., 3].astype(np.float64)

    def mean_alpha(indices):
        return float(np.mean([
            alpha[int(np.clip(y * (size - 1), 0, size - 1)),
                  int(np.clip(x * (size - 1), 0, size - 1))]
            for x, y in (centroid(fi) for fi in indices)]))

    sleeve_mu = mean_alpha(sleeve)
    trouser_mu = mean_alpha(trouser)
    assert 5.4 <= sleeve_mu <= 6.5, (
        f"{which}: sleeve specular alpha {sleeve_mu:.2f} outside [5.4, 6.5]")
    assert 11.0 <= trouser_mu <= 11.7, (
        f"{which}: trouser specular alpha {trouser_mu:.2f} outside [11.0, 11.7]")
    assert sleeve_mu < 0.60 * trouser_mu, (
        f"{which}: sleeve specular alpha {sleeve_mu:.2f} vs trousers "
        f"{trouser_mu:.2f} - the attenuation is not on the sleeve")


def test_uv_to_texel_frac_matches_udim_wrap_for_both_tile_signs():
    """Both UDIM tile signs must map to the same top-down row.

    The stored v of a top-down-authored atlas is ``1 - v_src``. A tile at
    ``v_src = 1.62`` stores ``v = -0.62``; a tile at ``v_src = 0.62`` stores
    ``v = 0.38``. Under D3D9 Wrap both must sample row ``0.62`` -- the mirror
    ``1 - mod(-v, 1) == mod(v, 1)`` was the shipped bug.
    """
    import build_christie_las as bcl

    v_src = 0.62
    negative_tile = np.array([[0.25, -v_src]])      # v_src = 1.62 -> stored v = -0.62
    positive_tile = np.array([[0.25, 1.0 - v_src]]) # v_src = 0.62 -> stored v = 0.38
    a = bcl.uv_to_texel_frac(negative_tile)
    b = bcl.uv_to_texel_frac(positive_tile)
    assert np.allclose(a, b), (a, b)
    assert abs(float(a[0, 1]) - v_src) < 1e-9, a


@pytest.mark.parametrize("which", sorted(PACKS))
def test_interior_coincident_normals_agree(which):
    """A duplicated vertex must shade as one vertex (work order item 1).

    PD2 meshes split vertices at UV and material seams, so one position carries
    several copies. The 2B reference carries 22,486 such pairs and **none** of
    them disagrees by more than 30 degrees - that is why its seams are
    invisible. Ours used to diverge on 480 (slim) / 856 (base) pairs, which
    shades as a hard step along every seam; `unify_coincident_normals` gives
    the *interior* copies one shared normal and leaves the copies that sit on a
    garment edge alone, because those are a real fold.
    """
    import build_christie_las as bcl
    import build_models as bm
    import diesel_model as dm
    import render_mesh_skeleton as rms

    pack_dir, item_id = PACKS[which][1], PACKS[which][2]
    with _zf(which) as zf:
        geo = rms.g_body_geo(zf, pack_dir, item_id)
    g = bm.Group(name="body",
                 verts=[tuple(map(float, v)) for v in geo["verts"]],
                 normals=[tuple(map(float, n)) for n in geo["normals"]],
                 faces=[tuple(map(int, f)) for f in geo["faces"]])
    report = bcl.coincident_normal_report(g)
    assert report["interior"] == 0, (
        f"{which}: {report['interior']} interior coincident pairs still "
        "disagree on their normal (the 2B reference has 0)")
    # ...and the pass must not have blanket-smoothed genuine folds: every
    # remaining divergence has to sit on a border edge.
    assert report["border"] > 300, (
        f"{which}: only {report['border']} border pairs diverge - a garment "
        "edge lost its hard normal, which means the pass went too far")

    # Reference anchor: the 2B body agrees everywhere, border included.
    mf = dm.ModelFile.read((_templates() / "2b.model").read_bytes())
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    for section in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(section.payload)
        if next((n for n in hl if dm.hash64(n) == md["name_hash"]), "") != "g_body":
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo2 = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        top2 = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        ref = bm.Group(name="2b",
                       verts=[tuple(map(float, v)) for v in geo2["verts"]],
                       normals=[tuple(map(float, n)) for n in geo2["normals"]],
                       faces=[tuple(map(int, f)) for f in
                              np.asarray(top2["indices"], int).reshape(-1, 3)])
        ref_report = bcl.coincident_normal_report(ref)
        assert ref_report == {"interior": 0, "border": 0, "pairs": 0}, ref_report
        break


def test_fit_numbers_match_the_build_report():
    """The numbers BUILD_INFO records from the build and the ones measured here
    on the shipped .model must agree — catches a stale dist/ artefact."""
    for which in sorted(PACKS):
        _, pack_dir, _item, _g = PACKS[which]
        with _zf(which) as zf:
            info = json.loads(zf.read(f"{pack_dir}/BUILD_INFO.json"))
        built = info.get("fit_tpp")
        assert built, f"{which}: BUILD_INFO has no fit_tpp (rebuild the pack)"
        measured = _fit_report(which)
        assert abs(built["worst_segment_offset"]
                   - measured["worst_segment_offset"]) < 1e-6


# ---------------------------------------------------------------------------
# Elbow deformation from the encoded 12-degree authoring rest. The old 72-
# degree menu pose is now a flexion of the rest skeleton, not its identity.
# Probes use the same posed_worlds / skin_verts LBS as the diagnostic renderer.
# Local X twists the ForeArm; local Y changes the Arm-ForeArm flexion angle.
# ---------------------------------------------------------------------------
_BEND_AXIS = 1          # ForeArm/Hand local axis that changes the joint angle
_BIND_ELBOW_DEG = 72.0  # old PD2 template/menu pose, now a 60-degree flexion
#: rotation from the encoded rest: 0 = old menu pose, 60 = idle identity,
#: 72 = straightened extension probe. These remain template-relative angles.
_STRAIGHTEN = (0, 22, 45, 60, 72)


def _elbow_angle(pw, template) -> float:
    import numpy as np

    A, E, H = (np.array(pw[template.name_id[f"Left{n}"]][12:15], float)
               for n in ("Arm", "ForeArm", "Hand"))
    u1 = (E - A) / np.linalg.norm(E - A)
    u2 = (H - E) / np.linalg.norm(H - E)
    return float(np.degrees(np.arccos(np.clip(u1 @ u2, -1, 1))))


def _hang_pose_metrics(which: str, straighten_deg: int) -> dict:
    """Edge compression + opposed-normal pairs inside the weld ring when the
    elbow is straightened from the bind bend toward the in-game idle."""
    import numpy as np

    import diesel_model as dm
    import build_models as bm
    import render_mesh_skeleton as rms

    pack_dir, item_id = PACKS[which][1], PACKS[which][2]
    with _zf(which) as zf:
        geo = rms.g_body_geo(zf, pack_dir, item_id)
        mf = dm.ModelFile.read(
            zf.read(f"{pack_dir}/assets/units/{item_id}/skins/"
                    f"{item_id}/{item_id}.model"))
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    skel = None
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
        if name == "g_body" and md.get("version") == 3:
            skel = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
            break
    template = bm.load_template(_templates() / "2b.model")

    v = np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    bw = np.array(geo["blendweights"], float)
    bi = np.array(geo["blendindices"], int)
    pal = skel["objects"]
    name_of = {sid: template.id_name[sid] for sid in template.id_name}
    w_arm = np.zeros(len(v))
    w_fa = np.zeros(len(v))
    for i in range(len(v)):
        for k, w in enumerate(bw[i]):
            if w <= 0.0:
                continue
            pi = int(bi[i][k])
            if pi >= len(pal):
                continue
            n = name_of.get(pal[pi])
            if n == "LeftArm":
                w_arm[i] += w
            elif n == "LeftForeArm":
                w_fa[i] += w
    ring = np.where((w_arm > 0.02) & (w_fa > 0.02) & (w_arm + w_fa > 0.5))[0]
    ringset = set(ring.tolist())
    coincident = {}
    for i, p in enumerate(v):
        if w_arm[i] + w_fa[i] > 0.5:
            coincident.setdefault(tuple(np.round(p, 4)), []).append(i)
    seam_groups = [np.array(ids, int) for ids in coincident.values() if len(ids) > 1]

    # blend width along the Shoulder->Arm->ForeArm->Hand chain, bind pose
    bones = dict((n, p) for n, p, _ in rms.rest_skeleton(template, skel))
    pts = [bones[f"Left{n}"] for n in ("Shoulder", "Arm", "ForeArm", "Hand")]
    cum = np.concatenate([[0.0], np.cumsum([float(np.linalg.norm(b - a))
                                            for a, b in zip(pts[:-1], pts[1:])])])
    arc = np.full(len(v), -1.0)
    dmin = np.full(len(v), 1e9)
    for si, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        ab = b - a
        t = np.clip((v - a) @ ab / (ab @ ab), 0, 1)
        d = np.linalg.norm(v - (a + t[:, None] * ab), axis=1)
        upd = d < dmin
        dmin[upd] = d[upd]
        arc[upd] = cum[si] + t[upd] * float(np.sqrt(ab @ ab))
    span = float(arc[ring].max() - arc[ring].min())

    pose = {f"{s}Arm": (2, 22) for s in ("Left", "Right")}
    pose.update({f"{s}ForeArm": (_BEND_AXIS, -straighten_deg) for s in ("Left", "Right")})
    pose.update({f"{s}Hand": (_BEND_AXIS, -8) for s in ("Left", "Right")})
    pw = rms.posed_worlds(template, pose)
    pv = rms.skin_verts(geo, skel, pw)
    seam_gap = 0.0
    for ids in seam_groups:
        pts = pv[ids]
        seam_gap = max(seam_gap, float(np.linalg.norm(
            pts[:, None, :] - pts[None, :, :], axis=2).max()))

    edges = set()
    for tri in faces:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ia, ib = int(tri[a]), int(tri[b])
            if ia in ringset or ib in ringset:
                edges.add((min(ia, ib), max(ia, ib)))
    e = np.array(sorted(edges), int)
    lb = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    lp = np.linalg.norm(pv[e[:, 0]] - pv[e[:, 1]], axis=1)
    ok = lb > 1e-9
    ratio = lp[ok] / lb[ok]
    shortening = np.maximum(lb - lp, 0.0)[ok]

    n = np.cross(pv[faces[:, 1]] - pv[faces[:, 0]], pv[faces[:, 2]] - pv[faces[:, 0]])
    nl = np.linalg.norm(n, axis=1)
    good = nl > 1e-12
    n = n[good] / nl[good][:, None]
    fg = faces[good]
    em = {}
    for t in range(len(fg)):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            k = (min(int(fg[t][a]), int(fg[t][b])), max(int(fg[t][a]), int(fg[t][b])))
            em.setdefault(k, []).append(t)
    flips = 0
    for k, ts in em.items():
        if len(ts) == 2 and (ringset & {int(fg[ts[0]][0]), int(fg[ts[0]][1]),
                                        int(fg[ts[1]][0]), int(fg[ts[1]][1])}):
            if float(np.dot(n[ts[0]], n[ts[1]])) < -0.5:
                flips += 1
    return dict(blend_span_cm=span, ring=len(ring),
                min_ratio=float(ratio.min()),
                frac_lt_070=float((ratio < 0.70).mean()),
                crease_pairs=flips,
                elbow_deg=_elbow_angle(pw, template),
                seam_gap_max=seam_gap,
                shorten_max=float(shortening.max()),
                shorten_sum=float(shortening.sum()))


@pytest.mark.parametrize("which", sorted(PACKS))
def test_elbow_bend_axis_is_flexion(which):
    """Local Y of the PD2 ForeArm must be the elbow's flexion axis.

    Pins the distinction the whole probe rests on: rotating about local X
    leaves the Arm-ForeArm angle at its bind 72.1 deg (it swings the forearm
    on a cone - a twist of the sleeve), while local Y moves it 1:1. The
    2026-11-06 round measured the X pose, so it tuned the weights against a
    twisted sleeve; this test stops that from silently recurring.
    """
    import build_models as bm
    import numpy as np
    import render_mesh_skeleton as rms

    template = bm.load_template(_templates() / "2b.model")
    bind = np.degrees(np.arccos(np.clip(
        _unit(pw_joint(template, "LeftArm"), pw_joint(template, "LeftForeArm")) @
        _unit(pw_joint(template, "LeftForeArm"), pw_joint(template, "LeftHand")), -1, 1)))
    assert abs(bind - _BIND_ELBOW_DEG) < 1.0, f"bind elbow is {bind:.1f} deg"
    for deg in (-40, -60, -72):
        pw = rms.posed_worlds(template, {f"{s}ForeArm": (_BEND_AXIS, deg)
                                        for s in ("Left", "Right")})
        got = _elbow_angle(pw, template)
        assert abs((bind + deg) - got) < 1.5, (
            f"ForeArm local Y {deg:+d} deg gives a {got:.1f} deg elbow; "
            f"expected {bind + deg:.1f}")
        pw_x = rms.posed_worlds(template, {f"{s}ForeArm": (0, deg)
                                          for s in ("Left", "Right")})
        assert abs(_elbow_angle(pw_x, template) - bind) < 0.5, (
            "ForeArm local X changed the elbow angle - the axis constants in "
            "render_mesh_skeleton.BEND_AXIS no longer describe this rig")


def pw_joint(template, name):
    import numpy as np
    w = template.worlds[template.name_id[name]]
    return np.array(w[12:15], float)


def _unit(a, b):
    import numpy as np
    d = b - a
    return d / np.linalg.norm(d)


@pytest.mark.parametrize("which", sorted(PACKS))
def test_idle_rest_worlds_survive_tpp_and_fps(which):
    """FPS extraction must retain the exact custom inverse-bind arm worlds."""
    import build_models as bm
    import render_mesh_skeleton as rms

    _, pack_dir, item_id, _g = PACKS[which]
    unit = f"{pack_dir}/assets/units/{item_id}/skins/{item_id}"
    with _zf(which) as zf:
        tpp = bm.read_drawable(zf.read(f"{unit}/{item_id}.model"), "g_body")
        fps = bm.read_drawable(zf.read(f"{unit}/fps_{item_id}.model"), "g_body")
    assert tpp and fps
    template = bm.load_template(_templates() / "2b.model")
    for side in ("Left", "Right"):
        for part in ("Arm", "ForeArm", "Hand"):
            name = f"{side}{part}"
            a = np.asarray(tpp["rest_worlds"][name], float)
            b = np.asarray(fps["rest_worlds"][name], float)
            assert np.allclose(a, b, atol=2e-5), name
            assert np.max(np.abs(a - template.worlds[template.name_id[name]])) > 0.01
    # Renderer rest overlays use the shipped inverse binds, not stale PD2 worlds.
    bones = dict((name, point) for name, point, _parent in
                 rms.rest_skeleton(template, {
                     "objects": [template.name_id[name] for name in tpp["palette"]],
                     "rotations": [np.linalg.inv(np.asarray(
                         tpp["rest_worlds"][name], float).reshape(4, 4)).reshape(-1).tolist()
                         for name in tpp["palette"]],
                 }))
    for name in ("LeftForeArm", "RightForeArm"):
        assert np.allclose(bones[name], tpp["rest_worlds"][name][12:15], atol=1e-5)


@pytest.mark.parametrize("which", sorted(PACKS))
def test_elbow_blend_is_wide(which):
    """The weld ring must span >= 10.8 cm of arm chain with >= 72 mixed verts.

    Shipped 2026-11-05 state: 9.4 cm / 64 verts on both packs - a narrow,
    steep weight step at the joint. The 2B reference body: 16.2 cm / 331.
    widen_elbow_blend re-splits 7 cm proximal + 9 cm distal of the pivot; the
    measured ring is ~12 cm / 83 verts (verts near the window edges get
    cross-weights under the 0.02 mix threshold, so the span is shorter than
    the nominal 16 cm window).
    """
    m = _hang_pose_metrics(which, 0)
    assert m["blend_span_cm"] >= 10.8, (
        f"{which}: elbow blend spans {m['blend_span_cm']:.1f} cm "
        f"(needs >= 10.8, was 9.4 before widen_elbow_blend)")
    assert m["ring"] >= 72, f"{which}: only {m['ring']} mixed-weight verts"


@pytest.mark.parametrize("which", sorted(PACKS))
def test_elbow_deforms_cleanly_from_idle_rest(which):
    """The 12-degree idle is the identity bind; flexion must not crumple it.

    Older packs authored a 72-degree rest elbow and had to straighten it by
    60 degrees before the first idle frame. The shipped skinbones now author
    the same near-idle pose as this probe's 60-degree row, so that row must be
    an exact no-op on the elbow ring. The 0-degree row flexes *into* the old
    menu pose; 72 extends 12 degrees beyond idle. All use original rest edge
    lengths and the shipped linear-blend matrices.
    """
    at0 = _hang_pose_metrics(which, 0)
    at45 = _hang_pose_metrics(which, 45)
    at50 = _hang_pose_metrics(which, 50)
    at60 = _hang_pose_metrics(which, 60)
    at72 = _hang_pose_metrics(which, 72)
    assert abs(at60["elbow_deg"] - 12.0) < 1.0, (
        f"{which}: the probe straightens to {at60['elbow_deg']:.1f} deg, not "
        "the idle's 12 deg")
    # Idle rest is identity: no compressed edge and no new opposed normals.
    assert at60["min_ratio"] > 0.99 and at60["shorten_max"] < 0.01
    # Rest can already contain opposed normals where lining/garment panels
    # meet; the deformation must not create additional opposed face pairs.
    rest_creases = at60["crease_pairs"]
    # The menu row is *maximum* flexion (the old 72-degree bind): the fabric
    # has to double back inside the crease there, and the source already folds
    # on a few edges (base rest 3, menu 5). stitch_sleeve_seams closes the
    # inner-elbow patch, so that patch joins the same fold (base menu 5 -> 7,
    # slim 1 -> 4) while every other row stays put. Give the menu row a wider
    # budget; the in-game rows keep the tight one.
    for label, metrics in (("menu", at0), ("27deg", at45), ("22deg", at50),
                           ("idle", at60), ("straight", at72)):
        assert metrics["seam_gap_max"] < 0.02, (
            f"{which} {label}: coincident sleeve vertices separate by "
            f"{metrics['seam_gap_max']:.3f} cm")
        budget = rest_creases + (5 if label == "menu" else 2)
        assert metrics["crease_pairs"] <= budget, (
            f"{which} {label}: {metrics['crease_pairs']} opposed face pairs at "
            f"the elbow ring (rest {rest_creases}, budget {budget})")
    # Near-idle flexion: measured base/slim minima are 0.70/0.71 at 27 deg
    # and 0.795/0.803 at 22 deg. Inner-crease edges naturally shorten here;
    # the hard continuity requirement above is the more important invariant.
    assert at45["min_ratio"] >= 0.65
    assert at45["shorten_max"] <= 1.20
    assert at50["min_ratio"] >= 0.75
    assert at50["shorten_max"] <= 0.85
    # Straightening the remaining 12 degrees must not introduce a new fold.
    assert at72["min_ratio"] >= 0.70
    assert at72["shorten_max"] <= 0.60


@pytest.mark.parametrize("which", sorted(PACKS))
@pytest.mark.parametrize("side", ("Left", "Right"))
def test_elbow_closeup_depth_has_no_false_holes(which, side, tmp_path):
    """The 50-degree side review must not cut an enclosed black hole.

    The near-shell camera-depth band must retain continuous sleeve coverage.
    Widening the band is not a valid fix: it can cover a genuine gap with
    unrelated far-side body faces. Internal background components larger than
    500 pixels catch a recurrence without mistaking the exterior silhouette
    for a mesh hole.
    """
    import build_models as bm
    import render_mesh_skeleton as rms
    from elbow_before_after import load_pack, pose_for, window_for
    from review_christie_idle import material_subset
    from scipy import ndimage

    _, pack, item, _g = PACKS[which]
    geo, skel = load_pack(Path(PACKS[which][0]), pack, item)
    template = bm.load_template(_templates() / "2b.model")
    worlds, bones = pose_for(template, -22)
    posed = rms.skin_verts(geo, skel, worlds)
    pivot = np.array(worlds[template.name_id[f"{side}ForeArm"]][12:15], float)
    if side == "Right":
        posed[:, 0] *= -1.0
        pivot[0] *= -1.0
    window, _ = window_for([posed], pivot, "side", 6.5)
    depth = float(rms.depth_towards_camera("side", np.atleast_2d(pivot))[0])
    out = tmp_path / "elbow.png"
    # No skeleton overlay: the overlay is drawn *over* the mesh, so its lines
    # can enclose a patch of background that no triangle closes and the
    # component detector below then reports it as a hole. That is what a
    # 2026-11-10 pass did to this test (three packs, >1 900 px regions) while
    # the mesh itself had no enclosed background at all. The invariant is about
    # the sleeve, so render the sleeve alone.
    rms.render(material_subset(geo, "mtr_c02_01"), [], "side", out,
               zoom=window, verts=posed, depth=(depth - 9, depth + 9))
    from PIL import Image
    pixels = np.asarray(Image.open(out).convert("RGB"))
    dark = pixels.max(axis=2) < 45
    dark[:70] = False  # renderer legend is an intentional dark rectangle
    labels, _ = ndimage.label(dark)
    border = set(np.unique(np.concatenate(
        [labels[0], labels[-1], labels[:, 0], labels[:, -1]])).tolist())
    internal = [i for i in np.unique(labels) if i and i not in border]
    holes = [(i, int((labels == i).sum())) for i in internal
             if (labels == i).sum() > 500]
    assert not holes, f"{which} {side}: enclosed background regions: {holes}"


def _model_rel(which: str, fps: bool = False) -> str:
    pack_dir = PACKS[which][1]   # e.g. "Christie_LAS_Slim"
    item_dir = PACKS[which][2]   # e.g. "christie_slim"
    stem = f"fps_{item_dir}" if fps else item_dir
    return f"{pack_dir}/assets/units/{item_dir}/skins/{item_dir}/{stem}.model"


_DRAWABLE_NAMES = ("g_body", "g_body_lod1", "s_body",
                   "fps_christie", "fps_christie_slim",
                   "fps_christie_lod1", "fps_christie_slim_lod1")


def _model_atoms(zip_path: Path, model_rel: str):
    """Yield (drawable_name, idx, atoms) for every atomised drawable.

    `idx` is the flat index buffer and `atoms` the drawable's list of
    {base_vertex, slice_len, base_index, tri_count} render-atom descriptions.
    The drawable name is resolved from the model_data name hash.
    """
    sys.path.insert(0, str(REPO / "tools" / "pd2-port"))
    import diesel_model as dm
    from diesel_model import decode_model_data, decode_passthroughgp
    from dmodel import DieselModel

    name_by_hash = {dm.hash64(n): n for n in _DRAWABLE_NAMES}
    with zipfile.ZipFile(zip_path) as zf:
        raw = zf.read(model_rel)
    mf = DieselModel.from_bytes(raw)
    for s in mf.sections:
        if s.tag != "model_data" or s.obj is None:
            continue
        md = decode_model_data(raw[s.start:s.end])
        if "atoms" not in md:
            continue
        pt = mf.by_id.get(md["passthroughgp"])
        if pt is None or pt.obj is None:
            continue
        pg = decode_passthroughgp(raw[pt.start:pt.end])
        gs = mf.by_id.get(pg["geometry"])
        ts = mf.by_id.get(pg["topology"])
        if gs is None or ts is None or gs.obj is None or ts.obj is None:
            continue
        idx = np.asarray(dm.decode_topology(raw[ts.start:ts.end])["indices"],
                         np.int64)
        yield name_by_hash.get(md["name_hash"]), idx, md["atoms"]


def _atom_oob(atoms, idx) -> list[tuple[int, int, int, int, int]]:
    """(atom_index, base_vertex, block_end, lo, hi) for each atom indexing out."""
    bad = []
    for ai, a in enumerate(atoms):
        bv, sl, tc, bi = (a["base_vertex"], a["slice_len"], a["tri_count"],
                          a["base_index"])
        seg = idx[bi:bi + tc * 3]
        end = bv + sl
        if int(((seg < bv) | (seg >= end)).sum()):
            bad.append((ai, bv, end, int(seg.min()), int(seg.max())))
    return bad


@pytest.mark.parametrize("which", sorted(PACKS))
def test_no_atom_indexes_outside_its_vertex_block(which):
    """An atom's index run must not reference another material slice's block.

    s_body's atom 0 on both shipped packs draws 16 whole triangles (48 indices)
    that live inside atom 1's vertex block - 730 (slim) / 919 (base) vertices
    past its own block. D3D9 binds the index buffer with the atom's vertex
    block, so that is an out-of-range sample no offline preview can see.
    """
    bad = []
    for name, idx, atoms in _model_atoms(DIST / PACKS[which][0],
                                         _model_rel(which)):
        for ai, bv, end, lo, hi in _atom_oob(atoms, idx):
            bad.append((name, ai, bv, end, lo, hi))
    assert not bad, (
        f"{which}: atom(s) index outside their vertex block: {bad}")


@pytest.mark.parametrize("which", sorted(PACKS))
def test_fps_shadow_and_body_share_the_same_triangle_runs(which):
    """FPS s_body and g_body share one index buffer at different vertex counts,
    so their atom triangle runs must agree or the shared stream is misread."""
    seen: dict[str, list[tuple[int, int]]] = {}
    for name, _idx, atoms in _model_atoms(DIST / PACKS[which][0],
                                          _model_rel(which, fps=True)):
        if name in ("s_body", "g_body"):
            seen[name] = [(a["base_index"], a["tri_count"]) for a in atoms]
    assert set(seen) == {"s_body", "g_body"}, (
        f"{which}: FPS missing s_body/g_body: {sorted(seen)}")
    assert seen["s_body"] == seen["g_body"], (
        f"{which}: FPS atom runs differ: "
        f"s_body={seen['s_body']} g_body={seen['g_body']}")
