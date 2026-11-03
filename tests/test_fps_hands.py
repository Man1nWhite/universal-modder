"""The first-person unit must carry the hands it was given.

Two bugs shipped in the first hand-fixed pack, and neither was visible offline:

1. the viewmodel cut was a fixed bone list ending at ``HandThumb1``, so every
   vertex dominated by a finger bone was dropped from ``fps_*.model`` while the
   third-person unit kept it (the heister holds her gun with two stumps in
   first person);
2. ``fps_*.material_config`` never declared ``mtr_hands``, the material the
   grafted hands use, so the viewmodel referenced a material the game cannot
   resolve.

Both are item 16 of ``knowledge/games/payday-2/las-moog-outfit-porting.md``.
These tests pin the rule and re-check the shipped pack, because the failure
mode is "third person fine, first person broken".
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402

DIST = REPO / "dist" / "BusinessWoman_LAS.zip"
UNIT = "BusinessWoman_LAS/assets/units/businesswoman/skins/businesswoman"
PACK_MATERIALS = ("mtr_body", "mtr_hands", "mtr_heels", "mtr_jacket",
                  "mtr_jacket2", "mtr_necklace", "mtr_skirt", "shadow_caster")


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


# --------------------------------------------------------------- shipped pack

def _model_facts(data: bytes):
    """(material hashes, per-node finger-dominant vertex counts)."""
    mf = dm.ModelFile.read(data)
    hashes = [dm.decode_material(s.payload)["name_hash"]
              for s in mf.by_type(dm.MATERIAL)]
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    names = {dm.hash64(n): n for n in hl["names"]}
    objs = {}
    for s in mf.sections:
        if s.type == dm.OBJECT3D:
            objs[s.id] = dm.decode_object3d(s.payload)
        elif s.type == dm.MODEL_DATA:
            objs[s.id] = dm.decode_model_data(s.payload)
    id_name = {sid: names.get(o["name_hash"], "") for sid, o in objs.items()}

    fingers: dict[str, int] = {}
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if not md.get("atoms"):
            continue
        try:
            gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            pal = [id_name.get(i, "") for i in dm.decode_skinbones(
                mf.by_id(md["skinbones"]).payload)["objects"]]
        except (ValueError, KeyError):
            continue                           # collision node, not a mesh
        for bi, bw in zip(geo["blendindices"], geo["blendweights"]):
            k = max(range(len(bw)), key=lambda j: bw[j])
            name = pal[bi[k]] if bi[k] < len(pal) else ""
            if any(t in name for t in
                   ("Thumb", "Index", "Middle", "Ring", "Pinky")):
                fingers[name] = fingers.get(name, 0) + 1
    return hashes, fingers


def _config_names(blob: bytes) -> set[str]:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(blob)
    return {m.get("name") for m in root.iter("material")}


@pytest.mark.skipif(not DIST.exists(), reason="pack not built in this checkout")
def test_shipped_fps_unit_declares_every_material_it_references():
    """A model may only reference materials its own config defines.

    Only *our* materials are checked: the models also carry the five orphaned
    2B template material sections (kept deliberately — "Leave 2B."), which no
    render atom of ours points at and which must not be re-declared.
    """
    by_hash = {dm.hash64(n): n for n in PACK_MATERIALS}
    with zipfile.ZipFile(DIST) as z:
        for model, config in (
                ("businesswoman.model", "businesswoman.material_config"),
                ("fps_businesswoman.model", "fps_businesswoman.material_config")):
            hashes, _ = _model_facts(z.read(f"{UNIT}/{model}"))
            defined = {dm.hash64(n) for n in _config_names(z.read(f"{UNIT}/{config}"))}
            used = {by_hash[h] for h in hashes if h in by_hash}
            missing = used - {by_hash[h] for h in defined if h in by_hash}
            assert used, f"{model} references none of our materials?"
            assert not missing, f"{model} needs {sorted(missing)} in {config}"


@pytest.mark.skipif(not DIST.exists(), reason="pack not built in this checkout")
def test_shipped_fps_unit_keeps_the_fingers():
    """The viewmodel must carry the same finger chains as the body."""
    with zipfile.ZipFile(DIST) as z:
        _, tpp = _model_facts(z.read(f"{UNIT}/businesswoman.model"))
        _, fps = _model_facts(z.read(f"{UNIT}/fps_businesswoman.model"))
    assert tpp, "no finger-dominant vertices in the body — graft lost?"
    missing = {b for b in tpp if b not in fps}
    assert not missing, f"fps unit dropped {sorted(missing)}"
    lost = sum(tpp[b] - fps.get(b, 0) for b in tpp)
    total = sum(tpp.values())
    assert lost <= total * 0.02, f"fps unit lost {lost}/{total} finger verts"
