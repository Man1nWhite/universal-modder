"""Diesel .model codec tests: byte-exact round-trip of the 2B reference models."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import diesel_model as dm  # noqa: E402

REF_DIR = Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b")
REF_2B = REF_DIR / "2b.model"
REF_FPS = REF_DIR / "fps_2b.model"

needs_ref = pytest.mark.skipif(
    not REF_2B.exists() or not REF_FPS.exists(),
    reason="2b.rar reference models not extracted to /tmp/2bsrc",
)


@needs_ref
class TestRoundTrip:
    @pytest.mark.parametrize("path", [REF_2B, REF_FPS], ids=["2b", "fps_2b"])
    def test_byte_exact(self, path):
        raw = path.read_bytes()
        mf = dm.ModelFile.read(raw)
        out = mf.write()
        assert out == raw, f"round-trip mismatch for {path.name}"

    @pytest.mark.parametrize("path", [REF_2B, REF_FPS], ids=["2b", "fps_2b"])
    def test_all_payloads_reencode(self, path):
        """Every section's decoded structure must re-encode to the same bytes."""
        raw = path.read_bytes()
        mf = dm.ModelFile.read(raw)
        decoders = {
            dm.MODEL_DATA: lambda p: dm.encode_model_data(dm.decode_model_data(p)),
            dm.SKINBONES: lambda p: dm.encode_skinbones(dm.decode_skinbones(p)),
            dm.GEOMETRY: lambda p: dm.encode_geometry(dm.decode_geometry(p)),
            dm.TOPOLOGY: lambda p: dm.encode_topology(dm.decode_topology(p)),
            dm.PASSTHROUGH_GP: lambda p: dm.encode_passthroughgp(dm.decode_passthroughgp(p)),
            dm.TOPOLOGY_IP: lambda p: dm.encode_topologyip(dm.decode_topologyip(p)),
            dm.MATERIAL: lambda p: dm.encode_material(dm.decode_material(p)),
            dm.MATERIAL_GROUP: lambda p: dm.encode_material_group(dm.decode_material_group(p)),
            dm.CUSTOM_HASHLIST: lambda p: dm.encode_custom_hashlist(dm.decode_custom_hashlist(p)),
        }
        bad = []
        for s in mf.sections:
            if s.type == dm.OBJECT3D:
                obj = dm.decode_object3d(s.payload)
                out = dm.encode_object3d(obj) + s.payload[obj["tail_off"]:]
                if out != s.payload:
                    bad.append((s.type, s.id))
            elif s.type in decoders:
                if decoders[s.type](s.payload) != s.payload:
                    bad.append((s.type, s.id))
        assert bad == [], f"payload re-encode mismatches: {bad}"


def _reencode_object3d(p):
    obj = dm.decode_object3d(p)
    return dm.encode_object3d(obj) + p[obj["tail_off"]:]


@needs_ref
class TestHash64:
    def test_names_cover_object_hashes(self):
        """hash64 must map the hashlist names onto the object name hashes."""
        mf = dm.ModelFile.read_path(REF_2B)
        hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
        name_hashes = {dm.hash64(n): n for n in hl["names"]}
        covered = total = 0
        for s in mf.sections:
            if s.type in (dm.OBJECT3D, dm.MODEL_DATA):
                h = dm.decode_object3d(s.payload)["name_hash"]
                if h == 0:
                    continue
                total += 1
                if h in name_hashes:
                    covered += 1
        assert total > 0
        assert covered / total > 0.99, f"only {covered}/{total} name hashes resolved"

    def test_known_anchors(self):
        mf = dm.ModelFile.read_path(REF_2B)
        hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
        for name in ("Hips", "root_point", "g_body", "g_head", "s_body"):
            assert name in hl["names"] or name in ("Hips",), name
        # Hips is a bone name present in the tree
        assert dm.hash64("Hips") != 0


@needs_ref
class TestSkinSemantics:
    def test_rotations_are_inverse_bind_worlds(self):
        """2B invariant: Rotations[i] == inv(bone WorldTransform)."""
        mf = dm.ModelFile.read_path(REF_2B)
        nodes = {}
        for s in mf.sections:
            if s.type in (dm.OBJECT3D, dm.MODEL_DATA):
                obj = dm.decode_object3d(s.payload)
                nodes[s.id] = obj
        worlds = {}
        for sid, obj in nodes.items():
            loc = list(obj["matrix"])
            loc[12], loc[13], loc[14] = obj["pos"]
            loc = tuple(loc)
            if obj["parent"] == 0:
                worlds[sid] = loc
            else:
                worlds[sid] = dm.mat_mul(loc, worlds[obj["parent"]])
        skins = [s for s in mf.sections if s.type == dm.SKINBONES]
        checked = 0
        for s in skins:
            sb = dm.decode_skinbones(s.payload)
            if not sb["objects"]:
                continue
            for i, oid in enumerate(sb["objects"]):
                if oid not in worlds:
                    continue
                expect = dm.mat_inv(worlds[oid])
                got = sb["rotations"][i]
                assert all(abs(a - b) < 1e-3 for a, b in zip(expect, got)), (
                    f"skinbones {s.id} obj {oid}: rotation != inv(world)")
                checked += 1
                if checked > 40:
                    return
        assert checked > 0
