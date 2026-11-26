"""The wrist pass: the distal forearm twists on `ForeArmRoll`, the cuff skin follows `Hand` (D73).

The 2026-11-26 first-person captures showed the outfit's own wrist standing through the white
dress glove's cuff in weapon poses. The cause is upstream of the gloves: `retarget_maps` fits one
rigid matrix per segment to both of the source forearm's joints, so the outfit's wrist lands a few
millimetres off the rig's `Hand` joint and the circle of skin the palm cut leaves is centred off
the globes' cross-section. The pass fixes it in the weights and in two millimetres of radius -
never in the cut - and runs after the slim, whose anchors depend on which bones carry a vertex.

These tests pin: the record the pack writes, the curve itself on the shipped mesh (vanilla
Sydney's own, which is what the pack now matches), the invariants the cut's tests depend on
(nothing hand-dominated, the rim where it was, the bracelet untouched), the shadow caster
following the body, and that a posed wrist no longer protrudes through a glove's cuff more than
a fraction of what it did.
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
BODY = dist_path(ROOT, "OfficeSuite.zip")
HILA = dist_path(ROOT, "OfficeSuite_Miranda_Romance_over_Hila.zip")
#: the two units in the Hila override that carry the outfit's own body drawable
HILA_UNIT = "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female"


def _template():
    return bm.load_template(TEMPLATES / "2b.model")


def _frames(template):
    """{side: (elbow, wrist, forearm unit axis, length)} straight off the rig."""
    out = {}
    for side, key in ((-1, "Left"), (1, "Right")):
        elbow = np.asarray(template.worlds[template.name_id[key + "ForeArm"]][12:15], dtype=np.float64)
        wrist = np.asarray(template.worlds[template.name_id[key + "Hand"]][12:15], dtype=np.float64)
        axis = (wrist - elbow) / np.linalg.norm(wrist - elbow)
        out[side] = (elbow, wrist, axis, float(np.linalg.norm(wrist - elbow)))
    return out


def _outfit(pack=BODY, stem="officesuite"):
    """(template, verts, weights as bone-name dicts, per-vertex slice index, atoms) of `g_body`."""
    pack = Path(pack)
    with zipfile.ZipFile(pack) as z:
        raw = z.read(_member(z, pack, stem))
    mf = dm.ModelFile.read(raw)
    template = bm.template(mf)
    md = next(dm.decode_model_data(s.payload) for s in mf.by_type(dm.MODEL_DATA)
              if dm.decode_model_data(s.payload).get("name_hash") == dm.hash64("g_body"))
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
    names = [template.id_name.get(o, f"#{o}") for o in sb["objects"]]
    verts = np.asarray(geo["verts"], dtype=np.float64)
    bi = np.asarray(geo["blendindices"], dtype=np.int64)
    bw = np.asarray(geo["blendweights"], dtype=np.float64)
    weights = []
    for i in range(len(bi)):
        d = {}
        for k in range(3):
            if bw[i, k] > 1e-6:
                d[names[bi[i, k]]] = d.get(names[bi[i, k]], 0.0) + float(bw[i, k])
        rest = 1.0 - float(bw[i].sum())
        if rest > 1e-6:
            d[names[bi[i, 3]]] = d.get(names[bi[i, 3]], 0.0) + rest
        weights.append(d)
    # the material each vertex belongs to, through the atoms' triangle ranges
    faces = np.asarray(topo["indices"], dtype=np.int64).reshape(-1, 3)
    slot_of = np.full(len(verts), "", dtype=object)
    mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
    mats = [bm.template_name(dm.decode_material(mf.by_id(m).payload)["name_hash"], mf)
            for m in mg["material_ids"]]
    for atom in md["atoms"]:
        start = atom["base_index"] // 3
        used = faces[start:start + atom["tri_count"]]
        mi = atom["material_id"]
        name = mats[mi] if mi < len(mats) else ""
        slot_of[np.unique(used)] = name
    return template, verts, weights, slot_of, faces


def _member(z, pack, stem):
    for n in z.namelist():
        if n.endswith(f"/skins/{stem}/{stem}.model"):
            return n
    raise AssertionError(f"no {stem}.model in {pack}")


def _info_text(pack):
    path = Path(pack)
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("OfficeSuite/BUILD_INFO.json"))


def _info(pack=BODY):
    path = Path(pack)
    if not path.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    return _info_text(pack)


# ---------------------------------------------------------------- the record


@pytest.mark.parametrize("pack,stem", [(BODY, "OfficeSuite"), (HILA, None)])
def test_the_pack_records_the_weight_curve_it_wrote(pack, stem):
    """Every number the pass used is in the pack, and the curve is vanilla Sydney's own.

    The Hila override is a native-path pack with no `BUILD_INFO.json`; it inherits the body
    drawable from `OfficeSuite.zip` byte for byte, so its copy of the curve is checked there.
    """
    if stem is None:
        info = _info(BODY)
    else:
        info = _info_text(pack)
    wrist = info.get("wrist")
    if wrist is None:
        pytest.skip(f"{Path(pack).stem} was built before the wrist pass")
    # vanilla `npc_criminal_sydney` g_body reaches a full ForeArmRoll by u = 0.80; the outfit
    # keeps that curve and takes it to the wrist, so the sleeve and the glove turn together
    assert wrist["twist_ramp"][0] == pytest.approx(0.35, abs=0.05)
    assert wrist["twist_ramp"][1] >= 0.80
    assert wrist["twist_to_roll"] == pytest.approx(1.0)
    # the hand blend and the tuck share one stretch of the palm axis, which ends proximal of
    # the cut (0 cm) so the rim ring itself is not tapered past the gloves
    assert wrist["hand_blend_cm"] == wrist["taper_cm"]
    assert wrist["hand_blend_cm"][1] < 0.0
    assert 0.0 < wrist["hand_blend_max"] < 0.5, "a hand majority would break the palm cut's test"
    assert wrist["taper_max_cm"] <= 0.5
    for group in ("outfit", "shadow"):
        entry = wrist["groups"][group]
        assert entry["palette_added"] == ["LeftForeArmRoll", "RightForeArmRoll"]
        assert entry["vertices_reweighted"] > 0
        assert entry["max_hand_weight"] < 0.5
        # a few millimetres of shape change, not a rescale of the wrist
        assert entry["max_shift_cm"] < 1.5


def test_the_shadow_caster_takes_the_same_reweighting_as_the_body():
    """Both drawables are posed by the same skeletons; a shadow that kept the old weights would
    slide against the body it casts from."""
    info = _info()
    wrist = info.get("wrist") or pytest.skip("built before the wrist pass")
    outfit, shadow = wrist["groups"]["outfit"], wrist["groups"]["shadow"]
    for key in ("vertices_reweighted", "vertices_tapered", "max_hand_weight", "max_shift_cm"):
        assert shadow[key] == pytest.approx(outfit[key]), key


# ---------------------------------------------------------------- the curve, on the mesh


@needs_templates
@pytest.mark.parametrize("side,key", [(-1, "Left"), (1, "Right")])
def test_the_forearm_hands_its_distal_half_to_the_roll_bone(side, key):
    """`u` 0.2-0.4 stays ForeArm's; the wrist end is the roll's - the vanilla curve, measured."""
    if not BODY.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    template, verts, weights, _slot, _faces = _outfit()
    elbow, wrist, axis, length = _frames(template)[side]
    u = ((verts - elbow) @ axis) / length
    on_arm = ((verts[:, 0] < 0) == (side < 0)) & (np.abs(verts[:, 0]) > 30.0) & (u > 0.15) & (u < 1.02)
    fore = np.array([w.get(f"{key}ForeArm", 0.0) for w in weights])
    roll = np.array([w.get(f"{key}ForeArmRoll", 0.0) for w in weights])
    hand = np.array([w.get(f"{key}Hand", 0.0) for w in weights])
    arm = on_arm & ((fore + roll + hand) > 0.9)
    assert arm.sum() > 100

    proximal = arm & (u > 0.20) & (u < 0.40)
    distal = arm & (u > 0.85) & (u < 1.02)
    assert proximal.sum() and distal.sum()
    # the elbow end is still the forearm's, untouched
    assert fore[proximal].mean() > 0.85
    assert roll[proximal].mean() < 0.10
    # the wrist end is the roll's, which is what makes the sleeve follow a twist
    assert roll[distal].mean() > 0.50
    assert fore[distal].mean() < 0.10
    # and the hand blend only reaches the very end, never a majority
    assert hand[distal].max() < 0.5


@needs_templates
def test_no_vertex_in_the_shipped_body_is_dominated_by_a_hand_bone():
    """`tests/test_palm_cut.py` and `tests/test_hila_body_override.py` require this: the hand
    blend must stay below the roll's weight everywhere, not just on average."""
    if not BODY.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    _template_, _verts, weights, _slot, _faces = _outfit()
    hand_dominated = [i for i, w in enumerate(weights)
                      if w and bm.is_hand_bone(max(w, key=w.get))]
    assert hand_dominated == []
    # and the tests' own reader (dominant by argmax over the stored four) agrees
    for w in weights:
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-5)
        assert len(w) <= 4


@needs_templates
@pytest.mark.parametrize("side", [-1, 1])
def test_the_cut_and_the_bracelet_are_where_they_were(side):
    """The pass must not move the cut: the rim stays 0.7-0.8 cm proximal of the crease, and the
    bracelet - a rigid ring - keeps its own vertices and its own radius."""
    if not BODY.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    template, verts, weights, slot, _faces = _outfit()
    origin = np.asarray(template.worlds[template.name_id[("Left" if side < 0 else "Right") + "Hand"]][12:15],
                        dtype=np.float64)
    palm = bm.palm_planes(template)[side]
    paxis = np.asarray(palm["axis"], dtype=np.float64)
    rel = verts - origin
    ax = rel @ paxis
    radius = np.linalg.norm(rel - np.outer(ax, paxis), axis=1)
    near = radius < 28.0
    assert -0.9 < ax[near].max() < 0.0
    # and at the D70 value: the pass moves the rim inwards and sideways, never along the axis
    assert ax[near].max() == pytest.approx(-0.76 if side < 0 else -0.79, abs=0.02)
    # the bracelet is the jewellery slice on the left wrist; it is a ring 2.4-5.5 cm back
    if side < 0:
        jewel = np.array([s.endswith("jewelry") for s in slot])
        assert jewel.sum() > 100
        ring = jewel & (ax > -5.6) & (ax < -2.2) & (radius < 6.0)
        assert ring.sum() > 50
        # it is still a full ring: no vertex was pulled towards the axis
        assert radius[ring].min() > 2.0


# ---------------------------------------------------------------- the bug itself, posed

GLOVES = ROOT / "references" / "Heister - FPS Gloves in TPS 2.zip"
GLOVE_UNITS = "Heister - FPS Gloves in TPS/Heister - FPS Gloves in TPS/units/"
GLOVES_BY_NAME = {
    "sydney": GLOVE_UNITS + "pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
    "joy": GLOVE_UNITS + "pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model",
    "clover": GLOVE_UNITS + "pd2_dlc_chill/characters/shared_character/npc_criminal_female_chill.model",
}
needs_gloves = pytest.mark.skipif(not GLOVES.is_file(), reason="the glove reference pack is absent")


def _glove_hands(which):
    with zipfile.ZipFile(GLOVES) as z:
        mf = dm.ModelFile.read(z.read(GLOVES_BY_NAME[which]))
    template = bm.template(mf)
    md = next(dm.decode_model_data(s.payload) for s in mf.by_type(dm.MODEL_DATA)
              if dm.decode_model_data(s.payload).get("name_hash") == dm.hash64("g_hands"))
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
    names = [template.id_name.get(o, f"#{o}") for o in sb["objects"]]
    bi = np.asarray(geo["blendindices"], dtype=np.int64)
    bw = np.asarray(geo["blendweights"], dtype=np.float64)
    weights = []
    for i in range(len(bi)):
        d = {}
        for k in range(3):
            if bw[i, k] > 1e-6:
                d[names[bi[i, k]]] = d.get(names[bi[i, k]], 0.0) + float(bw[i, k])
        rest = 1.0 - float(bw[i].sum())
        if rest > 1e-6:
            d[names[bi[i, 3]]] = d.get(names[bi[i, 3]], 0.0) + rest
        weights.append(d)
    return np.asarray(geo["verts"], dtype=np.float64), weights


def _rot(axis, deg):
    a = np.asarray(axis, dtype=np.float64) / np.linalg.norm(axis)
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * (K @ K)


def _pose(template, rotations):
    """Skinning matrices for a posed rig, with children following their parents.

    `rotations` is [(bone, axis, degrees, pivot)] in the bind pose's own world space. A bone's
    vertices move by the accumulated turn `A` of its chain - so a forearm twist carries the hand
    (and the glove on it), and a wrist bend carries the fingers, as in the game.
    """
    parent = {n: template.id_name.get(template.id_obj[s].get("parent"), "")
              for n, s in template.name_id.items()}
    by_bone = {}
    for bone, axis, deg, pivot in rotations:
        by_bone.setdefault(bone, []).append((axis, deg, pivot))
    order, seen = [], set()

    def visit(n):
        if n in seen or n not in template.name_id:
            return
        seen.add(n)
        order.append(n)
        for name, par in parent.items():
            if par == n:
                visit(name)
    visit("Hips")
    order += [n for n in template.name_id if n not in seen]

    acc = {}
    for name in order:
        par = parent.get(name, "")
        A = acc[par].copy() if par in acc else np.eye(4)
        for axis, deg, pivot in by_bone.get(name, ()):
            rot = _rot(axis, deg)
            R = np.eye(4)
            R[:3, :3] = rot
            T = np.eye(4)
            T[3, :3] = np.asarray(pivot, dtype=np.float64) - np.asarray(pivot, dtype=np.float64) @ rot
            A = A @ (R @ T)          # row-vector convention: p @ R, then p @ T
        acc[name] = A
    return {n: a for n, a in acc.items() if n in template.name_id}


def _skinned(verts, weights, posed):
    acc = np.zeros_like(verts)
    tot = np.zeros(len(verts))
    for i, wd in enumerate(weights):
        for bone, w in wd.items():
            if w <= 0.0 or bone not in posed:
                continue
            acc[i] += w * (np.append(verts[i], 1.0) @ posed[bone])[:3]
            tot[i] += w
    ok = tot > 1e-9
    acc[ok] /= tot[ok, None]
    acc[~ok] = verts[~ok]
    return acc


def _wrist_poses(template, side):
    """The rotations a weapon pose puts on a wrist, plus the rest pose."""
    key = "Left" if side < 0 else "Right"
    elbow = np.asarray(template.worlds[template.name_id[key + "ForeArm"]][12:15], dtype=np.float64)
    wrist = np.asarray(template.worlds[template.name_id[key + "Hand"]][12:15], dtype=np.float64)
    paxis = np.asarray(bm.palm_planes(template)[side]["axis"], dtype=np.float64)
    faxis = (wrist - elbow) / np.linalg.norm(wrist - elbow)
    ext = np.cross(paxis, faxis)
    ext /= np.linalg.norm(ext)
    twist = [(key + "ForeArmRoll", faxis, 45, wrist), (key + "Hand", faxis, 45, wrist)]
    return {
        "rest": [],
        "twist": twist,
        "ext30": [(key + "Hand", ext, 30, wrist)],
        "ext45": [(key + "Hand", ext, 45, wrist)],
        "ext30_twist": twist + [(key + "Hand", ext, 30, wrist)],
        "ext30_roll": [(key + "ForeArmRoll", faxis, 45, wrist), (key + "Hand", ext, 30, wrist)],
    }


def _walls(points, side, planes, stations, half=0.45, rmin=1.0, rmax=8.0):
    """The surface's radius in each (palm-axial station, 12-sector) cell: its wall there."""
    origin = np.asarray(planes[side]["origin"], dtype=np.float64)
    axis = np.asarray(planes[side]["axis"], dtype=np.float64)
    rel = points - origin
    ax = rel @ axis
    radial = rel - np.outer(ax, axis)
    r = np.linalg.norm(radial, axis=1)
    e1 = np.cross(axis, [0.0, 0.0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    sec = (np.arctan2(radial @ e2, radial @ e1) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    out = {}
    for st in stations:
        for s in range(12):
            m = (np.abs(ax - st) < half) & (sec == s) & (r > rmin) & (r < rmax)
            if m.any():
                out[(st, s)] = float(r[m].max())
    return out


#: palm-axial stations the cuff covers, in cm (0 is the rig's `Hand` joint, the cut)
STATIONS = (-3.6, -3.0, -2.4, -1.8, -1.2, -0.9)


def _worst_protrusion(which):
    """Worst (cm) by which the wrist skin stands outside a glove's wall, over both wrists' poses.

    Both surfaces are cut into 12 angular sectors at a handful of palm-axial stations; the glove's
    wall in a cell is its largest radius and the skin's is its largest radius, and the difference
    is how far the skin stands proud of the glove there. The outfit's cells are taken on the skin
    slice alone, so the bracelet - which is meant to sit outside the glove and is 2.4 cm back -
    cannot be mistaken for the wrist.
    """
    template, verts, weights, slot, _faces = _outfit()
    skin = np.array([s.endswith("body") for s in slot])
    sub = np.where(skin)[0]
    gverts, gweights = _glove_hands(which)
    planes = bm.palm_planes(template)
    worst = -9.0
    for side in (-1, 1):
        for rotations in _wrist_poses(template, side).values():
            posed = _pose(template, rotations)
            ov = _skinned(verts[sub], [weights[i] for i in sub], posed)
            gv = _skinned(gverts, gweights, posed)
            o_wall = _walls(ov, side, planes, STATIONS)
            g_wall = _walls(gv, side, planes, STATIONS)
            for cell, r in o_wall.items():
                if cell in g_wall:
                    worst = max(worst, r - g_wall[cell])
    return worst


@needs_templates
@needs_gloves
@pytest.mark.parametrize("which", ["sydney", "joy", "clover"])
def test_a_posed_wrist_no_longer_stands_through_the_glove_cuff(which):
    """The capture's bug, as a number.

    Measured on the shipped mesh under wrist extension and forearm twist - the rotations a weapon
    pose puts on the wrist - against three of the game's female gloves, the wrist's wall is at most
    0.16 cm outside a glove's now. On the D70 build, which these passes replaced, the same
    measurement read 0.27 cm against Sydney and 0.32 cm against Joy, and Joy's cuff was pushed
    through in every pose; it is now inside it everywhere.
    """
    if not BODY.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    worst = _worst_protrusion(which)
    assert worst < 0.20, f"{which}: the wrist still stands {worst:.2f} cm outside the cuff"
