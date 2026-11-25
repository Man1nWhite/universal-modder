"""Where the palm begins: the OfficeSuite family's hand cut, as a number (D59/D60/D62).

The three packs that share OfficeSuite's body cut everything distal to a plane through
the rig's `Hand` joint, perpendicular to the palm (the axis from that joint to the four
knuckle bases). That plane is what "where the palm begins" means in this repository, and
it is written into each pack's `BUILD_INFO.json` - origin, axis, degrees from the forearm
axis, what the cut removed by bone, and how far past the plane the surviving mesh reaches.
Since D60 the cut is made by splitting the triangles it crosses rather than dropping them
whole; since D62 it sits `PALM_EXTEND_CM` (4 cm) *past* the palm line, inside the palm,
because cutting on the crease left the arm ending in mid-air short of the heister's glove
cuff. These tests pin the landmark to the rig, the record to the mesh, and the mesh to the
landmark.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
import extract_2b  # noqa: E402
from dist_paths import dist_path  # noqa: E402

TEMPLATES = extract_2b.TEMPLATES
needs_templates = pytest.mark.skipif(not TEMPLATES.exists(), reason=extract_2b.MISSING)

#: pack, the unit inside it, and the drawable that carries the outfit body
PACKS = (
    ("OfficeSuite", "officesuite"),
    ("OfficeSuite_Head", "officesuite_head"),
)
#: what survives inside the extension: the thumb's base is the thenar, the palm's own
#: proximal few centimetres - it is what makes the arm's end continuous with the wrist
THENAR = ("LeftHandThumb1", "RightHandThumb1")

#: the native override ships the same body on Hila's unit
HILA = ("OfficeSuite_Miranda_Romance_over_Hila",
        "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female")


def _palm_planes():
    return bm.palm_planes(bm.load_template(TEMPLATES / "2b.model"))


@needs_templates
def test_the_landmark_is_the_hand_joint_and_the_knuckles_on_the_rig():
    """The plane's origin is the `Hand` joint; its axis points at the knuckle bases."""
    template = bm.load_template(TEMPLATES / "2b.model")
    planes = bm.palm_planes(template)
    assert sorted(planes) == [-1, 1]
    for side, key in ((-1, "Left"), (1, "Right")):
        info = planes[side]
        origin = np.asarray(info["origin"], dtype=np.float64)
        joint = np.asarray(template.worlds[template.name_id[key + "Hand"]][12:15], dtype=np.float64)
        np.testing.assert_allclose(origin, joint, atol=1e-9)
        knuckles = np.mean([np.asarray(template.worlds[template.name_id[key + k]][12:15], dtype=np.float64)
                            for k in bm.PALM_KNUCKLES], axis=0)
        np.testing.assert_allclose(info["axis"], (knuckles - joint) / np.linalg.norm(knuckles - joint), atol=1e-9)
        # The palm's own axis, not the forearm's: the two differ by a few degrees, and
        # that wedge is the heel of the hand a forearm-plane cut leaves behind.
        assert 2.0 < info["deg_from_forearm"] < 10.0, info["deg_from_forearm"]
    # the rig is mirrored: same height, opposite X, opposite X on the axis (the two
    # hand joints sit a tenth of a millimetre apart in X, so compare loosely)
    left, right = planes[-1], planes[1]
    assert left["origin"][0] == pytest.approx(-right["origin"][0], abs=1e-3)
    assert left["origin"][1:] == pytest.approx(right["origin"][1:], abs=1e-3)
    assert left["axis"][0] == pytest.approx(-right["axis"][0], abs=1e-4)


def _info(pack: str) -> dict:
    path = dist_path(ROOT, f"{pack}.zip")
    if not path.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(f"{pack}/BUILD_INFO.json"))


def _body_model(pack: str, stem: str):
    with zipfile.ZipFile(dist_path(ROOT, f"{pack}.zip")) as z:
        blob = z.read(f"{pack}/assets/units/{stem}/skins/{stem}/{stem}.model")
    return bm.template(dm.ModelFile.read(blob))


@pytest.mark.parametrize("pack,stem", PACKS)
def test_each_pack_records_the_plane_it_cut_on(pack, stem):
    info = _info(pack)
    assert info["hands"] == "palm_cut"
    cut = info["palm_cut"]
    # the cut is the palm line plus the extension D62 added, so the arm reaches into
    # the glove instead of ending in mid-air above it
    assert cut["margin_cm"] == cut["extend_cm"] == 4.0
    assert cut["removed_tris"] > 1000 and cut["rim_cap_tris"] > 0
    # The cut is made on the plane: the triangles it crosses are split, so the
    # surface that survives reaches the crease itself (D60).
    assert cut["exact"] is True
    assert cut["tris_split"] > 0 and cut["verts_added"] > 0
    # No default glove unit, no stock hands, and no vanilla bare-forearm piece: the
    # player's glove choice is the only thing that puts a hand on the character.
    assert info["registration"]["glove_adapter"] is False
    assert info["registration"]["own_hands"] is True
    # Everything the cut took is dominated by a hand or a finger bone. Cutting on the
    # crease (D60) took 17 forearm-dominated vertices per side as well, at the rim;
    # four centimetres into the palm (D62) the cut is entirely in hand territory.
    stray = sorted(b for b in cut["removed_bones"] if not bm.is_hand_bone(b))
    assert stray == [], stray
    assert "LeftHand" in cut["removed_bones"] and "RightHand" in cut["removed_bones"]
    assert sum(cut["removed_bones"].values()) > 1000


@pytest.mark.parametrize("pack,stem", PACKS)
def test_the_recorded_plane_is_the_one_on_the_rig(pack, stem):
    info = _info(pack)
    cut = info["palm_cut"]["plane"]
    expected = _palm_planes()
    for side, key in ((-1, "left"), (1, "right")):
        assert cut[key]["origin_cm"] == pytest.approx([round(v, 3) for v in expected[side]["origin"]])
        assert cut[key]["axis"] == pytest.approx([round(v, 4) for v in expected[side]["axis"]])
        assert cut[key]["deg_from_forearm"] == pytest.approx(round(expected[side]["deg_from_forearm"], 2))
        # the cut lands exactly where it was asked to: the palm line plus 4 cm, which
        # is where the shipped mesh ends (the 5% slim moves it by millimetres)
        assert cut[key]["clipped_to_cm"] == 4.0, cut[key]
        assert 3.8 < cut[key]["kept_to_cm"] <= 4.0, cut[key]


@pytest.mark.parametrize("pack,stem", PACKS)
def test_the_shipped_body_has_no_hand_left(pack, stem):
    """No finger survives, and nothing reaches past the palm line by more than the extension.

    The `Hand` bone may dominate: the proximal 4 cm of the palm is what the body keeps
    (D62), and that is a hand bone's territory. Every finger segment is not.
    """
    template = _body_model(pack, stem)
    drawable = template.drawables["g_body"]
    mf = template.mf
    gp = dm.decode_passthroughgp(mf.by_id(drawable["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    objects = [template.id_name.get(o, "?") for o in template.drawable_skin["g_body"]["objects"]]
    indices = np.asarray(geo["blendindices"])
    weights = np.asarray(geo["blendweights"])
    dominant = np.asarray(objects)[indices[np.arange(len(indices)), weights.argmax(axis=1)]]
    fingers = sorted({name for name in dominant if bm.is_hand_bone(name) and not name.endswith("Hand")})
    # The thumb's *base* is kept: it is the thenar (D62). Nothing past it survives -
    # no thumb phalanx, no finger segment.
    assert fingers == list(THENAR), fingers

    verts = np.asarray(geo["verts"], dtype=np.float64)
    planes = _palm_planes()
    for side in (-1, 1):
        origin = np.asarray(planes[side]["origin"], dtype=np.float64)
        axis = np.asarray(planes[side]["axis"], dtype=np.float64)
        rel = verts - origin
        axial = rel @ axis
        perp = np.linalg.norm(rel - np.outer(axial, axis), axis=1)
        near = perp < 28.0
        assert near.any()
        # ... and the farthest vertex is the extension, not a palm or a finger
        assert axial[near].max() <= 4.05, "geometry survives past the palm extension"
        assert axial[near].max() > 3.8, "the mesh stops short of the palm extension"


def test_the_native_override_carries_the_same_cut_and_hilas_gloves():
    """The Hila override inherits the body, so it inherits the cut - and keeps her gloves."""
    path = dist_path(ROOT, f"{HILA[0]}.zip")
    if not path.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    from build_hila_body_mod import GLOVE, INSTALL
    with zipfile.ZipFile(path) as z:
        model = dm.ModelFile.read(z.read(f"{INSTALL}/{HILA[1]}.model"))
        objects = z.read(f"{INSTALL}/{HILA[1]}.object").decode("utf-8")
    template = bm.template(model)
    assert GLOVE in template.drawables, "the stock glove drawable is missing"
    assert f'name="{GLOVE}"' in objects and 'enabled="true"' in objects
    drawable = template.drawables["g_body"]
    gp = dm.decode_passthroughgp(model.by_id(drawable["passthroughgp"]).payload)
    geo = dm.decode_geometry(model.by_id(gp["geometry"]).payload)
    names = [template.id_name.get(o, "?") for o in template.drawable_skin["g_body"]["objects"]]
    indices = np.asarray(geo["blendindices"])
    weights = np.asarray(geo["blendweights"])
    dominant = np.asarray(names)[indices[np.arange(len(indices)), weights.argmax(axis=1)]]
    # Same body, same cut: only the thenar the extension keeps may be hand-dominated.
    bones = sorted({name for name in dominant if bm.is_hand_bone(name)})
    assert bones == sorted([*THENAR, "LeftHand", "RightHand"]), bones


def _box_group():
    """A one-slice 2 cm box in the outfit's group shape, straddling the z = 0 plane."""
    import build_models as bm

    g = bm.Group(name="probe")
    corners = [(-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
               (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0)]
    g.verts = corners
    g.normals = [(0.0, 0.0, float(c[2])) for c in corners]
    g.uvs = [(0.5 * (c[0] + 1.0), 0.5 * (c[1] + 1.0)) for c in corners]
    g.weights = [[(0, 1.0)] for _ in corners]
    g.palette = ["LeftForeArm"]
    # bottom, top, and the four sides, wound outwards
    g.faces = [(0, 2, 1), (0, 3, 2),                  # z = -1
               (4, 5, 6), (4, 6, 7),                  # z = +1
               (0, 1, 5), (0, 5, 4),
               (1, 2, 6), (1, 6, 5),
               (2, 3, 7), (2, 7, 6),
               (3, 0, 4), (3, 4, 7)]
    g.slices = [("body", 0, 0, len(g.faces), len(g.verts))]
    g.mat_slots = ["officesuite_body"]
    return g


def test_the_clip_stops_dead_on_the_plane_and_the_drop_stops_a_face_early():
    """D60's whole difference from D59, on a box: split on the plane, not a band short."""
    import tmc_las

    planes = [((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))]

    clipped = _box_group()
    report = tmc_las.clip_group_at_planes(clipped, planes)
    assert max(v[2] for v in clipped.verts) == pytest.approx(0.0, abs=1e-12), \
        "the clip left geometry past the plane"
    # the four bottom corners plus eight crossing points: two per side panel (one on
    # the outer vertical edge, one on the panel's diagonal), the vertical ones shared
    # between neighbouring panels - which is the edge-keyed cache doing its job
    assert len(clipped.verts) == 12
    assert report["tris_split"] == 8 and report["verts_added"] == 8
    # each of the eight straddling triangles keeps its half - four keep a quad (two of
    # their vertices were already proximal) and four keep a triangle - plus the bottom
    # face's unchanged two
    assert len(clipped.faces) == 14
    assert report["verts_after"] == 12
    # the slice block is still the slice's own (the Diesel atom invariant)
    (src_mat, base_v, base_i, tris, nverts), = clipped.slices
    assert (src_mat, base_v, base_i, nverts) == ("body", 0, 0, 12)
    assert tris == len(clipped.faces) and base_i == 0
    assert all(base_v <= vi < base_v + nverts for f in clipped.faces for vi in f)
    # weights on the rim are interpolated, not invented
    assert all(w == [(0, 1.0)] for w in clipped.weights)
    # the cut leaves one watertight boundary loop, on the plane: eight rim edges, and
    # every rim vertex used by exactly two of them (no T-junction, no open seam)
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in clipped.faces:
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            counts[key] = counts.get(key, 0) + 1
    rim = [e for e, n in counts.items() if n == 1]
    assert len(rim) == 8, rim
    assert all(clipped.verts[v][2] == pytest.approx(0.0, abs=1e-12) for e in rim for v in e)
    degree: dict[int, int] = {}
    for x, y in rim:
        degree[x] = degree.get(x, 0) + 1
        degree[y] = degree.get(y, 0) + 1
    assert sorted(degree.values()) == [2] * 8

    dropped = _box_group()
    tmc_las.cut_group_at_planes(dropped, planes, margin=0.0)
    # ... while the whole-triangle drop cannot keep a side it crosses, so the box
    # ends a full face short of the same plane.
    assert max(v[2] for v in dropped.verts) == pytest.approx(-1.0)
