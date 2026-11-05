"""Tests for the Miranda "busty" LAS variant (`bust_variant` + its pack).

Two layers, like the sibling suites:

* **Unit** — the chest morph is a pure position function, so its contract
  (continuity, containment, symmetry, monotonicity in the cup parameters) is
  testable on hand-built vertices without any game asset.
* **Integration** — the variant pack reuses the base pack's registration
  contract with a different identity. Those tests read the tracked
  `dist/Miranda_Busty_LAS.zip` and the base `dist/Miranda_LAS.zip`, so they run
  offline from a checkout with no extracted templates.

The full geometry run needs the 2B templates at /tmp/2bsrc (see
tools/pd2-las/README.md); that test skips when they are absent, exactly like
tests/test_build_models.py.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import bust_variant as bv  # noqa: E402

DIST = REPO / "dist"
BASE_ZIP = DIST / "Miranda_LAS.zip"
VARIANT_ZIP = DIST / "Miranda_Busty_LAS.zip"
TEMPLATES = Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b")


# ------------------------------------------------------------------ unit: morph

def _body_group(verts, normals=None, mats=("miranda_body",)):
    import build_models as bm

    g = bm.Group(name="body")
    g.verts = list(verts)
    g.normals = list(normals or [(0.0, 1.0, 0.0)] * len(verts))
    g.slices = [(mats[0], 0, 0, 0, len(verts))]
    g.faces = []
    return g


def test_morph_is_zero_far_from_the_chest():
    morph = bv.ChestMorph()
    # back of the torso, both arms, the legs and the head/neck must be untouched
    for point in ((-3.0, -5.0, 140.0), (20.0, 10.0, 140.0), (3.0, 2.0, 100.0),
                  (0.0, 8.0, 170.0), (0.0, 8.0, 155.0)):
        assert morph.displacement(*point) == (0.0, 0.0, 0.0), point


def test_morph_grows_the_bust_forward_and_never_pulls_back():
    morph = bv.ChestMorph()
    dx, dy, dz = morph.displacement(bv.APEX_X, 20.0, bv.APEX_Z)
    assert dy > 3.2, "the preset has to be a visible cup-size increase (>2x base prominence)"
    # every edited vertex on the front moves forward and/or up, never backward
    for y in (8.0, 12.0, 16.0, 20.0):
        dx, dy, dz = morph.displacement(bv.APEX_X, y, bv.APEX_Z)
        assert dy >= 0.0 and dz >= 0.0


def test_morph_preserves_the_midline():
    """Symmetry: the sternum and every vertex on x=0 keep their x."""
    morph = bv.ChestMorph()
    for z in (132.0, 138.0, 141.5, 146.0):
        for y in (10.0, 16.0, 20.0):
            dx, _dy, _dz = morph.displacement(0.0, y, z)
            assert abs(dx) < 1e-12, (y, z, dx)


def test_morph_is_continuous_across_the_edit_boundary():
    """No cliff at the rim of the dome: the move decays smoothly to zero.

    The profile is C1 at the apex and at the rim, but it is *not* uniformly
    gentle between them — a fuller lower pole is steeper than a symmetric dome,
    and that is the point of it. So the contract is about the two places a real
    discontinuity would show up: the move must reach zero before the rim
    (no cut-off step), and the sampled profile must not jump by a large
    fraction of the peak between adjacent samples at the *ends* of the range,
    which is where a hard gate would step.
    """
    morph = bv.ChestMorph()
    # the soft dome reaches SOFT_SCALE times further than the breast itself, so
    # the profile is sampled over the *whole* support, not just the tight dome
    lo = bv.APEX_Z - bv.RADIUS_Z_DOWN * bv.SOFT_SCALE
    hi = bv.APEX_Z + bv.RADIUS_Z_UP * bv.SOFT_SCALE
    samples = [morph.displacement(bv.APEX_X, 20.0, lo + 0.25 * i)[1]
               for i in range(int((hi - lo) / 0.25) + 3)]
    peak = max(samples)
    assert peak > 3.2
    steps = [abs(b - a) for a, b in zip(samples, samples[1:])]
    assert max(steps) < 0.10 * peak, max(steps)
    # the ends fade out rather than stepping to zero
    assert samples[0] < 0.05 * peak and samples[-1] < 0.05 * peak
    assert samples[-1] == 0.0, "the profile has to reach zero inside the dome rim"
    assert abs(morph.displacement(bv.APEX_X, 20.0, hi)[1]) < 1e-12
    assert abs(morph.displacement(bv.APEX_X, 20.0, lo)[1]) < 1e-12


def test_morph_deepens_the_cleavage():
    """The added push separates the two cups while keeping a taut catsuit bridge."""
    morph = bv.ChestMorph()
    sternum = morph.displacement(0.0, 20.0, bv.APEX_Z)[1]
    breast = morph.displacement(bv.APEX_X, 20.0, bv.APEX_Z)[1]
    assert 0.50 * breast < sternum < 0.75 * breast
    assert morph.valley_factor(0.0) < morph.valley_factor(bv.APEX_X)


def test_morph_parameters_scale_the_result():
    flat = bv.ChestMorph(cup_gain=0.2)
    big = bv.ChestMorph(cup_gain=0.8)
    a = flat.displacement(bv.APEX_X, 20.0, bv.APEX_Z)[1]
    b = big.displacement(bv.APEX_X, 20.0, bv.APEX_Z)[1]
    assert b > a > 0.0


def test_morph_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        bv.ChestMorph(cup_gain=-1.0)
    with pytest.raises(ValueError):
        bv.ChestMorph(lift=-0.1)
    with pytest.raises(ValueError):
        bv.ChestMorph(valley=1.5)


def test_apply_moves_only_the_selected_material_slices():
    """The shadow-caster group also holds the head; its slices stay put."""
    verts = [(bv.APEX_X, 20.0, bv.APEX_Z)] * 2
    g = _body_group(verts)
    g.slices = [("miranda_head", 0, 0, 0, 1), ("miranda_body", 1, 0, 0, 1)]
    morph = bv.ChestMorph()
    moved = morph.apply(g)
    assert moved == 1
    assert g.verts[0] == verts[0], "head slice must not move"
    assert g.verts[1][1] > verts[1][1], "body slice must move"


def test_rebuild_normals_keeps_unit_length_and_targets_the_bump_surface():
    import math

    # a small fan around the apex: forward-facing before, still forward after
    verts = [(bv.APEX_X + 0.5 * i, 20.0, bv.APEX_Z + 0.5 * j)
             for i in (-1, 0, 1) for j in (-1, 0, 1)]
    faces = []
    for i in range(2):
        for j in range(2):
            a = i * 3 + j
            faces += [(a, a + 1, a + 3), (a + 1, a + 4, a + 3)]
    g = _body_group(verts)
    g.faces = faces
    g.normals = [(0.0, 1.0, 0.0)] * len(verts)
    bv.ChestMorph().apply(g)
    for nx, ny, nz in g.normals:
        assert abs(math.sqrt(nx * nx + ny * ny + nz * nz) - 1.0) < 1e-9
        assert ny > 0.5, "the bump surface still faces forward"


# ------------------------------------------------------- unit: pack identity

def test_variant_identity_is_distinct_from_the_base_pack():
    import las_pack

    base = las_pack.BASE_IDENTITY
    variant = _variant_identity()
    for attr in ("item_id", "category", "pack_dir_name", "unit_base", "gui_base"):
        assert getattr(base, attr) != getattr(variant, attr), attr
    assert variant.tpp_unit.endswith("/miranda_busty")
    assert variant.fps_unit.endswith("/fps_miranda_busty")


def _variant_identity():
    import build_busty_variant as bbv

    return bbv.IDENTITY


def test_variant_hook_registers_its_own_legendary_armour():
    import las_pack

    lua = las_pack.render_hook_lua(_variant_identity())
    assert "la.miranda_busty = {" in lua
    assert 'unit = "units/miranda_busty/skins/miranda_busty/miranda_busty"' in lua
    assert 'fps_unit = "units/miranda_busty/skins/miranda_busty/fps_miranda_busty"' in lua
    for flag in las_pack.FLAG_KEYS:
        assert f"{flag} = true" in lua


def test_variant_manifest_registers_prefixed_textures():
    """Textures must be renamed, or both packs compete for `miranda_*` files."""
    import las_pack

    identity = _variant_identity()
    xml = las_pack.render_main_xml(identity)
    assert '<df_nm path="units/miranda_busty/skins/miranda_busty/miranda_busty_body"/>' in xml
    assert '<texture path="units/miranda_busty/skins/miranda_busty/miranda_busty_eyes"/>' in xml
    assert "image=\"guis/dlcs/miranda_busty/armor_skins/miranda_busty\"" in xml
    assert "miranda_body_df" not in xml.split("miranda_busty_body_df")[0].split("<df_nm")[-1]

    renamed = las_pack.retarget_textures(
        {"miranda_body_df.texture": b"x", "miranda_eyes.texture": b"y"}, identity)
    assert set(renamed) == {"miranda_busty_body_df.texture", "miranda_busty_eyes.texture"}


def test_base_pack_rendering_is_unchanged_by_the_identity_refactor():
    import las_pack

    assert las_pack.render_hook_lua() == las_pack.render_hook_lua(las_pack.BASE_IDENTITY)
    xml = las_pack.render_main_xml()
    assert '<df_nm path="units/miranda/skins/miranda/miranda_body"/>' in xml
    assert '<unit_mat path="units/miranda/skins/miranda/fps_miranda"/>' in xml


# ------------------------------------------------------ integration: geometry

needs_templates = pytest.mark.skipif(
    not TEMPLATES.exists(), reason="extracted 2B templates at /tmp/2bsrc not present")


@needs_templates
def test_built_variant_model_matches_the_morph_and_leaves_the_rest_alone():
    """The geometry path end to end: retarget, morph, author, re-read."""
    import build_models as bm
    import diesel_model as dm

    source = REPO / "models" / "l4d2_miranda_lawson_1.zip"
    if not source.is_file():
        pytest.skip("source zip not present")
    from source_model import load_model
    from vpk import VpkArchive

    skel_map = json.loads((REPO / "tools/pd2-las/skeleton_map.json").read_text())
    template = bm.load_template(TEMPLATES / "2b.model")
    arc = VpkArchive.from_zip(source, "miranda_rochelle.vpk")
    model = load_model(*(arc.read(p) for p in bm.TPP_MDLS))
    groups = {name: bm.transfer_group(model, spec, skel_map, template, name)
              for name, spec in bm.TPP_GROUPS.items()}
    before = {name: list(g.verts) for name, g in groups.items()}
    morph = bv.ChestMorph()
    bv.morph_groups(groups, morph, log=lambda *a: None)

    import numpy as np

    v0 = np.asarray(before["body"])
    v1 = np.asarray(groups["body"].verts)
    # the morph subdivides the chest locally, so the body gains vertices; the
    # originals keep their indices and every added vertex is appended after them
    assert len(v1) > len(v0), "the chest is locally subdivided"
    d = np.linalg.norm(v1[:len(v0)] - v0, axis=1)
    added = v1[len(v0):]
    assert int((d > 1e-9).sum()) > 100, "the morph must actually edit the chest"
    assert d.max() > 3.2
    # containment: nothing behind the chest wall, in the arms, legs or head
    for mask, label in ((v0[:, 1] < 0.0, "back"),
                        (np.abs(v0[:, 0]) > 14.0, "arms"),
                        (v0[:, 2] < 115.0, "legs"),
                        (v0[:, 2] > 152.0, "head")):
        assert not (d[mask] > 1e-9).any(), label
    # every added vertex is a chest vertex: the split is local
    assert added[:, 2].min() > 120.0 and added[:, 2].max() < 156.0, "split left the chest"
    assert np.abs(added[:, 0]).max() < 14.0
    # the shadow caster's body block stays identical to the visible body
    s = np.asarray(groups["shadow"].verts)
    assert np.allclose(s[-len(v1):], v1, atol=1e-9)

    share = {dname: name for name, spec in bm.TPP_GROUPS.items()
             for dname in spec["drawables"]}
    data = bm.assemble_model(template, groups, share).write()
    mf = dm.ModelFile.read(data)
    assert any(dm.decode_model_data(s.payload).get("atoms") for s in mf.by_type(dm.MODEL_DATA))


# ----------------------------------------------------- integration: the pack

pytestmark_zip = pytest.mark.skipif(
    not (BASE_ZIP.is_file() and VARIANT_ZIP.is_file()),
    reason="dist packs not built")


@pytestmark_zip
def test_variant_dist_pack_is_tracked_and_self_consistent():
    build_zip = REPO / "build" / "pd2-las" / "Miranda_Busty_LAS.zip"
    build_sha = REPO / "build" / "pd2-las" / "Miranda_Busty_LAS.zip.sha256"
    dist_sha = DIST / "Miranda_Busty_LAS.zip.sha256"
    for p in (build_zip, build_sha, dist_sha):
        assert p.is_file(), f"missing tracked deliverable: {p}"
    raw = VARIANT_ZIP.read_bytes()
    assert build_zip.read_bytes() == raw
    digest = hashlib.sha256(raw).hexdigest()
    assert build_sha.read_text().split()[0] == digest
    assert dist_sha.read_text().split()[0] == digest

    with zipfile.ZipFile(VARIANT_ZIP) as z:
        names = z.namelist()
        info = json.loads(z.read("Miranda_Busty_LAS/BUILD_INFO.json"))
        assert info["models_present"] is True
        assert info["runtime_verified"] is False
        assert "WIP_DO_NOT_INSTALL.txt" not in info["payload_sha256"]
        assert info["registration"]["table"] == "LegendaryArmours.miranda_busty"
        variant = info["variant"]
        assert variant["kind"] == "chest_mass_morph"
        assert variant["base_item_id"] == "miranda"
        assert 3.2 < variant["measured"]["depth_gain_cm"] < 4.5
        for rel, expected in info["payload_sha256"].items():
            assert hashlib.sha256(z.read(f"Miranda_Busty_LAS/{rel}")).hexdigest() == expected, rel

        unit = "Miranda_Busty_LAS/assets/units/miranda_busty/skins/miranda_busty/"
        for model in ("miranda_busty.model", "fps_miranda_busty.model"):
            assert unit + model in names
        # textures carry the pack prefix so they cannot collide with the base pack
        assert unit + "miranda_busty_body_df.texture" in names
        assert unit + "miranda_body_df.texture" not in names


@pytestmark_zip
def test_variant_first_person_arms_are_the_base_arms():
    """The morph must not touch the viewmodel: every authored drawable matches.

    Compared per drawable rather than byte-for-byte: the tracked base pack was
    produced by an older revision of the builder that shipped two extra copies
    of the *head* drawables inside the viewmodel. The variant deliberately does
    not carry those (they are the template's own head), so what has to match is
    the arms: every drawable the variant ships must exist in the base pack with
    byte-identical vertices, normals, UVs and triangles.
    """
    import numpy as np

    import diesel_model as dm

    def drawables(raw: bytes) -> dict:
        mf = dm.ModelFile.read(raw)
        names = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]

        def name_of(h):
            return next((n for n in names if dm.hash64(n) == h), f"#{h:016x}")

        out: dict = {}
        for s in mf.by_type(dm.MODEL_DATA):
            md = dm.decode_model_data(s.payload)
            if md.get("version") != 3 or not md.get("atoms"):
                continue
            gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
            out.setdefault(name_of(md["name_hash"]), []).append(
                (np.asarray(geo["verts"]), np.asarray(geo["normals"]),
                 np.asarray(geo["uv0"]), np.asarray(topo["indices"])))
        return out

    with zipfile.ZipFile(VARIANT_ZIP) as zv, zipfile.ZipFile(BASE_ZIP) as zb:
        base = drawables(zb.read("Miranda_LAS/assets/units/miranda/skins/miranda/"
                                 "fps_miranda.model"))
        variant = drawables(zv.read("Miranda_Busty_LAS/assets/units/miranda_busty/skins/"
                                    "miranda_busty/fps_miranda_busty.model"))
    assert set(variant) == {"g_body", "g_body_lod1", "s_body", "c_block"}, set(variant)
    assert "g_head" not in variant and "g_head_lod1" not in variant
    for name, blocks in variant.items():
        for block in blocks:
            assert any(all(np.array_equal(a, b) for a, b in zip(block, other))
                       for other in base.get(name, [])), (
                f"the viewmodel drawable {name} differs from the base pack's")


@pytestmark_zip
def test_variant_model_is_the_base_model_plus_the_chest():
    """Same topology, same drawables; only the chest vertices moved."""
    import numpy as np

    import diesel_model as dm

    def drawable(raw: bytes, name: str):
        mf = dm.ModelFile.read(raw)
        for s in mf.by_type(dm.MODEL_DATA):
            md = dm.decode_model_data(s.payload)
            if md.get("version") != 3 or not md.get("atoms"):
                continue
            n = _name_of(md["name_hash"], mf)
            if n == name:
                gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
                topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
                return (np.asarray(geo["verts"]), np.asarray(topo["indices"]))
        raise AssertionError(f"drawable {name} not found")

    def _name_of(h, mf):
        hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
        for n in hl["names"]:
            if dm.hash64(n) == h:
                return n
        return f"#{h:016x}"

    with zipfile.ZipFile(VARIANT_ZIP) as zv, zipfile.ZipFile(BASE_ZIP) as zb:
        bv_raw = zv.read("Miranda_Busty_LAS/assets/units/miranda_busty/skins/miranda_busty/"
                         "miranda_busty.model")
        bb_raw = zb.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
    vb, tb = drawable(bb_raw, "g_body")
    vv, tv = drawable(bv_raw, "g_body")
    # the chest is locally subdivided: the variant keeps the base vertices (and
    # their indices) as a prefix and appends the new chest triangles after them
    assert vv.shape[0] > vb.shape[0], "the chest has to gain geometry"
    # topology grows by appending: every base triangle index stays in range and
    # the triangle count only goes up
    assert tv.size >= tb.size, "topology may only gain triangles"
    assert int(tv.max()) == vv.shape[0] - 1, "indices must address the whole mesh"
    untouched_base = (tb.max() < len(vb))
    assert untouched_base
    d = np.linalg.norm(vv[: len(vb)] - vb, axis=1)
    assert int((d > 1e-4).sum()) > 100
    moved = vv[: len(vb)][d > 1e-4]
    assert moved[:, 1].min() > 5.0, "only the chest shell moved"
    assert np.abs(moved[:, 0]).max() < 14.0
    assert moved[:, 2].min() > 123.0 and moved[:, 2].max() < 152.5
    added = vv[len(vb):]
    assert added[:, 2].min() > 124.0 and added[:, 2].max() < 152.0, "split stayed on the chest"
    assert np.abs(added[:, 0]).max() < 14.0


def _closed_chest_fixture(seam_x: float):
    """A closed box whose front face is the chest panel, optionally UV-seamed.

    A bare grid cannot stand in for the outfit: it has a real open border, so
    "no open edges" could never hold. This fixture is a closed solid, and setting
    ``seam_x`` duplicates the front-face vertices in that column so the split has
    to cope with coincident copies exactly as it does on the real mesh.
    """

    verts: list[tuple[float, float, float]] = []
    for zi in range(6):
        for xi in range(6):
            verts.append((12.0 - 4.0 * xi, 18.0, 132.0 + 3.0 * zi))
    back0 = len(verts)
    for zi in range(6):
        for xi in range(6):
            verts.append((12.0 - 4.0 * xi, 2.0, 132.0 + 3.0 * zi))

    def front(xi, zi):
        return zi * 6 + xi

    def back(xi, zi):
        return back0 + zi * 6 + xi

    faces: list[tuple[int, int, int]] = []
    for zi in range(5):
        for xi in range(5):
            faces.append((front(xi, zi), front(xi + 1, zi), front(xi + 1, zi + 1)))
            faces.append((front(xi, zi), front(xi + 1, zi + 1), front(xi, zi + 1)))
            faces.append((back(xi, zi), back(xi + 1, zi + 1), back(xi + 1, zi)))
            faces.append((back(xi, zi), back(xi, zi + 1), back(xi + 1, zi + 1)))
    for zi in range(5):                       # left / right walls
        faces.append((back(0, zi), front(0, zi), front(0, zi + 1)))
        faces.append((back(0, zi), front(0, zi + 1), back(0, zi + 1)))
        faces.append((back(5, zi), front(5, zi + 1), front(5, zi)))
        faces.append((back(5, zi), back(5, zi + 1), front(5, zi + 1)))
    for xi in range(5):                       # top / bottom
        faces.append((back(xi, 0), back(xi + 1, 0), front(xi + 1, 0)))
        faces.append((back(xi, 0), front(xi + 1, 0), front(xi, 0)))
        faces.append((back(xi, 5), front(xi + 1, 5), back(xi + 1, 5)))
        faces.append((back(xi, 5), front(xi, 5), front(xi + 1, 5)))

    if seam_x is not None:
        dup = {}
        for i, (x, _y, _z) in enumerate(list(verts)):
            if abs(x - seam_x) < 1e-9 and i < back0:
                dup[i] = len(verts)
                verts.append(verts[i])
        faces = [(dup.get(a, a), dup.get(b, b), dup.get(c, c))
                 for a, b, c in faces]

    normals = [(0.0, 1.0, 0.0)] * len(verts)
    return verts, faces, normals


def _fixture_group(verts, faces, normals):
    class G:
        pass

    g = G()
    g.name = "fixture"
    g.verts = [tuple(map(float, p)) for p in verts]
    g.faces = [tuple(f) for f in faces]
    g.normals = list(normals)
    g.uvs = [(p[0] * 0.05, p[2] * 0.05) for p in g.verts]
    g.weights = [[(0, 1.0)]] * len(g.verts)
    g.slices = [("miranda_body", 0, 0, len(g.faces), len(g.verts))]
    g.mat_slots = ["miranda_body"]
    g.palette = ["ValveBiped.Bip01_Spine2"]
    return g


def test_subdivision_keeps_the_chest_watertight():
    """The local split must not leave a single open edge in the chest band.

    Both failure modes found while tuning showed up here first: an unsplit edge
    neighbour (a T-junction, which the flat-shaded previews showed as jagged
    black cracks) and duplicated seam vertices that drift apart (hairline tears
    along the bust's outer edge).
    """
    morph = bv.ChestMorph()
    for seam_x in (None, 8.0, 4.0, 0.0):
        verts, faces, normals = _closed_chest_fixture(seam_x)
        g = _fixture_group(verts, faces, normals)
        assert not bv._open_edges(g), f"the fixture itself must be closed ({seam_x})"
        origin = list(g.verts)
        bv.subdivide_region(g, morph, levels=1)
        assert len(g.verts) > len(origin), f"split has to reach the panel ({seam_x})"
        assert not bv._open_edges(g), f"subdivision opened the surface ({seam_x})"
        subdivided_origin = list(g.verts)
        morph.displace(g)
        bv.smooth_region(g, morph, 3, 0.32, origin=subdivided_origin)
        bv.keep_copies_together(g, subdivided_origin)
        assert not bv._open_edges(g), f"the morph opened the surface ({seam_x})"


def test_subdivision_renormalises_the_midpoint_normals():
    """A midpoint normal is the *average* of two unit normals, so it is shorter than one.

    `rebuild_normals` only renormalises inside the morph's weight region, so a split vertex outside
    it (the top of the chest band, z ≈ 150.8) used to ship at |n| = 0.9867: every other normal in the
    pack is unit length, and shading assumptions in the engine assume they are.
    """
    import math

    verts, faces, _ = _closed_chest_fixture(None)
    # alternate the source normals so every average is visibly short of unit length
    normals = [(0.0, 0.0, 1.0) if i % 2 else (0.6, 0.8, 0.0) for i in range(len(verts))]
    g = _fixture_group(verts, faces, normals)
    added = bv.subdivide_region(g, bv.ChestMorph(), levels=1)
    assert added > 0, "the fixture has to split, or this proves nothing"
    lengths = [math.dist((0.0, 0.0, 0.0), n) for n in g.normals]
    assert min(lengths) > 1.0 - 1e-9, f"non-unit normal {min(lengths):.4f}"
    assert max(lengths) < 1.0 + 1e-9


def test_smooth_region_never_leaks_into_unselected_slices():
    """Fairing must not move vertices in non-body slices (e.g. shadow head/neck)."""
    verts, faces, normals = _closed_chest_fixture(None)
    g = _fixture_group(verts, faces, normals)
    head_idx = len(g.verts)
    # Co-located head/collar vertex right inside the chest band.
    g.verts.append((bv.APEX_X, 18.0, 148.5))
    g.normals.append((0.0, 1.0, 0.0))
    g.uvs.append((0.5, 0.5))
    g.weights.append([(0, 1.0)])
    g.faces.append((head_idx, head_idx, head_idx))
    g.slices = [
        ("miranda_body", 0, 0, len(faces), head_idx),
        ("miranda_head", len(faces), head_idx, 1, 1),
    ]
    before_head = g.verts[head_idx]
    bv.ChestMorph().apply(g)
    assert g.verts[head_idx] == before_head, "unselected slice drifted during apply()"


def test_display_path_accepts_paths_outside_repo():
    import build_busty_variant as bbv

    ext = Path("/tmp/outside_repo_test/Miranda_Busty_LAS.zip")
    assert bbv._display_path(ext) == str(ext.resolve())


def test_shipped_busty_archive_regressions():
    """Verify the shipped Miranda_Busty_LAS.zip fixes every audited defect."""
    import hashlib
    import json
    import zipfile

    import build_models as bm
    import diesel_model as dm
    import numpy as np

    busty_zip = Path(__file__).resolve().parents[1] / "dist" / "Miranda_Busty_LAS.zip"
    base_zip = Path(__file__).resolve().parents[1] / "dist" / "Miranda_LAS.zip"
    if not busty_zip.is_file() or not base_zip.is_file():
        pytest.skip("dist archives not present")

    with zipfile.ZipFile(base_zip) as zb:
        base_icon = zb.read("Miranda_LAS/assets/guis/dlcs/miranda/armor_skins/miranda.texture")
        mf_base = dm.ModelFile.read(
            zb.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
        )
    with zipfile.ZipFile(busty_zip) as zv:
        busty_icon = zv.read(
            "Miranda_Busty_LAS/assets/guis/dlcs/miranda_busty/armor_skins/miranda_busty.texture"
        )
        build_info = json.loads(zv.read("Miranda_Busty_LAS/BUILD_INFO.json"))
        mf_var = dm.ModelFile.read(
            zv.read("Miranda_Busty_LAS/assets/units/miranda_busty/skins/miranda_busty/miranda_busty.model")
        )

    # 1. Distinct valid DDS outfit-grid icon (not byte-identical to Miranda_LAS).
    assert busty_icon[:4] == b"DDS "
    assert hashlib.sha256(busty_icon).hexdigest() != hashlib.sha256(base_icon).hexdigest()

    def _drawable(mf, target):
        for s in mf.by_type(dm.MODEL_DATA):
            md = dm.decode_model_data(s.payload)
            if md.get("version") == 3 and md.get("atoms") and bm.template_name(md["name_hash"], mf) == target:
                gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
                topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
                return (
                    np.asarray(geo["verts"], dtype=np.float64),
                    np.asarray(topo["indices"], dtype=np.int32).reshape(-1, 3),
                )
        raise AssertionError(f"missing drawable {target}")

    vb, _ = _drawable(mf_base, "g_body")
    vv, tv = _drawable(mf_var, "g_body")

    # 2. Local chest subdivision actually added vertices while staying well within uint16.
    assert len(vb) < len(vv) < 65535

    # 3. No abdominal forward bulge below z = 134.0 cm (previously +5.10 cm).
    n_orig = len(vb)
    belly = (vb[:, 2] < 134.0) & (vb[:, 1] > 8.0)
    assert np.max(np.abs(vv[:n_orig][belly, 1] - vb[belly, 1])) < 0.05

    # 4. No coarse >2.0 cm triangle edges left across the sculpted chest cups.
    p0, p1, p2 = vv[tv[:, 0]], vv[tv[:, 1]], vv[tv[:, 2]]
    ctr = (p0 + p1 + p2) / 3.0
    cup_tris = (np.abs(ctr[:, 0]) < 8.5) & (ctr[:, 2] >= 136.0) & (ctr[:, 2] <= 146.0) & (ctr[:, 1] > 16.0)
    max_edge = np.maximum(
        np.linalg.norm(p0[cup_tris] - p1[cup_tris], axis=1),
        np.maximum(
            np.linalg.norm(p1[cup_tris] - p2[cup_tris], axis=1),
            np.linalg.norm(p2[cup_tris] - p0[cup_tris], axis=1),
        ),
    )
    assert float(max_edge.max()) < 2.0

    # 5. BUILD_INFO measurement matches true g_body max(y) across ALL vertices (including subdivided).
    reported_max_y = build_info["variant"]["measured"]["front_y_max_cm"][1]
    true_max_y = float(vv[(vv[:, 2] >= 131.0) & (vv[:, 2] <= 152.0), 1].max())
    assert abs(reported_max_y - true_max_y) <= 0.02

    # 6. Posterior/lateral breast-root vertices closer to the spine (y in [8.0, 16.5],
    #    |x| in [9.0, 12.4], z in [138.5, 142.5]) expand smoothly both forward (+dy)
    #    and outward (+|dx|) without inflating the outer ribcage into boxy blocks.
    root_mask = (
        (vb[:, 2] >= 138.5)
        & (vb[:, 2] <= 142.5)
        & (vb[:, 1] >= 8.0)
        & (vb[:, 1] <= 16.5)
        & (np.abs(vb[:, 0]) >= 9.0)
        & (np.abs(vb[:, 0]) <= 12.4)
    )
    assert root_mask.any()
    root_dy = vv[:n_orig][root_mask, 1] - vb[root_mask, 1]
    root_dx = np.abs(vv[:n_orig][root_mask, 0]) - np.abs(vb[root_mask, 0])
    assert 0.25 < float(root_dy.mean()) < 1.2, "spine-side breast root must expand smoothly"
    assert 0.08 < float(root_dx.mean()) < 0.6, "spine-side breast root must widen proportionally"

    # 7. Bounded UV/edge stretch across all original body edges (<1.80x vs old 2.47x)
    #    so honeycomb hexagons stay clean in top and bottom views.
    _, tb = _drawable(mf_base, "g_body")
    max_stretch = 0.0
    for a, b, c in tb:
        for i, j in ((a, b), (b, c), (c, a)):
            l0 = float(np.linalg.norm(vb[i] - vb[j]))
            if l0 > 0.05:
                r = float(np.linalg.norm(vv[i] - vv[j])) / l0
                if r > max_stretch:
                    max_stretch = r
    assert max_stretch < 1.80, f"excessive edge/UV stretch {max_stretch:.3f}x"

    # 8. Smooth, cone-free twin-hemisphere geometry in horizontal AND vertical slices:
    #    - Distinct two-cup separation over taut catsuit (0.55 cm < y_ap - y_sternum < 1.50 cm:
    #      prevents both a central monoboob and an over-carved W-canyon).
    #    - Blunt horizontal roundness on both cups and melted x≈+8.0->+8.5 bib step.
    #    - Blunt 60°/90° vertical side-profile hemisphere (no `>` torpedo cone).
    h_slice = vv[(np.abs(vv[:, 2] - 140.7) < 0.75) & (vv[:, 1] > 15.0)]
    y_sternum = float(h_slice[np.abs(h_slice[:, 0]) < 0.65, 1].max())
    peaks = []
    for side in (-1, +1):
        y_ap = float(h_slice[np.abs(h_slice[:, 0] - side * 5.0) < 1.2, 1].max())
        y_in = float(h_slice[np.abs(h_slice[:, 0] - side * 2.5) < 1.0, 1].max())
        y_out = float(h_slice[np.abs(h_slice[:, 0] - side * 7.0) < 1.0, 1].max())
        assert 0.55 < (y_ap - y_sternum) < 1.50, (
            f"expected clean two-cup separation on side {side}, got {y_ap - y_sternum:.2f} cm"
        )
        assert y_ap - y_in < 0.65, f"pointy medial cone on side {side}"
        assert y_ap - y_out < 0.65, f"pointy lateral cone on side {side}"
        peaks.append(y_ap)
    assert abs(peaks[0] - peaks[1]) < 0.28, "excessive left/right cup asymmetry"

    y_bib_in = float(h_slice[np.abs(h_slice[:, 0] - 8.0) < 0.45, 1].max())
    y_bib_out = float(h_slice[np.abs(h_slice[:, 0] - 8.5) < 0.45, 1].max())
    assert abs(y_bib_in - y_bib_out) < 0.35, "unsmoothed x=+8.0..+8.5 bib cliff"

    v_slice = vv[(np.abs(np.abs(vv[:, 0]) - 5.0) < 1.1) & (vv[:, 1] > 15.0)]
    y_z_ap = float(v_slice[np.abs(v_slice[:, 2] - 140.7) < 0.8, 1].max())
    y_z_lo = float(v_slice[np.abs(v_slice[:, 2] - 138.2) < 0.8, 1].max())
    y_z_hi = float(v_slice[np.abs(v_slice[:, 2] - 143.2) < 0.8, 1].max())
    assert y_z_ap - y_z_lo < 0.85, "pointy lower 60°/90° cone"
    assert y_z_ap - y_z_hi < 0.85, "pointy upper 60°/90° cone"

    # 9. The preview sheets are build output, not repository content: the
    # tracked copies under docs/pd2-las/previews/ were deleted to keep the tree
    # small. They are still rendered on every build, so what stays pinned here
    # is that the builder keeps producing all five of them by name.
    source = (Path(__file__).resolve().parents[1] / "tools" / "pd2-las"
              / "build_busty_variant.py").read_text(encoding="utf-8")
    for sheet in (
        "busty_compare_chest.png",
        "busty_compare_full.png",
        "busty_sculpt_clay.png",
        "busty_compare_top_bottom.png",
        "busty_sculpt_top_bottom_clay.png",
    ):
        assert sheet.removesuffix(".png") in source, f"builder no longer emits {sheet}"


def test_smooth_region_pins_open_boundary_edges():
    """Open mesh boundary lips (such as the keyhole flap overhang) must stay pinned."""
    g = _fixture_group(
        [
            (0.0, 18.0, 145.5),
            (2.0, 18.0, 145.5),
            (1.0, 19.0, 144.0),
            (1.0, 18.2, 142.5),
        ],
        [(0, 1, 2), (1, 3, 2), (3, 0, 2)],
        [(0.0, 1.0, 0.0)] * 4,
    )
    # Outer triangle edges (0,1), (1,3), (3,0) have use count 1 -> vertices 0,1,3 are boundary;
    # interior vertex 2 has all incident edges used twice -> movable.
    origin = list(g.verts)
    bv.smooth_region(g, bv.ChestMorph(), iterations=4, strength=0.35, origin=origin)
    assert g.verts[0] == origin[0]
    assert g.verts[1] == origin[1]
    assert g.verts[3] == origin[3]
    assert g.verts[2] != origin[2]

