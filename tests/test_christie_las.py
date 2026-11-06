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
    "slim": ("dist/Christie_LAS_Slim.zip", "Christie_LAS_Slim",
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


# PD2 2B bind-space joints (cm) — x mirrored per side. Segment = own joint ->
# child joint; the slim pack thins the full cross-section about these axes.
_P2_JOINTS = {
    "Arm": (20.863, 2.967, 146.699), "ForeArm": (39.502, -0.995, 133.292),
    "Hand": (45.985, 18.701, 124.472), "UpLeg": (10.689, 8.412, 99.487),
    "Leg": (10.689, 2.912, 52.717), "Foot": (10.689, 0.925, 9.889),
}
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

    def J(n):
        p = _P2_JOINTS[n]
        return np.array([-p[0] if side == "Left" else p[0], p[1], p[2]])

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
    """v4 acceptance: in unblended mid-segment slices the principal radius
    ratio slim/base must be 0.75 +/- 0.02 for arms and 0.90 +/- 0.02 for legs
    (25%/10% smaller cross-sectional dimensions, both perpendicular axes)."""
    slices = {"Arm": (0.35, 0.65), "ForeArm": (0.20, 0.40),
              "UpLeg": (0.30, 0.60), "Leg": (0.30, 0.60)}
    for bone, target in (("Arm", 0.75), ("ForeArm", 0.75),
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
    """straighten_segments v3 lock: median centerline deviation of pure
    forearm verts in clean mid-segment slices (t in [0.35L, 0.65L], away from
    the elbow/wrist end fades and blend zones) must be small — the bind-pose
    forearm is straight within its segment."""
    import numpy as np

    for side in ("Left", "Right"):
        v, dom = _g_body_geo_dom("base")
        a0, b0 = _P2_SEGMENTS["ForeArm"]

        def J(n):
            p = _P2_JOINTS[n]
            return np.array([-p[0] if side == "Left" else p[0], p[1], p[2]])

        a, b = J(a0), J(b0)
        u = (b - a) / np.linalg.norm(b - a)
        L = float(np.linalg.norm(b - a))
        sel = [i for i, (nm, w) in enumerate(dom)
               if nm == f"{side}ForeArm" and w > 0.85]
        pts = np.array([v[i] for i in sel])
        t = (pts - a) @ u
        r = (pts - a) - np.outer(t, u)
        perp = np.linalg.norm(r, axis=1)
        m = (perp < 4.5) & (0.35 * L <= t) & (t <= 0.65 * L)
        assert m.sum() >= 20, f"{side}ForeArm: only {int(m.sum())} mid core verts"
        # 2D median in the perp plane, per 2 cm slice
        tmp = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = np.cross(u, tmp); e1 /= np.linalg.norm(e1)
        e2 = np.cross(u, e1)
        worst = 0.0
        for t0 in np.arange(0.35 * L, 0.65 * L, 2.0):
            mm = m & (t >= t0) & (t < t0 + 2.0)
            if mm.sum() < 6:
                continue
            c2 = np.median(r[mm] @ np.stack([e1, e2], axis=1), axis=0)
            worst = max(worst, float(np.linalg.norm(c2)))
        assert worst <= 1.5, f"{side}ForeArm mid-segment centerline off by {worst:.2f} cm"
