"""Tests for the LAS restart pipeline: ME2 COLLADA import, PD2 rig retarget,
DODB model authoring and the 2B-contract pack assembly.

Synthetic fixtures only, except the integration test which uses the tracked
source zip (skipped when absent).
"""
import importlib.util
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PD2 = ROOT / "tools" / "pd2-port"
sys.path.insert(0, str(PD2))
SOURCE_ZIP = ROOT / ("PC _ Computer - Mass Effect 2 - Non-Playable "
                     "Characters - Miranda Lawson (Romance).zip")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, PD2 / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


me2_dae = _load("me2_dae", "me2_dae.py")
rig_target = _load("rig_target", "rig_target.py")
las_model = _load("las_model", "las_model.py")
dds = _load("dds_las", "dds.py")
dmodel = _load("dmodel_las", "dmodel.py")


# ---------------------------------------------------------------- fixtures
TINY_DAE = """<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
 <asset>
  <unit name="meter" meter="1"/>
  <up_axis>Z_UP</up_axis>
 </asset>
 <library_images>
  <image id="tex_png" name="tex_png"><init_from>tex.png</init_from></image>
 </library_images>
 <library_effects>
  <effect id="fx"><profile_COMMON><technique sid="t"><lambert>
   <diffuse><texture texture="tex_png-surface"/></diffuse>
  </lambert></technique></profile_COMMON></effect>
 </library_effects>
 <library_materials>
  <material id="Body_1-material" name="Body_1-material">
   <instance_effect url="#fx"/></material>
 </library_materials>
 <library_geometries>
  <geometry id="mesh1" name="mesh1">
   <mesh>
    <source id="pos">
     <float_array id="posa" count="9">0 0 0  1 0 0  0 1 0</float_array>
     <technique_common><accessor source="#posa" count="3" stride="3">
      <param name="X" type="float"/><param name="Y" type="float"/>
      <param name="Z" type="float"/></accessor></technique_common>
    </source>
    <source id="nrm">
     <float_array id="nrma" count="9">0 0 1  0 0 1  0 0 1</float_array>
     <technique_common><accessor source="#nrma" count="3" stride="3">
      <param name="X" type="float"/><param name="Y" type="float"/>
      <param name="Z" type="float"/></accessor></technique_common>
    </source>
    <source id="uv">
     <float_array id="uva" count="6">0 0  1 0  0 1</float_array>
     <technique_common><accessor source="#uva" count="3" stride="2">
      <param name="S" type="float"/><param name="T" type="float"/>
      </accessor></technique_common>
    </source>
    <vertices id="vin"><input semantic="POSITION" source="#pos"/></vertices>
    <triangles material="Body_1-material" count="1">
     <input semantic="VERTEX" source="#vin" offset="0"/>
     <input semantic="NORMAL" source="#nrm" offset="1"/>
     <input semantic="TEXCOORD" source="#uv" offset="2"/>
     <p>0 0 0  1 1 1  2 2 2</p>
    </triangles>
   </mesh>
  </geometry>
 </library_geometries>
 <library_controllers>
  <controller id="skin1">
   <skin source="#mesh1">
    <bind_shape_matrix>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1</bind_shape_matrix>
    <source id="joints">
     <Name_array id="ja" count="2">root BoneA</Name_array>
     <technique_common><accessor source="#ja" count="2" stride="1">
      <param name="JOINT" type="name"/></accessor></technique_common>
    </source>
    <source id="ibm">
     <float_array id="ibma" count="32">1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1  1 0 0 0 0 1 0 0 0 0 1 0 10 0 0 1</float_array>
     <technique_common><accessor source="#ibma" count="2" stride="16">
      <param name="TRANSFORM" type="float4x4"/></accessor></technique_common>
    </source>
    <source id="wts">
     <float_array id="wtsa" count="3">1 1 0.5</float_array>
     <technique_common><accessor source="#wtsa" count="3" stride="1">
      <param name="WEIGHT" type="float"/></accessor></technique_common>
    </source>
    <joints>
     <input semantic="JOINT" source="#joints"/>
     <input semantic="INV_BIND_MATRIX" source="#ibm"/>
    </joints>
    <vertex_weights count="3">
     <input semantic="JOINT" source="#joints" offset="0"/>
     <input semantic="WEIGHT" source="#wts" offset="1"/>
     <vcount>1 1 2</vcount>
     <v>0 0  1 1  0 2 1 2</v>
    </vertex_weights>
   </skin>
  </controller>
 </library_controllers>
 <library_visual_scenes>
  <visual_scene id="s">
   <node id="Scene" name="Scene" type="NODE">
    <matrix sid="transform">1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1</matrix>
    <node id="root" name="root" sid="root" type="JOINT">
     <matrix sid="transform">1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1</matrix>
     <node id="BoneA" name="BoneA" sid="BoneA" type="JOINT">
      <matrix sid="transform">1 0 0 10 0 1 0 20 0 0 1 30 0 0 0 1</matrix>
     </node>
    </node>
    <node id="Body_1" name="Body 1" type="NODE">
     <matrix sid="transform">1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1</matrix>
     <instance_controller url="#skin1">
      <skeleton>#root</skeleton>
      <bind_material><technique_common>
       <instance_material symbol="Body_1-material" target="#Body_1-material"/>
      </technique_common></bind_material>
     </instance_controller>
    </node>
   </node>
  </visual_scene>
 </library_visual_scenes>
</COLLADA>
"""


@pytest.fixture(scope="module")
def tiny_scene():
    return me2_dae.load_dae(TINY_DAE)


def _tmp_rig():
    """Minimal TargetRig: Hips + BoneB at +X, root_point."""
    import math
    ident = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]

    def trans(x, y, z):
        m = [row[:] for row in ident]
        m[3] = [x, y, z, 1.0]
        return m

    entries = [
        {"id": 1, "name": "root_point", "name_hash": f"{dmodel.hash_str('root_point'):016x}",
         "parent_id": 0, "local": trans(0, 0, 0), "world": trans(0, 0, 0)},
        {"id": 2, "name": "Hips", "name_hash": f"{dmodel.hash_str('Hips'):016x}",
         "parent_id": 1, "local": trans(0, 0, 100), "world": trans(0, 0, 100)},
        {"id": 3, "name": "BoneB", "name_hash": f"{dmodel.hash_str('BoneB'):016x}",
         "parent_id": 2, "local": trans(30, 0, 0), "world": trans(30, 0, 100)},
    ]
    return rig_target.TargetRig(
        names=["Hips", "BoneB"],
        world={"Hips": entries[1]["world"], "BoneB": entries[2]["world"]},
        by_name={"Hips": entries[1], "BoneB": entries[2], "root_point": entries[0]},
        entries=entries,
    )


# ---------------------------------------------------------------- me2_dae
def test_dae_import_counts(tiny_scene):
    assert tiny_scene.up_axis == "Z_UP"
    assert len(tiny_scene.meshes) == 1
    m = tiny_scene.meshes[0]
    assert m.name == "Body 1"
    assert len(m.positions) == 3
    assert len(m.triangles) == 1
    assert m.triangles[0] == (0, 1, 2)


def test_dae_matrix_layout_translation_in_last_row(tiny_scene):
    # BoneA local translation is (10, 20, 30) in the file's row-major layout
    j = tiny_scene.joints["BoneA"]
    assert j.world[3][:3] == pytest.approx((10.0, 20.0, 30.0))
    assert j.parent == "root"


def test_dae_weights(tiny_scene):
    m = tiny_scene.meshes[0]
    assert [b.joint for b in m.weights[0]] == ["root"]
    assert [b.joint for b in m.weights[2]] == ["root", "BoneA"]
    assert m.weights[2][1].weight == pytest.approx(0.5)


def test_dae_skips_non_joint_nodes(tiny_scene):
    assert "Scene" not in tiny_scene.joints
    assert "Body 1" not in tiny_scene.joints
    assert set(tiny_scene.joints) == {"root", "BoneA"}


# ---------------------------------------------------------------- bone map
def test_map_joint_core_and_side_swap():
    # In the ME2 COLLADA file Miranda faces -Y with +X = Left; 180 deg Z
    # rotation aligns -Y -> +Y and +X -> -X, so Left* maps to PD2 Left*.
    assert rig_target.map_joint("LeftWrist") == "LeftHand"
    assert rig_target.map_joint("RightWrist") == "RightHand"
    assert rig_target.map_joint("LeftHip") == "LeftUpLeg"
    assert rig_target.map_joint("RightToe") == "RightToeBase"
    assert rig_target.map_joint("root") == "Hips"
    assert rig_target.map_joint("Pelvis") == "Hips"
    assert rig_target.map_joint("Chest") == "Spine"
    assert rig_target.map_joint("Neck1") == "Neck"


def test_map_joint_maps_fingers_to_finger_bones_and_folds_the_face():
    # the guide's PD2 rig has three bones per finger; the source's finger
    # chains map onto them one-to-one so the fingers articulate instead of
    # riding along with the hand
    assert rig_target.map_joint("LeftIndexFinger2") == "LeftHandIndex3"
    assert rig_target.map_joint("RightRingFinger1") == "RightHandRing2"
    assert rig_target.map_joint("LeftThumbFinger") == "LeftHandThumb1"
    assert rig_target.map_joint("RightPinkFinger2") == "RightHandPinky3"
    # the face still folds to the head (PD2 has no facial bones)
    assert rig_target.map_joint("brow_Left") == "Head"
    assert rig_target.map_joint("innerUpperLip_right") == "Head"
    assert rig_target.map_joint("eyeLookBackAt") == "Head"


def test_map_joint_unknown_raises():
    with pytest.raises(KeyError):
        rig_target.map_joint("NotABone")


def test_rig_contract_names_hash_to_their_stored_hashes():
    """The contract's names are recovered by hashing PD2's naming convention.

    Every named bone must hash to the name_hash the 2B model stored, so a
    mis-recovered name cannot slip into the rig.
    """
    rig = json.loads((PD2 / "reference" / "las_rig.json").read_text())
    named = [b for b in rig["bones"] if b.get("name")]
    assert len(named) >= 55
    for b in named:
        assert f"{dmodel.hash_str(b['name']):016x}" == b["name_hash"], b


def test_finger_bones_are_named_in_the_rig_contract():
    rig = json.loads((PD2 / "reference" / "las_rig.json").read_text())
    names = {b["name"] for b in rig["bones"] if b.get("name")}
    for side in ("Left", "Right"):
        for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
            for n in (1, 2, 3):
                assert f"{side}Hand{finger}{n}" in names


def test_finger_bones_carry_weight_in_the_built_model():
    """Mitten hands were a guide-compliance failure: no finger bone had a
    vertex. The retarget must bind the hand's vertices to the finger chains."""
    build = _load("build_las_pack", "build_las_pack.py")
    source = build.load_source(build.SOURCE_ZIP)
    scene = me2_dae.load_dae(source[build.DAE_NAME])
    rig = rig_target.load_target_rig(build.RIG_JSON)
    rigged = {m.name: rig_target.rebind_mesh(m, scene, rig, smooth_iters=2)
              for m in scene.meshes}
    used = set()
    for mesh in rigged.values():
        for weights in mesh.weights:
            for bone, _w in weights:
                used.add(bone)
    finger_bones = {n for n in used if "Hand" in n and n[-1].isdigit()}
    assert len(finger_bones) >= 20, f"only {sorted(finger_bones)} carry weight"


def test_fps_cut_keeps_the_fingers():
    """The FPS unit holds the arm mesh - hands included.

    The fingers' vertices are dominated by the finger bones, so an arm cut
    that only knows the arm bones drops them and the view model loses the
    fingers (the compliance audit's F3 check caught exactly that).
    """
    mesh = rig_target.RiggedMesh(
        name="Body 2", material="mtr_body2", positions=[], normals=[],
        uvs=[], triangles=[],
        weights=[[("RightHandThumb1", 1.0)],
                 [("RightHandIndex3", 0.9), ("RightHand", 0.1)],
                 [("Hips", 1.0)]])
    body, arms = rig_target.split_arm_verts(mesh)
    assert arms == {0, 1}, "finger vertices must stay in the first-person cut"
    assert body == {2}


def test_bone_map_targets_exist_in_donor_rig():
    rig = rig_target.load_target_rig(PD2 / "reference" / "las_rig.json")
    missing = {t for t in rig_target.BONE_MAP.values() if t not in rig.by_name}
    assert not missing, f"BONE_MAP targets missing from las_rig.json: {missing}"


# ---------------------------------------------------------------- retarget
def test_rebind_maps_by_target_bones(monkeypatch):
    """Segment-fit retarget: axis-aligned bones give pure translations."""
    monkeypatch.setitem(rig_target.BONE_MAP, "BoneA", "BoneB")
    ident = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]

    def trans(x, y, z):
        m = [row[:] for row in ident]
        m[3] = [x, y, z, 1.0]
        return m

    joints = {
        "root": me2_dae.Joint("root", None, ident, trans(0, 0, 0)),
        "BoneA": me2_dae.Joint("BoneA", "root", trans(10, 0, 0), trans(10, 0, 0)),
    }
    mesh = me2_dae.Mesh(
        name="m", material="mtr",
        positions=[(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3, uvs=[(0.0, 0.0)] * 3,
        triangles=[(0, 1, 2)],
        weights=[[me2_dae.SkinBind("root", 1.0)],
                 [me2_dae.SkinBind("root", 1.0)],
                 [me2_dae.SkinBind("root", 0.5), me2_dae.SkinBind("BoneA", 0.5)]])
    scene = me2_dae.DaeScene(
        unit_scale=1.0, up_axis="Z_UP", joints=joints, joint_order=list(joints),
        meshes=[mesh], images={}, material_images={})
    rig = _tmp_rig()
    rm = rig_target.rebind_mesh(mesh, scene, rig)
    # root segment +X -> Hips segment +X: pure translation (0,0,100)
    # BoneA segment +X -> BoneB segment +X: pure translation (20,0,100)
    # vertex 2 weighted 50/50: 0.5*(p+(0,0,100)) + 0.5*(p+(20,0,100))
    p = mesh.positions[2]  # (0, 1, 0)
    exp = (p[0] + 10.0, p[1], p[2] + 100.0)
    assert rm.positions[2] == pytest.approx(exp, abs=1e-4)
    assert rm.positions[0] == pytest.approx((0.0, 0.0, 100.0), abs=1e-4)
    assert sum(w for _, w in rm.weights[2]) == pytest.approx(1.0)


def test_rebind_folded_joints_keep_shape(monkeypatch):
    """Many-to-one folds (face->Head, fingers->Hand) must share one operator.

    Per-source-joint operators rigidly misplace fold neighbours: on the real
    face mesh that tore edges apart (median distortion 68%, p95 1117%).
    """
    monkeypatch.setitem(rig_target.BONE_MAP, "Jaw", "BoneB")
    monkeypatch.setitem(rig_target.BONE_MAP, "Brow", "BoneB")
    ident = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]

    def trans(x, y, z):
        m = [row[:] for row in ident]
        m[3] = [x, y, z, 1.0]
        return m

    joints = {
        "Jaw": me2_dae.Joint("Jaw", None, ident, trans(0, 0, 5)),
        "Brow": me2_dae.Joint("Brow", None, ident, trans(0, 0, 20)),
    }
    mesh = me2_dae.Mesh(
        name="face", material="mtr_face",
        positions=[(0.0, 0.0, 5.0), (0.0, 0.0, 6.0), (0.0, 1.0, 20.0)],
        normals=[(0.0, 0.0, 1.0)] * 3, uvs=[(0.0, 0.0)] * 3,
        triangles=[(0, 1, 2)],
        weights=[[me2_dae.SkinBind("Jaw", 1.0)],
                 [me2_dae.SkinBind("Jaw", 1.0)],
                 [me2_dae.SkinBind("Brow", 1.0)]])
    scene = me2_dae.DaeScene(
        unit_scale=1.0, up_axis="Z_UP", joints=joints, joint_order=list(joints),
        meshes=[mesh], images={}, material_images={})
    rig = _tmp_rig()
    rm = rig_target.rebind_mesh(mesh, scene, rig)
    # one shared operator => the folded piece is rigid: pairwise lengths hold
    import math
    for i, j in ((0, 1), (0, 2), (1, 2)):
        assert math.dist(rm.positions[i], rm.positions[j]) == pytest.approx(
            math.dist(mesh.positions[i], mesh.positions[j]), rel=1e-6)


def test_eye_uv_planar_centers_iris():
    """ME2's eye shader placed the iris; plain diffuse sampling needs planar
    UVs or the iris lands on the u-seam and smears (blank pink spheres)."""
    b = _load("build_las_pack_eye", "build_las_pack.py")
    r = 1.5
    pts = []
    for cx in (-3.0, 3.0):
        for dx, dy, dz in ((0, r, 0), (0, -r, 0), (r, 0, 0), (-r, 0, 0),
                           (0, 0, r), (0, 0, -r)):
            pts.append((cx + dx, 3.0 + dy, 174.0 + dz))
    uvs = b.eye_uv_planar(pts)
    # forward pole (0, +r, 0 offset) must map to the iris centre (0.5, 0.5)
    assert uvs[0] == pytest.approx((0.5, 0.5), abs=1e-6)
    assert uvs[6] == pytest.approx((0.5, 0.5), abs=1e-6)
    # up point maps above the centre
    assert uvs[4][1] > 0.7 and uvs[4][0] == pytest.approx(0.5, abs=1e-6)
    assert all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 for u, v in uvs)


def test_smooth_weights_softens_seams():
    """Hard weight boundaries (crotch/armpit) tear under retarget; smoothing
    must blend across the seam while keeping top-3 normalized weights."""
    mesh = me2_dae.Mesh(
        name="m", material="mtr",
        positions=[(0.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                   (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 4, uvs=[(0.0, 0.0)] * 4,
        triangles=[(0, 1, 2), (1, 3, 2)],
        weights=[[me2_dae.SkinBind("Hips", 1.0)],
                 [me2_dae.SkinBind("Hips", 1.0)],
                 [me2_dae.SkinBind("BoneA", 1.0)],
                 [me2_dae.SkinBind("BoneA", 1.0)]])
    smoothed = rig_target.smooth_weights(mesh.weights, mesh.positions,
                                         mesh.triangles, iters=2, alpha=0.5)
    assert mesh.weights[0][0].weight == pytest.approx(1.0)   # input untouched
    for binds in smoothed:
        assert len(binds) <= 3
        assert sum(b.weight for b in binds) == pytest.approx(1.0)
        assert all(b.weight > 0 for b in binds)
    # the seam edge (1,2) now carries both joints
    seam = {b.joint for b in smoothed[1]} | {b.joint for b in smoothed[2]}
    assert seam == {"Hips", "BoneA"}


def test_smooth_weights_glues_corner_split_twins():
    """Corner-split DAE meshes duplicate vertices per corner. Smoothing must
    not pull the twins apart (it shredded the retargeted body once already):
    coincident vertices receive identical smoothed weights."""
    # two triangles sharing the welded edge (1,2)-(2,1): 6 corners, twins at
    # (0,1,0) and (1,0,0)
    pos = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0),
           (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)]
    tris = [(0, 1, 2), (3, 4, 5)]
    w = [[me2_dae.SkinBind("Hips", 1.0)]] * 3 + \
        [[me2_dae.SkinBind("BoneA", 1.0)]] * 3
    smoothed = rig_target.smooth_weights(w, pos, tris, iters=2, alpha=0.5)
    for a, b in ((1, 3), (2, 4)):
        assert [(x.joint, round(x.weight, 9)) for x in smoothed[a]] == \
               [(x.joint, round(x.weight, 9)) for x in smoothed[b]]


def test_split_arm_verts(tiny_scene, monkeypatch):
    monkeypatch.setitem(rig_target.BONE_MAP, "BoneA", "BoneB")
    rig = _tmp_rig()
    rm = rig_target.rebind_mesh(tiny_scene.meshes[0], tiny_scene, rig)
    # force known dominant bones
    rm.weights = [[("Hips", 1.0)], [("LeftHand", 0.7), ("Hips", 0.3)], [("RightForeArm", 1.0)]]
    body, arms = rig_target.split_arm_verts(rm)
    assert body == {0}
    assert arms == {1, 2}


# ---------------------------------------------------------------- las_model
def _drawable():
    rig = _tmp_rig()
    atom = las_model.Atom(
        material="mtr_body1",
        positions=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        weights=[[("Hips", 1.0)], [("Hips", 0.5), ("BoneB", 0.5)], [("BoneB", 1.0)]],
        faces=[(0, 1, 2)],
    )
    return rig, las_model.Drawable("g_body", [atom])


def _read_back(data: bytes):
    import tempfile, os
    p = tempfile.mktemp(suffix=".model")
    Path(p).write_bytes(data)
    try:
        return dmodel.DieselModel(p)
    finally:
        os.unlink(p)


def test_model_roundtrip():
    rig, dr = _drawable()
    res = las_model.build_model(rig, [dr], extra_materials=("shadow_caster",))
    m = _read_back(res.data)
    assert not m.legacy
    ids = [s.id for s in m.sections]
    assert ids == list(range(1, len(ids) + 1))          # contiguous 1..N (audit)
    geo = next(s.obj for s in m.sections if s.tag == "geometry")
    topo = next(s.obj for s in m.sections if s.tag == "topology")
    assert geo.vert_count == 3
    assert len(topo.faces) == 1
    sb = next(s.obj for s in m.sections if s.tag == "skinbones")
    assert sb.count == 2                                # Hips + BoneB
    for mapping in sb.bone_mappings:
        assert list(mapping) == list(range(len(mapping)))  # 0..N-1 local indices
    # weights survive with indices inside the palette
    assert all(all(i < sb.count for i in j) for j in geo.joints)
    names = {s.obj.name_hash for s in m.sections if s.tag in ("model_data", "object3D")}
    assert dmodel.hash_str("g_body") in names
    assert dmodel.hash_str("Hips") in names
    assert dmodel.hash_str("c_block") in names


def test_model_large_topology_not_trimmed():
    """A05 regression: >65535 indices in one drawable must be authored intact."""
    rig = _tmp_rig()
    n = 23000  # 69000 indices
    positions = [(float(i % 100), float(i // 100), 0.0) for i in range(n)]
    faces = [(i, i + 1, i + 2) for i in range(n - 2)]
    atom = las_model.Atom(
        material="mtr_body1", positions=positions,
        normals=[(0.0, 0.0, 1.0)] * n, uvs=[(0.0, 0.0)] * n,
        weights=[[("Hips", 1.0)]] * n, faces=faces)
    res = las_model.build_model(rig, [las_model.Drawable("g_body", [atom])],
                                extra_materials=("shadow_caster",))
    m = _read_back(res.data)
    topo = next(s.obj for s in m.sections if s.tag == "topology")
    assert len(topo.faces) == len(faces)                 # nothing dropped


def test_model_rejects_too_many_vertices():
    rig = _tmp_rig()
    n = 65537
    atom = las_model.Atom(
        material="mtr_body1", positions=[(0.0, 0.0, 0.0)] * n,
        normals=[(0.0, 0.0, 1.0)] * n, uvs=[(0.0, 0.0)] * n,
        weights=[[("Hips", 1.0)]] * n, faces=[(0, 1, 2)])
    with pytest.raises(ValueError, match="vertices"):
        las_model.build_model(rig, [las_model.Drawable("g_body", [atom])])


def test_model_rejects_invalid_weight():
    rig = _tmp_rig()
    atom = las_model.Atom(
        material="mtr_body1", positions=[(0.0, 0.0, 0.0)] * 3,
        normals=[(0.0, 0.0, 1.0)] * 3, uvs=[(0.0, 0.0)] * 3,
        weights=[[("Hips", -1.0)], [("Hips", 1.0)], [("Hips", 1.0)]],
        faces=[(0, 1, 2)])
    with pytest.raises(ValueError, match="weight"):
        las_model.build_model(rig, [las_model.Drawable("g_body", [atom])])


# ---------------------------------------------------------------- dds A07
def test_pd2_normal_channels_repacks_layout():
    import numpy as np
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    arr[..., 0] = 40          # X
    arr[..., 1] = 200         # Y
    arr[..., 2] = 70          # Z (dropped)
    arr[..., 3] = 255
    out = dds.pd2_normal_channels(arr, invert_y=True)
    assert (out[..., 0] == 255).all()          # red unused -> white
    assert (out[..., 2] == 0).all()            # blue unused -> black
    assert (out[..., 3] == 40).all()           # X moved to alpha
    assert (out[..., 1] == 55).all()           # green Y inverted (255-200)
    out2 = dds.pd2_normal_channels(arr, invert_y=False)
    assert (out2[..., 1] == 200).all()


def test_dxt5_decodes_4color_when_c0_lt_c1():
    """Audit A07: DXT5 has separate alpha; c0 < c1 is not a transparent hole."""
    c0, c1 = 0x0000, 0xFFFF                      # c0 < c1 on purpose
    bits = 0                                     # all pixels index 0
    block = bytes([255, 255]) + b"\x00" * 6 + struct.pack("<HH", c0, c1) \
        + bits.to_bytes(4, "little")
    px = dds._decode_block(block)
    assert all(p[3] == 255 for p in px)          # alpha comes only from alpha block
    assert all(p[:3] == (0, 0, 0) for p in px)   # endpoint 0, not a black hole


def test_dxt5_roundtrip_and_validate():
    import numpy as np
    img = np.zeros((8, 8, 4), dtype=np.uint8)
    img[..., 0] = 200
    img[..., 3] = 255
    data = dds.pack_dds(dds.mip_payloads_from_image(img), 8)
    assert dds.validate_dxt5_texture(data) == []
    decoded = dds.decode_dxt5(data[dds.DDS_HEADER_SIZE:], 8, 8)
    assert abs(int(decoded[0, 0, 0]) - 200) <= 8


# ---------------------------------------------------------------- pack
@pytest.fixture(scope="module")
def built():
    if not SOURCE_ZIP.exists():
        pytest.skip("source zip not present")
    build = _load("build_las_pack_test", "build_las_pack.py")
    source = build.load_source(SOURCE_ZIP)
    scene = me2_dae.load_dae(source[build.DAE_NAME])
    rig = rig_target.load_target_rig(build.RIG_JSON)
    files = build.assemble(scene, rig, source, log=lambda *a: None)
    return build, scene, rig, files


class TestSourceIntegration:

    def test_all_weighted_joints_mapped(self, built):
        build, scene, rig, files = built
        for m in scene.meshes:
            for w in m.weights:
                for b in w:
                    rig_target.map_joint(b.joint)   # raises on unknown

    def test_pack_layout_matches_2b_contract(self, built):
        build, scene, rig, files = built
        names = set(files)
        for required in (
            f"{build.ROOT_DIR}/main.xml",
            f"{build.ROOT_DIR}/hooks/lawson.lua",
            f"{build.ROOT_DIR}/localization/english.txt",
            f"{build.ROOT_DIR}/{build.ASSET_DIR}/{build.UNIT_DIR}/lawson.model",
            f"{build.ROOT_DIR}/{build.ASSET_DIR}/{build.UNIT_DIR}/fps_lawson.model",
            f"{build.ROOT_DIR}/{build.ASSET_DIR}/{build.GUI_DIR}/lawson.texture",
            f"{build.ROOT_DIR}/CREDITS.txt",
        ):
            assert required in names, required
        assert not any(n.endswith(".cooked_physics") for n in names)

    def test_validation_passes(self, built):
        build, scene, rig, files = built
        build.validate(files, log=lambda *a: None)

    def test_fps_is_an_arm_cut(self, built):
        build, scene, rig, files = built
        tpp, fps = build.build_models(scene, rig, log=lambda *a: None)
        tpp_v = sum(d["verts"] for d in tpp.drawables.values())
        fps_v = sum(d["verts"] for d in fps.drawables.values())
        assert 0 < fps_v < tpp_v

    def test_models_deterministic(self, built):
        build, scene, rig, files = built
        a, _ = build.build_models(scene, rig, log=lambda *a: None)
        b, _ = build.build_models(scene, rig, log=lambda *a: None)
        assert a.data == b.data

    def test_hooks_register_las_entry(self, built):
        build, scene, rig, files = built
        hook = files[f"{build.ROOT_DIR}/hooks/lawson.lua"].decode()
        assert "la.lawson" in hook
        assert 'fps_unit' in hook
        assert "replace_all = true" in hook
        main = files[f"{build.ROOT_DIR}/main.xml"].decode()
        assert 'source_file="lib/tweak_data/armorskinstweakdata"' in main
        assert 'directory="hooks"' in main            # case-consistent (2B mix not copied)

    def test_materials_follow_moog_guide(self, built):
        """ModWorkshop LAS/MOOG guide: group + unique + CONTOUR variables on
        TPP materials, DEPTH_SCALING on FPS, no invented template combos."""
        build, scene, rig, files = built
        tpp = files[f"{build.ROOT_DIR}/{build.ASSET_DIR}/{build.UNIT_DIR}/lawson.material_config"].decode()
        fps = files[f"{build.ROOT_DIR}/{build.ASSET_DIR}/{build.UNIT_DIR}/fps_lawson.material_config"].decode()
        assert '<materials version="3" group="lawson">' in tpp
        assert '<materials version="3" group="fps_criminals_suit_lawson">' in fps
        assert tpp.count('unique="true"') == 7        # every non-masked material
        assert "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS" in tpp
        assert 'name="contour_color"' in tpp and 'name="contour_opacity"' in tpp
        # masked lashes keep the attested 2B combo; no CONTOUR invention
        assert "generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_1WEIGHT" in tpp
        assert "CONTOUR:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF" not in tpp
        # FPS: DEPTH_SCALING present, no contour
        assert "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS" in fps
        assert "CONTOUR" not in fps

    def test_normal_maps_use_pd2_layout(self, built):
        build, scene, rig, files = built
        nm = files[f"{build.ROOT_DIR}/{build.ASSET_DIR}/{build.UNIT_DIR}/face_nm.texture"]
        size, mips, view = dds.dds_mip0_slice(nm)
        arr = dds.decode_dxt5(bytes(view), size, size)
        # X lives in alpha, not red; red is constant white, blue constant black
        assert (arr[..., 0] == 255).all()
        assert (arr[..., 2] == 0).all()
        assert arr[..., 3].std() > 1                  # actual X data in alpha

    def test_rebind_geometry_gates(self, built):
        """The 'complete mess' regression: the retargeted meshes must keep
        their integrity (edge lengths preserved, no exploded vertices).
        Pre-fix measurements were 200-1100% edge distortion and 12-27 cm
        neighbour spikes; the segment-fit rebind with smoothed weights
        calibrates at p95 <= 50% and spikes <= 7 cm on this source."""
        build, scene, rig, files = built
        pc = _load("preview_check", "preview_check.py")
        rebound = [rig_target.rebind_mesh(m, scene, rig, smooth_iters=2)
                   for m in scene.meshes]
        for src, dst in zip(scene.meshes, rebound):
            rel = pc.edge_stats(src.positions, dst.positions, src.triangles)
            p95 = float(__import__("numpy").percentile(rel, 95))
            # torn-frame state measured p95 330-1117%; coherent ~170%
            assert p95 < 4.0, f"{src.name}: edge p95 {p95:.2f} (torn mesh)"
            _, spikes = pc.displacement_smoothness(
                src.positions, dst.positions, src.triangles)
            # torn-frame spikes were 27-28 cm; coherent <= 2.4 cm
            assert float(spikes.max()) < 25.0, f"{src.name}: exploded vertices"
            sep = pc.twin_separation(src.positions, dst.positions)
            assert sep < 2.0, f"{src.name}: twins separated by {sep:.2f} cm"


def test_built_pack_passes_the_guide_compliance_check():
    """The shipped pack must satisfy the ModWorkshop LAS/MOOG guide.

    `check_guide_compliance.py` re-reads the built zip and checks it against
    the guide's rules (skeleton, weights, materials, render templates, FPS
    unit, texture format, BeardLib packaging). A FAIL here is a guide
    violation in the pack, not a flake.
    """
    pack = ROOT / "dist" / "lawson_las.zip"
    if not pack.exists():
        pytest.skip("no built pack")
    checker = _load("check_guide_compliance", "check_guide_compliance.py")
    report = checker.audit(pack)
    fails = [c for c in report.checks if c["status"] == "FAIL"]
    assert not fails, "; ".join(f"{c['id']}: {c['detail']}" for c in fails)


def test_the_compliance_checker_actually_fails_on_broken_packs():
    """A checker that only ever passes proves nothing.

    The self-test mutates the built pack the way the guide forbids (invented
    render template, missing `unique="true"`, no DEPTH_SCALING, DXT1-style
    texture, an unregistered texture, a hook flag switched off, ...) and
    asserts that the matching check fails. It is the checker's own test.
    """
    pack = ROOT / "dist" / "lawson_las.zip"
    if not pack.exists():
        pytest.skip("no built pack")
    selftest = _load("check_guide_compliance_self_test",
                     "check_guide_compliance_self_test.py")
    missed = []
    base = selftest.read_pack()
    for mutate, expect, label in selftest.MUTATIONS:
        files = mutate(dict(base))
        ids = selftest.failed_ids(selftest.audit_pack(files))
        if expect not in ids:
            missed.append(f"{expect} ({label}) -> failed {sorted(ids) or 'nothing'}")
    assert not missed, "the checker did not catch: " + "; ".join(missed)


def test_repair_winding_reverses_only_the_folded_triangles():
    """A triangle that faces away from its own normals must be reversed.

    The bind-pose transfer rotates every bone piece independently, so bands
    of triangles fold back on themselves where the ME2 and the PD2 rigs
    disagree.  The vertex normals still describe the unfolded surface, so the
    winding is what has to be repaired -- and only where it disagrees.
    """
    # a flat, correctly wound triangle in the xy plane (normal +z)
    positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                 (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]
    normals = [(0.0, 0.0, 1.0)] * 6
    tris = [(0, 1, 2), (3, 4, 5)]
    fixed, flipped = rig_target.repair_winding(positions, normals, tris)
    assert flipped == 1, "only the backwards triangle may be reversed"
    assert fixed[0] == (0, 1, 2), "the correct triangle must be left alone"
    assert fixed[1] == (3, 5, 4), "the folded triangle must be reversed"
    # a second pass finds nothing left to do
    _again, flipped2 = rig_target.repair_winding(positions, normals, fixed)
    assert flipped2 == 0


def test_the_built_pack_has_no_inverted_faces():
    """Every triangle of the shipped pack must face the same way as its normals.

    An inverted triangle is culled by the game: it leaves a hole in the skin
    and the shading around it is wrong.  The quadruple check found 946 of
    them in pack 0.1.1; the builder now repairs the winding.
    """
    pack = ROOT / "dist" / "lawson_las.zip"
    if not pack.exists():
        pytest.skip("no built pack")
    with zipfile.ZipFile(pack) as z:
        for name in ("Lawson_LAS/assets/units/lawson/skins/lawson/lawson.model",
                     "Lawson_LAS/assets/units/lawson/skins/lawson/fps_lawson.model"):
            raw = z.read(name)
            model = dmodel.DieselModel.from_bytes(raw)
            inverted = total = 0
            for s in model.sections:
                if s.tag != "model_data" or s.obj is None:
                    continue
                pas = model.by_id.get(s.obj.passthrough_id)
                if pas is None or pas.obj is None:
                    continue
                geo = model.by_id.get(pas.obj.geometry_id)
                top = model.by_id.get(pas.obj.topology_id)
                if geo is None or top is None or geo.obj is None or top.obj is None:
                    continue
                pos, nrm = geo.obj.positions, geo.obj.normals
                for a, b, c in top.obj.faces:
                    if max(a, b, c) >= len(pos):
                        continue
                    e1 = [pos[b][i] - pos[a][i] for i in range(3)]
                    e2 = [pos[c][i] - pos[a][i] for i in range(3)]
                    gn = [e1[1] * e2[2] - e1[2] * e2[1],
                          e1[2] * e2[0] - e1[0] * e2[2],
                          e1[0] * e2[1] - e1[1] * e2[0]]
                    ln = sum(x * x for x in gn) ** 0.5
                    if ln < 1e-9:
                        continue
                    total += 1
                    if sum(gn[i] * (nrm[a][i] + nrm[b][i] + nrm[c][i])
                           for i in range(3)) < 0:
                        inverted += 1
            assert total, f"{name}: no triangles found"
            assert inverted == 0, f"{name}: {inverted} of {total} triangles are inverted"


def test_the_status_page_matches_the_shipped_pack():
    """`tools/pd2-port/STATUS.md` is the handoff page - it must not drift.

    A status page that quotes a stale size, checksum or audit result is
    worse than none: the next agent trusts it.
    """
    import hashlib
    import re

    status = (PD2 / "STATUS.md").read_text()
    pack = ROOT / "dist" / "lawson_las.zip"
    if not pack.exists():
        pytest.skip("no built pack")
    raw = pack.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest in status, "STATUS.md does not quote the pack's sha256"
    assert f"{len(raw):,}" in status, "STATUS.md does not quote the pack's size"

    checker = _load("check_guide_compliance", "check_guide_compliance.py")
    counts = checker.audit(pack).counts()
    assert f"**{counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail**" in status, (
        "STATUS.md does not quote the audit's result")


def test_the_builder_version_matches_the_latest_release_notes():
    """Two sources of truth for the pack version - they must agree.

    The release workflow stamps the version from the release notes of the
    tag; a push without notes falls back to the builder's own VERSION. If
    the two drift, the workflow builds a pack with a different version in
    its manifest and the byte check fails (which is how it was found).
    """
    import re

    builder = (PD2 / "build_las_pack.py").read_text()
    version = re.search(r'^VERSION\s*=\s*"([^"]+)"', builder, re.M).group(1)

    notes = sorted(
        PD2.glob("releases/lawson-las-v*.md"),
        key=lambda p: int(re.search(r"v(\d+)\.md$", p.name).group(1)),
    )
    assert notes, "no release notes found"
    latest = notes[-1]
    stamped = re.search(r"<!--\s*pack_version:\s*([^>]+?)\s*-->", latest.read_text()).group(1)
    assert version == stamped, (
        f"the builder stamps {version} but {latest.name} says {stamped}")


def test_the_tracked_pack_carries_the_builder_version():
    """The shipped pack's manifest must carry the current version."""
    import json
    import re
    import zipfile

    pack = ROOT / "dist" / "lawson_las.zip"
    if not pack.exists():
        pytest.skip("no built pack")
    with zipfile.ZipFile(pack) as z:
        manifest = json.loads(z.read("Lawson_LAS/build_manifest.json"))
    builder = (PD2 / "build_las_pack.py").read_text()
    version = re.search(r'^VERSION\s*=\s*"([^"]+)"', builder, re.M).group(1)
    assert manifest["version"] == version
