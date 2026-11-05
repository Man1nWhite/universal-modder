"""SMD read/write: the Blender hand-off, and the rig it must not lose.

The reason this file exists is a gap: the repo reads MDL/VVD/VTX/VTF/VPK/GMA but
wrote none of them, and Blender (Crowbar, Blender Source Tools, SourceIO) reads
**SMD**. A wrong SMD is worse than no SMD — Blender will happily import a rig with
zeroed bind-pose rotations and it will look almost right — so the tests are
weighted towards the two things that silently destroy a skeleton:

* bind-pose rotation (a ValveBiped pelvis is a 90° turn about X, not identity),
* weight links (SMD allows any number, `SkinVertex` carries three).

Plus the format's sharp edges: it has no index buffer (consecutive triples *are*
triangles, so vertices must be de-indexed on write) and no way to express "this is
an animation" other than a second `time` block, which a reference-mesh reader must
refuse rather than bake as a bind pose.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))

import smd  # noqa: E402
from source_model import Bone, ModelData, SkinVertex, SubMesh  # noqa: E402
from vpk import VpkArchive  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "models" / "l4d2_miranda_lawson_1.zip"
TPP = (
    "models/survivors/survivor_producer.mdl",
    "models/survivors/survivor_producer.vvd",
    "models/survivors/survivor_producer.dx90.vtx",
)


# ------------------------------------------------------------------- parsing

HAND_WRITTEN = """\
version 1
nodes
0 "root" -1
1 "child" 0
end
skeleton
time 0
0 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000
1 1.000000 2.000000 3.000000 1.570796 0.000000 0.000000
end
triangles
mymat
0 0.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 1 0 1.0
0 1.0 0.0 0.0 0.0 0.0 1.0 1.0 0.0 2 0 0.25 1 0.75
0 0.0 1.0 0.0 0.0 0.0 1.0 0.0 1.0 1 0 1.0
end
"""


def test_parses_nodes_skeleton_and_weights():
    model = smd.parse_smd(HAND_WRITTEN)
    assert model.nodes == [("root", -1), ("child", 0)]
    assert model.skeleton[1][0] == 1
    assert model.skeleton[1][1] == (1.0, 2.0, 3.0)
    assert model.skeleton[1][2][0] == pytest.approx(math.pi / 2)
    (mesh,) = model.meshes
    assert mesh.material == "mymat"
    assert mesh.triangles == [(0, 1, 2)]
    assert mesh.vertices[1].links == ((0, 0.25), (1, 0.75))


def test_comments_and_crlf_are_tolerated():
    text = HAND_WRITTEN.replace("\n", "\r\n").replace("mymat", "mymat // body")
    (mesh,) = smd.parse_smd(text).meshes
    assert mesh.material == "mymat"


def test_an_animation_is_refused_not_baked():
    """Two `time` blocks is an animation; frame 0 is not a bind pose."""
    text = HAND_WRITTEN.replace("time 0\n", "time 0\n").replace(
        "end\ntriangles", "time 1\n0 0 0 0 0 0 0\nend\ntriangles"
    )
    with pytest.raises(smd.SmdError, match="animation"):
        smd.parse_smd(text)


def test_a_vertex_count_that_is_not_a_triangle_triple_is_refused():
    text = HAND_WRITTEN.replace(
        "0 0.0 1.0 0.0 0.0 0.0 1.0 0.0 1.0 1 0 1.0\n", ""
    )
    with pytest.raises(smd.SmdError, match="not a multiple of 3"):
        smd.parse_smd(text)


def test_the_optional_link_count_field_is_skipped():
    """Source writes `<links> id w …`; a naive reader shifts every later field."""
    text = HAND_WRITTEN.replace("2 0 0.25 1 0.75", "2 0 0.250000 1 0.750000")
    (mesh,) = smd.parse_smd(text).meshes
    assert mesh.vertices[1].links == ((0, 0.25), (1, 0.75))
    assert mesh.vertices[1].uv == (1.0, 0.0)


def test_single_vertex_triangle_line_is_an_error():
    text = HAND_WRITTEN.replace("0 0.0 0.0 0.0 0.0 0.0 1.0 0.0 0.0 1 0 1.0",
                                "0 0.0 0.0 0.0")
    with pytest.raises(smd.SmdError):
        smd.parse_smd(text)


# ------------------------------------------------------------------- writing

def test_written_smd_parses_back_identically():
    model = smd.parse_smd(HAND_WRITTEN)
    again = smd.parse_smd(smd.write_smd(model))
    assert again.nodes == model.nodes
    assert again.skeleton == model.skeleton
    assert again.meshes[0].vertices[1].links == model.meshes[0].vertices[1].links


# ------------------------------------------------------- skeleton round-trip

def test_identity_quaternion_is_zero_angles():
    assert smd.quat_to_euler((0.0, 0.0, 0.0, 1.0)) == (0.0, 0.0, 0.0)
    assert smd._euler_to_quat((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0, 1.0)


def test_a_quarter_turn_about_x_is_pitch_not_yaw():
    q = (math.sin(math.pi / 4), 0.0, 0.0, math.cos(math.pi / 4))
    pitch, yaw, roll = smd.quat_to_euler(q)
    assert pitch == pytest.approx(math.pi / 2)
    assert yaw == pytest.approx(0.0) and roll == pytest.approx(0.0)


def test_yaw_and_roll_land_in_the_right_fields():
    for axis, index in ((1, 1), (2, 2)):  # Y -> yaw, Z -> roll
        q = [0.0, 0.0, 0.0, 1.0]
        q[axis] = math.sin(0.3 / 2)
        q[3] = math.cos(0.3 / 2)
        angles = smd.quat_to_euler(tuple(q))
        assert angles[index] == pytest.approx(0.3)
        assert [a for i, a in enumerate(angles) if i != index] == pytest.approx([0.0, 0.0])


@pytest.mark.skipif(not PACK.exists(), reason="tracked L4D2 pack is absent")
def test_every_real_bone_rotation_survives_the_text_round_trip():
    """Angles → quaternion → angles on the 104 ValveBiped bones of the real pack."""
    from source_model import load_model

    arc = VpkArchive.from_zip(str(PACK), "miranda_rochelle.vpk")
    model = load_model(*(arc.read(path) for path in TPP))
    for bone in model.bones:
        angles = smd.quat_to_euler(bone.quat)
        back = smd._euler_to_quat(angles)
        # q and -q are the same rotation; the extraction may pick either sign.
        same = max(abs(g - w) for g, w in zip(back, bone.quat))
        flipped = max(abs(g + w) for g, w in zip(back, bone.quat))
        assert min(same, flipped) < 1e-6, bone.name


# ------------------------------------------------------- ModelData <-> SMD

def _tiny_model() -> ModelData:
    bones = [
        Bone("root", -1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        Bone("spine", 0, (0.0, 0.0, 10.0), (math.sin(0.2), 0.0, 0.0, math.cos(0.2))),
    ]
    verts = [
        SkinVertex((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0), ((0, 1.0),)),
        SkinVertex((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0), ((0, 0.5), (1, 0.5))),
        SkinVertex((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0), ((1, 1.0),)),
    ]
    return ModelData(
        name="tiny",
        bones=bones,
        materials=["body"],
        vertices=verts,
        meshes=[SubMesh(material="body", triangle_indices=(0, 1, 2))],
    )


def test_model_to_smd_deindexes_and_keeps_the_triangle():
    """SMD has no index buffer, so a shared vertex is repeated per corner."""
    model = _tiny_model()
    smd_model, warnings = smd.model_to_smd(model)
    assert warnings == []
    (mesh,) = smd_model.meshes
    assert len(mesh.vertices) == 3 == len(mesh.triangles) * 3
    assert mesh.triangles == [(0, 1, 2)]
    assert [v.parent for v in mesh.vertices] == [0, 0, 1]


def test_more_than_three_links_are_clamped_and_counted():
    verts = [
        SkinVertex((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0),
                   ((0, 0.4), (1, 0.3), (2, 0.2), (3, 0.1))),
        SkinVertex((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0), ((0, 1.0),)),
        SkinVertex((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0), ((0, 1.0),)),
    ]
    model = ModelData(
        name="clamp",
        bones=[Bone(f"b{i}", -1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)) for i in range(4)],
        materials=["m"],
        vertices=verts,
        meshes=[SubMesh(material="m", triangle_indices=(0, 1, 2))],
    )
    smd_model, _ = smd.model_to_smd(model)
    (mesh,) = smd_model.meshes
    first = mesh.vertices[0]
    assert mesh.clamped_links == 1
    assert len(first.links) == 3
    assert sum(w for _, w in first.links) == pytest.approx(1.0)
    assert 3 not in [bone for bone, _ in first.links]  # weakest link dropped


def test_smd_to_model_rebuilds_bones_and_weights():
    back = smd.smd_to_model(smd.parse_smd(HAND_WRITTEN))
    assert [b.name for b in back.bones] == ["root", "child"]
    assert back.bones[1].parent == 0
    assert back.bones[1].quat[0] == pytest.approx(math.sin(math.pi / 4), abs=1e-6)
    (sub,) = back.meshes
    assert sub.material == "mymat"
    assert back.vertices[1].weights == ((0, 0.25), (1, 0.75))


# ------------------------------------------------------------------- QC stub

def test_qc_stub_dedupes_material_folders():
    model = _tiny_model()
    model.materials = ["a/one", "a/two", "a/three"]
    qc = smd.qc_stub(model, "tiny.smd")
    assert 'a/model.mdl' not in qc
    assert qc.count("$cdmaterials") == 1  # all three share the folder "a"
    assert '$cdmaterials "a"' in qc
    assert '$body "tiny.smd"' in qc


# ---------------------------------------------------------------------- CLI

@pytest.mark.skipif(not PACK.exists(), reason="tracked L4D2 pack is absent")
def test_cli_writes_smd_and_qc_for_the_tracked_pack(tmp_path):
    out = tmp_path / "smd"
    assert smd.main([str(PACK), "--out", str(out), "--qc"]) == 0
    written = sorted(p.name for p in out.iterdir())
    assert written == [
        "survivor_producer.qc", "survivor_producer.smd",
        "v_arms_producer_new.qc", "v_arms_producer_new.smd",
    ]
    parsed = smd.read_smd(out / "survivor_producer.smd")
    assert len(parsed.nodes) == 104
    assert parsed.triangle_count == 16433
    assert [m.material for m in parsed.meshes] == [
        "miranda_hair", "eyeball_r", "eyeball_l",
        "miranda_face", "miranda_head", "miranda_body",
    ]


@pytest.mark.skipif(not PACK.exists(), reason="tracked L4D2 pack is absent")
def test_the_exported_mesh_is_geometrically_the_source_mesh(tmp_path):
    """Triangle count, materials and per-triangle centroids survive the export."""
    import numpy as np

    from source_model import load_model

    out = tmp_path / "smd"
    smd.main([str(PACK), "--out", str(out)])
    arc = VpkArchive.from_zip(str(PACK), "miranda_rochelle.vpk")
    original = load_model(*(arc.read(path) for path in TPP))
    exported = smd.smd_to_model(smd.read_smd(out / "survivor_producer.smd"))
    assert exported.triangle_count == original.triangle_count
    # `phy` is in `ModelData.materials` but has no triangles, so no SMD material
    # block is written for it — the mesh materials must match exactly.
    assert [m.material for m in exported.meshes] == [
        m.material for m in original.meshes
    ]

    def centroids(model):
        rows = []
        for sub in model.meshes:
            flat = sub.triangle_indices
            for i in range(0, len(flat), 3):
                pts = np.array([model.vertices[g].pos for g in flat[i : i + 3]])
                rows.append((sub.material, tuple(np.round(pts.mean(axis=0), 3).tolist())))
        return sorted(rows)

    left, right = centroids(original), centroids(exported)
    assert len(left) == len(right)
    disagreements = [(a, b) for a, b in zip(left, right) if a != b]
    # 6-decimal text output, so a handful of centroids can round differently by 1mm
    assert len(disagreements) <= 20, disagreements[:3]
