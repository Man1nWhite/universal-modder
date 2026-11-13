"""The first-person unit must carry the hands it was given.

A bug that shipped in the first hand-fixed pack and was not visible offline:
the viewmodel cut was a fixed bone list ending at ``HandThumb1``, so every
vertex dominated by a finger bone was dropped from ``fps_*.model`` while the
third-person unit kept it (the heister holds her gun with two stumps in first
person). It is item 16 of ``knowledge/games/payday-2/las-moog-outfit-porting.md``.

These tests pin the rule of the cut, `build_models.is_fps_arm_bone` and
`extract_bones`, which the Christie builder cuts its first-person arms with.
The pack the bug shipped in was the cancelled Skyrim outfit; the tests that
re-read that pack went with it on 2026-11-13.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402


@pytest.mark.parametrize("name", [
    "LeftShoulder", "LeftArm", "LeftForeArm", "RightForeArm",
    "LeftHand", "RightHand",
    "LeftHandThumb1", "LeftHandThumb2", "LeftHandThumb3",
    "LeftHandIndex1", "RightHandIndex3",
    "LeftHandMiddle2", "RightHandMiddle3",
    "LeftHandRing1", "RightHandRing3",
    "LeftHandPinky1", "RightHandPinky2", "LeftHandPinky3",
])
def test_fps_cut_covers_the_whole_hand(name):
    """Every hand and finger bone belongs to the viewmodel."""
    assert bm.is_fps_arm_bone(name)


@pytest.mark.parametrize("name", [
    "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftUpLeg", "RightLeg", "LeftFoot", "RightFoot",
])
def test_fps_cut_leaves_the_body_behind(name):
    """The viewmodel is arms only — the torso, legs and head stay out."""
    assert not bm.is_fps_arm_bone(name)


def _finger_group() -> bm.Group:
    """One palm quad plus one pinky-tip quad, welded to nothing."""
    g = bm.Group(name="body")
    g.palette = ["Hips", "LeftHand", "LeftHandPinky3"]
    g.verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0),
               (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0)]
    g.normals = [(0.0, 0.0, 1.0)] * len(g.verts)
    g.uvs = [(0.0, 0.0)] * len(g.verts)
    g.weights = [
        [(0, 1.0)], [(0, 1.0)], [(0, 1.0)],          # torso (dropped)
        [(1, 1.0)], [(1, 1.0)], [(1, 1.0)],          # palm
    ]
    # a second slice for the finger tip, dominated by the pinky's last bone
    g.weights += []
    g.verts += [(4.0, 0.0, 0.0), (5.0, 0.0, 0.0), (5.0, 1.0, 0.0)]
    g.normals += [(0.0, 0.0, 1.0)] * 3
    g.uvs += [(0.0, 0.0)] * 3
    g.weights += [[(2, 1.0)], [(2, 1.0)], [(2, 1.0)]]
    g.faces = [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    g.slices = [("body", 0, 0, 1, 3), ("body", 3, 3, 1, 3),
                ("body", 6, 6, 1, 3)]
    g.mat_slots = ["mtr_body", "mtr_body", "mtr_body"]
    return g


def test_fixed_bone_list_would_drop_the_fingers():
    """The regression itself: the old list loses the finger slice."""
    g = _finger_group()
    old = bm.extract_bones(g, bm.FPS_BONES, "arms")
    assert len(old.verts) == 3           # torso out, palm in, pinky gone
    assert len(old.faces) == 1
    new = bm.extract_bones(g, bm.is_fps_arm_bone, "arms")
    assert len(new.verts) == 6           # ... and the finger tip is kept
    assert len(new.faces) == 2


def test_extract_bones_still_takes_a_name_list():
    g = _finger_group()
    keep = bm.extract_bones(g, {"LeftHand", "LeftHandPinky3"}, "arms")
    assert len(keep.verts) == 6


def _group(verts, faces, palette, weights) -> bm.Group:
    g = bm.Group(name="t")
    g.verts = [tuple(map(float, v)) for v in verts]
    g.normals = [(0.0, 0.0, 1.0)] * len(verts)
    g.uvs = [(0.5, 0.5)] * len(verts)
    g.palette = palette
    g.weights = weights
    g.faces = list(faces)
    g.mat_slots = ["mtr_body"]
    g.slices = [("skin", 0, 0, len(faces), len(verts))]
    return g


def test_extract_bones_keeps_only_dominated_geometry():
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (5, 5, 5), (6, 5, 5), (5, 6, 5)]
    faces = [(0, 1, 2), (3, 4, 5)]
    weights = [[(0, 1.0)]] * 3 + [[(1, 1.0)]] * 3
    g = _group(verts, faces, ["LeftArm", "Hips"], weights)
    out = bm.extract_bones(g, ["LeftArm"], "arms")
    assert len(out.verts) == 3 and len(out.faces) == 1
    assert out.palette == ["LeftArm", "Hips"]
    assert out.slices[0][:2] == ("skin", 0)
    # every vertex still carries its weight row
    assert out.weights[0] == [(0, 1.0)]


def test_extract_bones_refuses_an_empty_selection():
    g = _group([(0, 0, 0)], [(0, 0, 0)], ["Hips"], [[(0, 1.0)]])
    with pytest.raises(SystemExit):
        bm.extract_bones(g, ["LeftArm"], "arms")
