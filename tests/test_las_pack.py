"""Tests for the LAS restart pipeline: ME2 COLLADA import, PD2 rig retarget,
DODB model authoring and the 2B-contract pack assembly.

Synthetic fixtures only, except the integration test which uses the tracked
source zip (skipped when absent).
"""
import importlib.util
import io
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
    # ME2 Left* is world +X = PD2 Right*
    assert rig_target.map_joint("LeftWrist") == "RightHand"
    assert rig_target.map_joint("RightWrist") == "LeftHand"
    assert rig_target.map_joint("LeftHip") == "RightUpLeg"
    assert rig_target.map_joint("RightToe") == "LeftToeBase"
    assert rig_target.map_joint("root") == "Hips"
    assert rig_target.map_joint("LowerBack") == "Spine"
    assert rig_target.map_joint("Neck1") == "Neck"


def test_map_joint_folds_fingers_and_face():
    assert rig_target.map_joint("LeftIndexFinger2") == "RightHand"
    assert rig_target.map_joint("RightRingFinger1") == "LeftHand"
    assert rig_target.map_joint("brow_Left") == "Head"
    assert rig_target.map_joint("innerUpperLip_right") == "Head"
    assert rig_target.map_joint("eyeLookBackAt") == "Head"


def test_map_joint_unknown_raises():
    with pytest.raises(KeyError):
        rig_target.map_joint("NotABone")


def test_bone_map_targets_exist_in_donor_rig():
    rig = rig_target.load_target_rig(PD2 / "reference" / "las_rig.json")
    missing = {t for t in rig_target.BONE_MAP.values() if t not in rig.by_name}
    assert not missing, f"BONE_MAP targets missing from las_rig.json: {missing}"


# ---------------------------------------------------------------- retarget
def test_rebind_maps_by_target_bones(tiny_scene, monkeypatch):
    monkeypatch.setitem(rig_target.BONE_MAP, "BoneA", "BoneB")
    rig = _tmp_rig()
    rm = rig_target.rebind_mesh(tiny_scene.meshes[0], tiny_scene, rig)
    # vertex 2 weighted 50/50 root->Hips and BoneA->BoneB:
    # root: identity -> Hips = +100 z; BoneA world (10,20,30) -> BoneB (30,0,100)
    # expected = 0.5*(p + (0,0,100)) + 0.5*(p + (20,-20,70))
    p = tiny_scene.meshes[0].positions[2]  # (0, 1, 0)
    exp = (0.5 * (p[0] + 0) + 0.5 * (p[0] + 20),
           0.5 * (p[1] + 0) + 0.5 * (p[1] - 20),
           0.5 * (p[2] + 100) + 0.5 * (p[2] + 70))
    assert rm.positions[2] == pytest.approx(exp, abs=1e-4)
    assert sum(w for _, w in rm.weights[2]) == pytest.approx(1.0)


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
            f"{build.ROOT_DIR}/{build.UNIT_DIR}/lawson.model",
            f"{build.ROOT_DIR}/{build.UNIT_DIR}/fps_lawson.model",
            f"{build.ROOT_DIR}/{build.GUI_DIR}/lawson.texture",
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
        tpp = files[f"{build.ROOT_DIR}/{build.UNIT_DIR}/lawson.material_config"].decode()
        fps = files[f"{build.ROOT_DIR}/{build.UNIT_DIR}/fps_lawson.material_config"].decode()
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
        nm = files[f"{build.ROOT_DIR}/{build.UNIT_DIR}/face_nm.texture"]
        size, mips, view = dds.dds_mip0_slice(nm)
        arr = dds.decode_dxt5(bytes(view), size, size)
        # X lives in alpha, not red; red is constant white, blue constant black
        assert (arr[..., 0] == 255).all()
        assert (arr[..., 2] == 0).all()
        assert arr[..., 3].std() > 1                  # actual X data in alpha
