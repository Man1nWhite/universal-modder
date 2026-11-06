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
        viewers = ["front", "side", "iso", "top", "bottom"] if "{view}" in pat else [None]
        for v in viewers:
            emitted.add(pat if v is None else pat.replace("{view}", v))
    assert emitted, "main() emits no per-stem renders at all"

    missing = []
    for name in sorted(documented):
        body = name.replace("christie_slim", "{stem}").replace("christie", "{stem}")
        if body not in emitted:
            missing.append(name)
    assert not missing, (
        "documented in CHRISTIE.md but never written by the renderer: "
        f"{missing} (main() emits {sorted(emitted)})")
