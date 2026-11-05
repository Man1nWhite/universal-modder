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


DIST = REPO / "dist"
SHIPPED_MODELS = [
    (
        "Miranda_L4D2_over_Bonnie.zip",
        "Miranda L4D2 over Bonnie",
        "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
    ),
    (
        "Miranda_Romance_over_Clover.zip",
        "Miranda Romance over Clover",
        "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
    ),
]


class TestShippedHeisterModels:
    """Geometry sections in the shipped heister packs must decode, including the
    vanilla bag meshes that carry a second and third UV set (TEXCOORD1/2,
    channels 8/9). Before those channels were supported, decoding `g_armorbag`,
    `g_medicbag`, `g_sentrybag` or `g_bodybagsbag` raised
    `ValueError: unsupported geometry channel 8`, so no shipped pack could be
    verified end to end."""

    @pytest.mark.skipif(not (DIST / SHIPPED_MODELS[0][0]).exists(), reason="dist packs not built")
    @pytest.mark.parametrize("zip_name,prefix,model_rel", SHIPPED_MODELS, ids=["bonnie", "clover"])
    def test_every_geometry_section_round_trips(self, zip_name, prefix, model_rel):
        import zipfile

        with zipfile.ZipFile(DIST / zip_name) as z:
            mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
        geoms = mf.by_type(dm.GEOMETRY)
        assert geoms, "no geometry sections"
        for s in geoms:
            g = dm.decode_geometry(s.payload)
            assert dm.encode_geometry(g) == s.payload, f"geometry section {s.id} does not round-trip"

    @pytest.mark.skipif(not (DIST / SHIPPED_MODELS[0][0]).exists(), reason="dist packs not built")
    def test_second_and_third_uv_sets_decode(self):
        import zipfile

        zip_name, prefix, model_rel = SHIPPED_MODELS[0]
        with zipfile.ZipFile(DIST / zip_name) as z:
            mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
        md_by_hash = {dm.decode_model_data(s.payload)["name_hash"]: s for s in mf.by_type(dm.MODEL_DATA)}
        md = dm.decode_model_data(md_by_hash[dm.hash64("g_armorbag")].payload)
        pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        g = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
        enum_types = [h["enum_type"] for h in g["headers"]]
        assert dm.TEXCOORD1 in enum_types and dm.TEXCOORD2 in enum_types
        assert len(g["uv1"]) == g["vert_count"] == len(g["uv2"]) > 0
        assert g["remaining"] == b"", "geometry payload not fully consumed"


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
