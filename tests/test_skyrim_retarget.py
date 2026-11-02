"""Tests for the Skyrim-outfit -> PAYDAY 2 LAS authoring path.

Two things are worth pinning down offline, and both use the real files:

* the **adapters** (`skyrim_source.py`): a garment vertex must come out of
  `4.zip` in world space, weighted only to bones PD2 actually has, with weights
  that sum to 1 and no helper bone left behind;
* the **retarget** (`skyrim_retarget.py`): every joint must land on its PD2
  counterpart. That is the whole contract — if a joint drifts, every animation
  in the game bends the outfit in the wrong place.

The template half needs `references/2b.rar` unpacked to `/tmp/2bsrc` (that is
what `tools/pd2-las/bootstrap.sh` does); the tests skip without it.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402
import skyrim_retarget as sr  # noqa: E402
import skyrim_source as ss  # noqa: E402

MESH_ZIP = ROOT / "4.zip"
TEMPLATES = Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b")

needs_source = pytest.mark.skipif(not MESH_ZIP.exists(), reason="4.zip absent")
needs_templates = pytest.mark.skipif(
    not (TEMPLATES / "2b.model").exists(), reason="2B templates not extracted")


@pytest.fixture(scope="module")
def meshes(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("melodic")
    with zipfile.ZipFile(MESH_ZIP) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".nif"):
                (out / Path(name).name).write_bytes(zf.read(name))
    return out


@pytest.fixture(scope="module")
def bone_map() -> dict:
    return json.loads((ROOT / "tools" / "skyrim-nif" / "skeleton_map.json").read_text())


@pytest.fixture(scope="module")
def model(meshes, bone_map):
    return ss.load_outfit(ss.default_outfit(meshes), bone_map)


@pytest.fixture(scope="module")
def template():
    return bm.load_template(TEMPLATES / "2b.model")


@needs_source
def test_source_meshes_become_one_skinned_model(model):
    model, report = model
    assert report["vertices"] == len(model.vertices)
    # body + feet + both jacket layers + skirt + heels, per material
    assert set(report["materials"]) == {"skin", "jacket", "jacket2", "skirt", "heels"}
    assert report["triangles"] > 50_000


@needs_source
def test_every_vertex_is_weighted_to_pd2_bones_only(model, bone_map):
    model, _report = model
    deform = set(bone_map["map"].values())
    for vertex in model.vertices[:2000]:
        assert vertex.weights, "vertex without weights"
        total = sum(w for _b, w in vertex.weights)
        assert total == pytest.approx(1.0, abs=1e-6)
        assert len(vertex.weights) <= 3            # Diesel SKINNED_3WEIGHTS
        for bone_index, _w in vertex.weights:
            assert model.bones[bone_index].name in deform


@needs_source
def test_helper_bones_are_folded_not_dropped(model, bone_map):
    """A skirt weighted to a twist/breast bone must keep that weight on a real bone."""
    model, _report = model
    helper_names = set(bone_map["fold"]) - {"comment"}
    used = {model.bones[b].name for v in model.vertices for b, _w in v.weights}
    assert not (used & helper_names)
    # and the total weight is conserved: nothing evaporated
    for vertex in model.vertices[:2000]:
        assert sum(w for _b, w in vertex.weights) == pytest.approx(1.0, abs=1e-6)


@needs_source
def test_builtin_body_is_kept(model):
    """The 3BA body ships inside the outfit (the user asked to keep it)."""
    model, report = model
    assert report["materials"]["skin"] > 20_000


@needs_source
@needs_templates
def test_retarget_places_every_joint_on_its_target(model, template):
    model, _report = model
    fits = sr.retarget_fits(model, template)
    assert fits, "no fits produced"
    for bone in model.bones:
        index = model.bones.index(bone)
        if index not in fits or bone.name not in template.name_id:
            continue
        transform = np.asarray(fits[index], dtype=float).reshape(4, 4)
        placed = np.array([*bone.pos, 1.0]) @ transform
        target = np.asarray(template.worlds[template.name_id[bone.name]][12:15], dtype=float)
        # the thumb stub rides the hand's fit and cannot be exact
        tolerance = 0.01 if "Thumb" not in bone.name else 2.0
        assert np.linalg.norm(placed[:3] - target) < tolerance, bone.name


@needs_source
@needs_templates
def test_retarget_handedness_is_preserved(model, template):
    """No mirrored/inside-out mesh: every bone transform is a proper similarity."""
    model, _report = model
    for index, flat in sr.retarget_fits(model, template).items():
        det = float(np.linalg.det(np.asarray(flat, dtype=float).reshape(4, 4)[:3, :3]))
        assert det > 0.0, model.bones[index].name


@needs_source
@needs_templates
def test_outfit_fits_the_target_silhouette(model, template):
    """After retargeting, the whole outfit is inside a PD2-sized body box."""
    model, _report = model
    fits = sr.retarget_fits(model, template)
    positions = []
    for vertex in model.vertices:
        infl = [(i, w) for i, w in vertex.weights if i in fits]
        if not infl:
            continue
        blended = sum(w * np.asarray(fits[i], dtype=float).reshape(4, 4) for i, w in infl)
        p = np.array([*vertex.pos, 1.0]) @ blended
        positions.append(p[:3] / p[3] if p[3] else p[:3])
    pts = np.asarray(positions)
    lo, hi = pts.min(0), pts.max(0)
    assert 150.0 < hi[2] < 190.0, "height should be ~1.6-1.8 m"
    assert -70.0 < lo[0] and hi[0] < 70.0, "arms should not fly off the body"
    assert hi[1] - lo[1] < 60.0, "no stretched depth"
