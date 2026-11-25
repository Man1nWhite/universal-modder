"""Where the palm begins: the OfficeSuite family's hand cut, as a number (D59).

The three packs that share OfficeSuite's body drop everything distal to the plane
through the rig's `Hand` joint, perpendicular to the palm (the axis from that joint
to the four knuckle bases). That plane is what "where the palm begins" means in this
repository, and it is written into each pack's `BUILD_INFO.json` - origin, axis,
degrees from the forearm axis, what the cut removed by bone, and how far short of the
plane the surviving mesh now ends. These tests pin the landmark to the rig, the record
to the mesh, and the mesh to the landmark.
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
    assert cut["margin_cm"] == 0.0, "the cut is the crease itself, not a few cm past it"
    assert cut["removed_tris"] > 1000 and cut["rim_cap_tris"] > 0
    assert info["registration"]["glove_adapter"] is True
    assert info["registration"]["own_hands"] is False
    # Everything the cut took was a hand or a finger; the rim carries a few
    # forearm-dominated vertices, which is the edge of the sleeve.
    stray = sorted(b for b in cut["removed_bones"] if not bm.is_hand_bone(b))
    assert stray == ["LeftForeArm", "RightForeArm"], stray
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
        # the shipped mesh ends short of the plane, on the sleeve side
        assert -6.0 < cut[key]["kept_to_cm"] < -0.5, cut[key]


@pytest.mark.parametrize("pack,stem", PACKS)
def test_the_shipped_body_has_no_hand_left(pack, stem):
    """Not one vertex is dominated by a hand or finger bone, and none passes the plane."""
    template = _body_model(pack, stem)
    drawable = template.drawables["g_body"]
    mf = template.mf
    gp = dm.decode_passthroughgp(mf.by_id(drawable["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    objects = [template.id_name.get(o, "?") for o in template.drawable_skin["g_body"]["objects"]]
    indices = np.asarray(geo["blendindices"])
    weights = np.asarray(geo["blendweights"])
    dominant = np.asarray(objects)[indices[np.arange(len(indices)), weights.argmax(axis=1)]]
    assert not np.array([bm.is_hand_bone(name) for name in dominant]).any()

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
        assert axial[near].max() < 0.0, "geometry survives distal to where the palm begins"


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
    assert not np.array([bm.is_hand_bone(name) for name in dominant]).any()
