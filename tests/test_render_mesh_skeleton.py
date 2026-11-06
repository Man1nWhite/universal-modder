"""The pose preview has to be able to lie *loudly*, not plausibly.

`render_mesh_skeleton.skin_verts` feeds the posed overlays in
`docs/pd2-las/renders/`, which is how a human decides whether a mesh sits on
its skeleton. It has silently produced garbage twice (2026-11-06), both times
because the identity pose round-trips no matter how the matrices are
composed: a transposed matrix, or `pose @ inv_bind` instead of
`inv_bind @ pose`, are both exactly the identity in the bind pose and both
fling verts tens of centimetres once anything moves.

So these tests do not check the bind pose. They bend an elbow and assert the
things a wrong composition cannot fake: joints stay put, nothing stretches,
the limb that did not move does not move, and a hand goes where the bone says.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

def _templates() -> Path:
    """The 2B reference pack, wherever bootstrap.sh / the sandbox put it."""
    import os

    for cand in (Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"),
                 Path(os.environ.get("HOME", "/home/user"))
                 / "tmpsrc/2B - LAS/assets/units/2b/skins/2b"):
        if (cand / "2b.model").is_file():
            return cand
    env = os.environ.get("PD2_2B_TEMPLATES")
    if env and (Path(env) / "2b.model").is_file():
        return Path(env)
    pytest.skip("2B templates not extracted (run tools/pd2-las/bootstrap.sh)")


TEMPLATES = _templates()
PACK = REPO / "dist" / "Christie_LAS.zip"

pytestmark = pytest.mark.skipif(
    not PACK.is_file(),
    reason="Christie base pack not built (run tools/pd2-las/bootstrap.sh)",
)


def _fixtures():
    import diesel_model as dm
    import build_models as bm
    import render_mesh_skeleton as rms

    tpl = bm.load_template(TEMPLATES / "2b.model")
    with zipfile.ZipFile(PACK) as zf:
        geo = rms.g_body_geo(zf, "Christie_LAS", "christie")
        mf = dm.ModelFile.read(zf.read(
            "Christie_LAS/assets/units/christie/skins/christie/christie.model"))
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    sk = None
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if next((n for n in hl if dm.hash64(n) == md["name_hash"]), "") == "g_body" \
                and md.get("version") == 3:
            sk = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
            break
    assert sk is not None
    return rms, tpl, geo, sk


def _joints(tpl, worlds):
    return {tpl.id_name[sid]: np.array(w[12:15], float) for sid, w in worlds.items()}


def test_bind_pose_round_trips():
    rms, tpl, geo, sk = _fixtures()
    v0 = np.array(geo["verts"], float)
    got = rms.skin_verts(geo, sk, rms.posed_worlds(tpl, {}))
    assert np.abs(got - v0).max() < 1e-3


def test_pose_pivots_each_bone_about_its_own_head():
    """A posed bone must not move its own joint: PD2 pivots the child there."""
    rms, tpl, _, _ = _fixtures()
    rest = _joints(tpl, rms.posed_worlds(tpl, {}))
    posed = _joints(tpl, rms.posed_worlds(tpl, {"LeftForeArm": (0, -22.0)}))
    for name in ("Hips", "Spine", "Neck", "LeftShoulder", "LeftArm",
                 "LeftForeArm", "RightArm", "RightForeArm"):
        assert np.allclose(rest[name], posed[name], atol=1e-6), (
            f"{name} joint moved {np.linalg.norm(rest[name] - posed[name]):.2f} cm "
            f"when the elbow bent")
    # ...and the child of the posed bone must actually move
    assert np.linalg.norm(rest["LeftHand"] - posed["LeftHand"]) > 5.0


def test_elbow_bend_does_not_stretch_the_mesh():
    """No triangle edge may grow: a wrong skinning composition flings verts.

    Measured on the shipped pack: the correct order grows an edge by at most
    ~1 cm (a 0.8 cm edge at the crease, linear-blend candy-wrapper on a 22 deg
    bend), while ``pose @ inv_bind`` grows 1630 edges by up to 32 cm. The
    threshold sits in that gap with room for a different posing recipe.
    """
    rms, tpl, geo, sk = _fixtures()
    v0 = np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    e0 = np.linalg.norm(v0[faces] - v0[np.roll(faces, 1, axis=1)], axis=2)
    pose = {f"{s}ForeArm": (0, -22.0) for s in ("Left", "Right")}
    v1 = rms.skin_verts(geo, sk, rms.posed_worlds(tpl, pose))
    e1 = np.linalg.norm(v1[faces] - v1[np.roll(faces, 1, axis=1)], axis=2)
    growth = e1 - e0
    assert growth.max() <= 3.0, (
        f"an edge grew {growth.max():.1f} cm when the elbow bent - skinning "
        f"matrices are composed in the wrong order")
    stretched = int((growth > 2.0).sum())
    assert stretched == 0, f"{stretched} edges grew by more than 2 cm"
    # a pure stretch has to stay bounded in absolute terms too
    assert e1.max() <= 15.0, f"longest posed edge is {e1.max():.1f} cm"


def test_posed_mesh_stays_where_the_bones_are():
    """No vertex may end up far from the skeleton that drives it."""
    rms, tpl, geo, sk = _fixtures()
    pose = {**{f"{s}Arm": (0, 6.0) for s in ("Left", "Right")},
            **{f"{s}ForeArm": (0, -22.0) for s in ("Left", "Right")},
            **{f"{s}Hand": (0, -38.0) for s in ("Left", "Right")}}
    v1 = rms.skin_verts(geo, sk, rms.posed_worlds(tpl, pose))
    joints = np.array(list(_joints(tpl, rms.posed_worlds(tpl, pose)).values()))
    # every vertex within 40 cm of its nearest joint (the body is ~164 cm tall
    # and limbs are <50 cm, so a correct pose is far inside this)
    d = np.min(np.linalg.norm(v1[:, None, :] - joints[None, :, :], axis=2), axis=1)
    assert d.max() <= 40.0, (
        f"a posed vertex is {d.max():.1f} cm from the nearest joint")
    # and the arms specifically: no vertex further from a wrist than a forearm
    for side in ("Left", "Right"):
        wrist = _joints(tpl, rms.posed_worlds(tpl, pose))[f"{side}Hand"]
        near = np.linalg.norm(v1 - wrist, axis=1)
        assert near.min() < 4.0, f"{side}: no mesh near the wrist joint"


def test_bind_matrices_are_inverse_bind_worlds():
    """``skinbones['rotations']`` is W^-1 per palette entry (row-vector)."""
    import diesel_model as dm

    _, tpl, _, sk = _fixtures()
    ident = np.eye(4)
    for k, bid in enumerate(sk["objects"]):
        w = np.array(tpl.worlds[bid], float).reshape(4, 4)
        r = np.array(sk["rotations"][k], float).reshape(4, 4)
        assert np.abs(w @ r - ident).max() < 1e-3, (
            f"{tpl.id_name[bid]}: rotations[{k}] is not the inverse bind world")
        assert dm.mat_mul(tuple(r.flatten()), tuple(w.flatten())) is not None


def _documented_render_names(item: str) -> set[str]:
    """The render filenames CHRISTIE.md tells a reader to look at.

    The doc is the only place a reader learns which images exist, so it is also
    the list the renderer has to be able to produce. Reading it here keeps the
    two from drifting: before 2026-11-06 the doc named
    `christie_base_skel_top.png`, the renderer wrote `christie_skel_top.png`,
    and half the committed set could not be rebuilt at all.
    """
    import re

    doc = (REPO / "docs" / "pd2-las" / "CHRISTIE.md").read_text(encoding="utf-8")
    section = doc.split("## Mesh + skeleton renders", 1)[1].split("\n## ", 1)[0]
    names: set[str] = set()
    for m in re.finditer(r"`([a-z0-9_{},*]+\.png)`", section):
        pat = m.group(1)
        # expand the {a,b} shorthand the doc uses
        parts = [pat]
        while any("{" in p for p in parts):
            nxt = []
            for p in parts:
                b = re.search(r"\{([^}]*)\}", p)
                if not b:
                    nxt.append(p)
                    continue
                nxt.extend(p[:b.start()] + opt + p[b.end():]
                           for opt in b.group(1).split(","))
            parts = nxt
        names.update(n.replace("*", "slim" if "slim" in n else "base")
                     for n in parts)
    return names


def test_render_cli_writes_every_file_the_docs_name():
    """A doc that names images the tool cannot produce is a dead end."""
    import re

    doc = (REPO / "docs" / "pd2-las" / "CHRISTIE.md").read_text(encoding="utf-8")
    section = doc.split("## Mesh + skeleton renders", 1)[1].split("\n## ", 1)[0]
    # the two composites are made outside the renderer and are called out as such
    documented = set()
    for m in re.finditer(r"`(christie[a-z_{},]*\.png)`", section):
        pat = m.group(1)
        if "fit_before_after" in pat:
            continue
        parts = [pat]
        while any("{" in q for q in parts):
            nxt = []
            for q in parts:
                b = re.search(r"\{([^}]*)\}", q)
                if b is None:
                    nxt.append(q)
                    continue
                nxt.extend(q[:b.start()] + opt + q[b.end():]
                           for opt in b.group(1).split(","))
            parts = nxt
        documented.update(parts)
    assert len(documented) >= 14, f"the render list shrank: {sorted(documented)}"

    src = (REPO / "tools" / "pd2-las" / "render_mesh_skeleton.py").read_text(encoding="utf-8")
    # `--source` renders the reference model under its own stem; fold those
    # patterns in too so the doc can list both kinds in one section
    src_body = src[src.index("def render_source("):src.index("def main(")]
    main_body = src[src.index("def main("):]
    for m in re.finditer(r'f"\{stem\}_([a-z_{}]+)\.png"', src_body):
        main_body += "\n" + f'f"{{stem}}_source_{m.group(1)}.png"' 
    emitted = set()
    for m in re.finditer(r'f"\{stem\}_([a-z_{}]+)\.png"', main_body):
        pat = "{stem}_" + m.group(1) + ".png"
        if "{tag}" in pat:
            viewers = ["front", "side"]
        elif "{view}" in pat or "{stem}" in pat and pat.count("{") == 1 and "{view}" not in pat:
            viewers = ["front", "side", "iso", "top", "bottom"]
        else:
            viewers = [None]
        for v in viewers:
            emitted.add(pat if v is None else pat.replace("{view}", v)
                        .replace("{tag}", "front" if v == "front" else "side"))
    assert emitted, "main() emits no per-stem renders at all"

    missing = []
    for name in sorted(documented):
        body = name.replace("christie_slim", "{stem}").replace("christie", "{stem}")
        if body not in emitted:
            missing.append(name)
    assert not missing, (
        "documented in CHRISTIE.md but never written by the renderer: "
        f"{missing} (main() emits {sorted(emitted)})")


def test_projection_never_negates_both_screen_axes():
    """`bottom` came from `(-x, -y)` - a 180 degree spin, not a new viewpoint.

    Negating both axes maps every point to the point diametrically opposite the
    model origin, which projects the model from *above* and then rotates the
    picture. On a body that is roughly left/right and front/back symmetric the
    outline is unaffected, so the mistake is invisible in the finished image -
    which is exactly why it needs asserting on the maths rather than the
    pixels. A camera below keeps model +x on the right and flips only y.
    """
    import render_mesh_skeleton as rms

    p = np.array([[3.0, 5.0, 7.0]])
    assert rms.project(p, "front")[0].tolist() == [3.0, 7.0]    # (x, z)
    assert rms.project(p, "side")[0].tolist() == [5.0, 7.0]     # (y, z)
    assert rms.project(p, "top")[0].tolist() == [3.0, 5.0]      # (x, y)
    assert rms.project(p, "bottom")[0].tolist() == [3.0, -5.0]  # (x, -y)
    # no view may be another view point-mirrored: that is a rotation of the
    # same camera, and it silently passes every "does it look right" review
    for view in ("front", "side", "top", "bottom"):
        for other in ("front", "side", "top", "bottom"):
            if other == view:
                continue
            a = rms.project(p, view)[0]
            b = -rms.project(p, other)[0]
            assert not np.allclose(a, b), f"{view} is {other} rotated 180 degrees"


def test_views_are_not_duplicates():
    """Cheap sanity net: two different view names must not draw one picture."""
    import tempfile

    from PIL import Image

    rms, tpl, geo, _sk = _fixtures()
    bones = rms.skeleton(tpl)
    with tempfile.TemporaryDirectory() as td:
        sil = {}
        for view in ("front", "side", "iso", "top", "bottom"):
            p = Path(td) / f"{view}.png"
            rms.render(geo, bones, view, p)
            a = np.array(Image.open(p).convert("RGB")).astype(int)
            m = np.abs(a - np.array([24, 24, 28])).sum(2) > 10
            m[0:70, 0:340] = False
            sil[view] = m
    for view, m in sil.items():
        assert m.sum() > 20000, f"{view} drew almost nothing ({m.sum()} px)"
    for a, b in (("front", "side"), ("front", "top"), ("side", "top")):
        iou = (sil[a] & sil[b]).sum() / max((sil[a] | sil[b]).sum(), 1)
        assert iou < 0.95, f"{a} and {b} draw the same silhouette (IoU {iou:.2f})"


def test_depth_key_points_towards_the_camera():
    """Painter's algorithm needs the far side drawn first."""
    import render_mesh_skeleton as rms
    v = np.array([[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]])
    # top: camera at +z, so z=2 is nearer than z=1
    d = rms.depth_towards_camera("top", v)
    assert d[1] > d[0]
    # bottom: camera at -z, so z=1 is nearer
    d = rms.depth_towards_camera("bottom", v)
    assert d[0] > d[1]
    # front: camera at +y
    d = rms.depth_towards_camera("front", v)
    assert d[1] > d[0]


def test_close_up_subset_is_only_the_limb():
    """A close-up may contain the limb and nothing else.

    The close-ups used to be crop windows on (x, z). A window is a slab through
    an orthographic scene, so the "left forearm" crop also caught the torso, the
    far shoulder and the hip, and the bone read as buried in cloth. Selecting by
    3D distance to the bone chain removes that by construction - so assert the
    construction.
    """
    import render_mesh_skeleton as rms

    _rms, tpl, geo, _sk = _fixtures()
    bones = rms.skeleton(tpl)
    arm = [p for n, p, _ in bones if n in ("LeftArm", "LeftForeArm", "LeftHand")]
    assert len(arm) == 3

    radius = 8.0
    sub = rms._subset_near_polyline(geo, arm, radius=radius)

    # every kept vertex is within the radius (plus the closing pad) of the chain
    v = np.array(sub["verts"], float)
    chain = np.array(arm, float)
    d = np.full(len(v), np.inf)
    for a, b in zip(chain[:-1], chain[1:]):
        ab = b - a
        t = np.clip((v - a) @ ab / float(ab @ ab), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(v - (a + np.outer(t, ab)), axis=1))
    assert d.max() <= radius + 6.0 + 1e-6, (
        f"a close-up vertex sits {d.max():.1f} cm from the arm bones - the "
        f"crop is picking up the body")

    # and it is a small part of the model, not the whole thing
    assert len(sub["faces"]) < 0.6 * len(geo["faces"])


def test_side_camera_is_on_the_left_of_the_character():
    """`side` must look at the character's left - the side its arm chain is on.

    The character faces +y with up +z, so left is -x, and every `Left*` bone in
    the rig sits at negative x. A camera at -x therefore films the left side and
    the left arm is the *near* limb; a camera at +x would shoot it through the
    torso, and a correctly-fitted bone would look buried inside the body. This
    pins the handedness so the mistake cannot come back in either direction.
    """
    import render_mesh_skeleton as rms

    cam = np.array(rms.CAMERA_DIR["side"], float)
    assert cam[0] < 0, "`side` must look along -x to face the character's left"

    _rms, tpl, _geo, _sk = _fixtures()
    arm = {n: np.array(p, float) for n, p, _ in rms.skeleton(tpl)}
    lf = arm["LeftForeArm"]
    assert lf[0] < 0, "left limbs are expected at negative x in this rig"

    # nearer camera <=> larger depth key, and the left arm must be the near one
    d_left = rms.depth_towards_camera("side", np.array([lf]))[0]
    d_far = rms.depth_towards_camera("side", np.array([lf * np.array([-1, 1, 1])]))[0]
    assert d_left > d_far, (
        "from `side` the left arm must be nearer than the mirrored point on the "
        "character's right")



def test_close_up_bones_are_only_the_limb_subtree():
    """No attachment nodes, capsules or context bones in a limb close-up.

    Two failure modes this guards, both seen in the images: proximity alone
    pulled in a weapon attachment and `LeftShoulder` (50 bones within 16 cm of
    the arm), whose parent lines are drawn to joints that are not in the
    picture and read as stray bones crossing the crop; and adding a context
    parent for the shoulder drew a line from the shoulder in to the chest, which
    looked like a bone escaping the sleeve.
    """
    import render_mesh_skeleton as rms

    _rms, tpl, _geo, _sk = _fixtures()
    bones = rms.skeleton(tpl)
    arm = [p for n, p, _ in bones if n in ("LeftArm", "LeftForeArm", "LeftHand")]
    keep = {n for n, _p, _par in rms._bones_near(arm, bones, radius=3.0)}

    assert {"LeftArm", "LeftForeArm", "LeftHand"} <= keep
    assert any(n.startswith("LeftHandIndex") for n in keep), "fingers dropped"
    junk = [n for n in keep
            if any(t in n for t in ("locator", "capsule", "weapon", "_end"))]
    assert not junk, f"non-anatomy bones in a limb close-up: {junk}"

    # no ancestor of the limb may sneak in: `render()` draws a line to the
    # parent whenever it is in the list, so one context bone above the shoulder
    # is enough to draw a line across the crop, and reading it looks like a bone
    # escaping the arm rather than a camera choice
    parent = {n: p for n, _h, p in bones}
    node = "LeftArm"
    ancestors = set()
    while parent.get(node):
        node = parent[node]
        ancestors.add(node)
    leaked = keep & ancestors
    assert not leaked, (
        f"context bones above the limb leaked into the close-up: {sorted(leaked)}")
