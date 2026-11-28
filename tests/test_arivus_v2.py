"""`Arivus_over_Hoxton_v2.zip`: the owner's Blender scene as a head pack over Old Hoxton.

The pack is v1's builder with the head and hair taken from the owner's scene instead of
the Random4 `.dff`, so these tests are in three groups:

* **the source** — the tracked digest is the scene it says it is, and the builder reads
  nothing else;
* **what must not move** — every file that is not one of the three models is v1's, byte
  for byte, and the geometry keeps v1's topology, uv0, weights and palette;
* **what did move** — the crown and the back of the skull, by a measured, small amount,
  and nowhere else.

Everything is measured on the two shipped zips, not on a render: a bind-pose render
cannot see skinning, which is how the D72 neck regression got past the sheets.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import arivus_v2_from_blend as arivus  # noqa: E402
import diesel_model as dm  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from pack_checksum import verify_checksum  # noqa: E402
from status import target as make_target  # noqa: E402

PACK = dist_path(ROOT, "Arivus_over_Hoxton_v2.zip")
V1 = dist_path(ROOT, "Arivus_over_Hoxton.zip")
MESH = ROOT / "references/arivus_v2/head_v2.json"
SCENE = ROOT / "references/templates/Arivus Head BLEND.7z"
PREFIX = "Arivus over Hoxton v2"
PREFIX_V1 = "Arivus over Hoxton"
HEAD = "g_head_old_hoxton"
SUIT_MODELS = (
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_1.model",
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_menu_1.model",
    "units/pd2_dlc_chill/characters/shared_character/npc_criminals_suit_chill.model",
)
#: the four textures and the icon are v1's own encode of the same atlas
SAME_AS_V1 = (
    "units/payday2/characters/shared_textures/old_hoxton_head_df.texture",
    "units/payday2/characters/shared_textures/old_hoxton_head_nm.texture",
    "units/payday2/characters/shared_textures/old_hoxton_head_p_df.texture",
    "units/payday2/characters/shared_textures/old_hoxton_head_p_nm.texture",
    "units/payday2/characters/npc_criminals_suit_1/mtr_old_hoxton.material_config",
    "units/payday2/characters/npc_criminals_suit_1/mtr_old_hoxton_cc.material_config",
    "units/pd2_dlc_chill/characters/shared_character/mtr_old_hoxton.material_config",
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_1.object",
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_menu_1.object",
)


def _nearest(points: np.ndarray, queries: np.ndarray, chunk: int = 512) -> np.ndarray:
    """Distance from each query to the nearest point, in chunks to bound the pairwise array.

    A plain NumPy brute force: scipy is not a dependency of this repository (`pins.txt`),
    and 4,600 by 4,600 is 170 MB per axis as one float64 block, which is why it is chunked.
    """
    out = np.empty(len(queries))
    for start in range(0, len(queries), chunk):
        block = queries[start:start + chunk]
        diff = block[:, None, :] - points[None, :, :]
        out[start:start + chunk] = np.sqrt((diff * diff).sum(axis=2)).min(axis=1)
    return out


def _radii(points: np.ndarray, queries: np.ndarray, radius: float, chunk: int = 512) -> list[np.ndarray]:
    """Index of every point within `radius` of each query, as a list of arrays."""
    out: list[np.ndarray] = []
    for start in range(0, len(queries), chunk):
        block = queries[start:start + chunk]
        diff = block[:, None, :] - points[None, :, :]
        inside = (diff * diff).sum(axis=2) <= radius * radius
        out.extend(np.nonzero(row)[0] for row in inside)
    return out


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as zf:
        return {name.split("/", 1)[1]: zf.read(name) for name in zf.namelist()}


def _drawable(model_bytes: bytes, name: str = HEAD) -> dict:
    """One drawable of a packed `.model`: its geometry, topology and both palettes."""
    mf = dm.ModelFile.read(model_bytes)
    want = dm.hash64(name)
    for shape in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(shape.payload)
        if md.get("version") != 3 or not md.get("atoms") or md.get("name_hash") != want:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        indices = np.asarray(topo["indices"], np.int64)
        atom = md["atoms"][0]
        tris = indices[atom["base_index"]:atom["base_index"] + atom["tri_count"] * 3].reshape(-1, 3)
        skinbones = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
        return {
            "model_data": md,
            "verts": np.asarray(geo["verts"], np.float64),
            "normals": np.asarray(geo["normals"], np.float64),
            "uv0": np.asarray(geo["uv0"], np.float64),
            "blendindices": np.asarray(geo["blendindices"], np.int64),
            "blendweights": np.asarray(geo["blendweights"], np.float64),
            "tris": tris,
            "palette": skinbones["objects"],
        }
    raise AssertionError(f"{name} is not in the model")


# ------------------------------------------------------------------ the source

def test_the_pack_is_tracked_and_has_a_builder():
    assert PACK.is_file(), f"{PACK.relative_to(ROOT)} is missing"
    verify_checksum(PACK, ROOT)
    assert make_target(PACK.stem) == "heads_v2"


def test_the_digest_is_the_tracked_scene():
    """The builder reads this file, so the file must be the archive it names."""
    document = json.loads(MESH.read_text())
    assert document["source"]["archive"] == "references/templates/Arivus Head BLEND.7z"
    assert document["source"]["archive_sha256"] == hashlib.sha256(SCENE.read_bytes()).hexdigest()
    assert document["counts"] == {"vertices": len(document["positions"]),
                                  "triangles": len(document["triangles"])}
    assert np.asarray(document["uv"]).shape == (document["counts"]["triangles"], 3, 2)
    assert np.asarray(document["corner_normals"]).shape == (document["counts"]["triangles"], 3, 3)


def test_the_scene_opens_in_the_pinned_blender():
    """The tracked `.blend` is saved by 4.2, the Blender this repository pins.

    It shipped saved by 5.1 (501), which 4.2 refuses outright; `resave_arivus_blend.py`
    rewrote it with 4.2.23 from a data dump of the original. The stamp is in the file's
    own header, behind Blender's zstd frame.
    """
    import tempfile

    py7zr = pytest.importorskip("py7zr", reason="the scene is inside a .7z")

    with tempfile.TemporaryDirectory() as scratch:
        with py7zr.SevenZipFile(SCENE, mode="r") as archive:
            name = next(n for n in archive.getnames() if n.endswith(".blend"))
            archive.extract(path=scratch, targets=[name])
        blend = Path(scratch) / name
        header = arivus.blend_header(blend)
    assert header[:7] == b"BLENDER", header[:12]
    stamp = header[9:12].decode("ascii", "replace")
    major, minor = int(stamp[0]), int(stamp[1:])
    assert (major, minor) <= (4, 2), (
        f"the tracked scene is saved by {major}.{minor}: Blender 4.2 refuses it "
        f"(run tools/pd2-las/resave_arivus_blend.py)")
    assert json.loads(MESH.read_text())["source"]["blender_that_wrote_it"] == f"{major}.{minor}"


def test_the_archive_kept_everything_but_the_blend():
    """The re-save replaced the `.blend` and left the v1 export folder beside it alone."""
    import py7zr

    with py7zr.SevenZipFile(SCENE, mode="r") as archive:
        names = set(archive.getnames())
    assert "Arivus Head GLB/Untitled.blend" in names
    # the v1 GLB/DDS export the owner shipped in the same archive
    for name in ("Arivus Head GLB/arivus_head_over_old_hoxton.glb",
                 "Arivus Head GLB/manifest.json",
                 "Arivus Head GLB/old_hoxton_head_df.dds"):
        assert name in names, name
    # and the digest still names the member it was read from
    assert json.loads(MESH.read_text())["source"]["member"] == "Untitled.blend"


def test_the_digest_is_in_diesel_centimetres():
    """Metres x100, z up: the head's own height, and the neck at the collar's 148."""
    document = json.loads(MESH.read_text())
    z = np.asarray(document["positions"], np.float64)[:, 2] / 1e5
    assert 148.0 <= z.min() <= 148.05, f"the neck ring is at z {z.min():.2f}, not the collar's 148"
    assert 186.0 <= z.max() <= 190.0, f"the crown is at z {z.max():.2f}"


def test_the_scene_carries_v1s_neck_skirt_so_it_is_not_stitched_twice():
    """The scene was derived from this pack; it already ends at the D79 ring."""
    document = json.loads(MESH.read_text())
    z = np.asarray(document["positions"], np.float64)[:, 2] / 1e5
    ring = np.nonzero(np.abs(z - 148.0) < 0.01)[0]
    assert 20 <= len(ring) <= 26, f"{len(ring)} scene vertices at z 148, expected v1's ring of 22"
    v1 = _drawable(_members(V1)[SUIT_MODELS[0]])
    assert len(v1["verts"]) - 4618 <= 2, "v2 must not carry a second skirt"


# ------------------------------------------------------- what must not move

@pytest.mark.parametrize("member", SAME_AS_V1)
def test_this_file_is_v1s_byte_for_byte(member: str):
    """Everything but the three models is v1's: same atlas encode, same material, same objects."""
    assert _members(PACK)[member] == _members(V1)[member], member


def test_the_pack_holds_the_same_files_as_v1():
    assert set(_members(PACK)) == set(_members(V1))


def test_the_geometry_is_v1s_topology_and_uvs():
    """Same triangle count, same UV keys: the atlas lands on it exactly as on v1."""
    v2 = _drawable(_members(PACK)[SUIT_MODELS[0]])
    v1 = _drawable(_members(V1)[SUIT_MODELS[0]])
    assert len(v2["tris"]) == len(v1["tris"]) == 8692, "the hair's back faces are doubled in both"
    assert v2["model_data"]["atoms"][0]["tri_count"] == 8692
    assert v2["model_data"]["atoms"][0]["material_id"] == v1["model_data"]["atoms"][0]["material_id"]
    # uv0 lands on the same atlas cell, but not on the same last bit: the scene's UVs
    # are float32 in Blender and v1's come from the `.dff`'s float16-ish stream. Every
    # corner is within 3e-3 UV (~6 texels at 2048, well inside one cell of the atlas).
    near = _nearest(v1["uv0"], v2["uv0"])
    assert near.max() < 3e-3, f"a v2 corner is {near.max():.4f} UV from any v1 corner"
    assert near.mean() < 1e-4, f"the two atlases are laid out differently (mean {near.mean():.5f})"


def test_the_weights_are_the_same_palette_and_the_same_bones():
    """Same bones, same blend: the scene was re-weighted onto the pack's own palette."""
    for model in SUIT_MODELS:
        v2 = _drawable(_members(PACK)[model])
        v1 = _drawable(_members(V1)[model])
        # the heist/menu unit numbers the head's three bones 40-42, the Safe House unit
        # 10132-10137; both packs take each unit's own numbers, unchanged
        assert v2["palette"] == v1["palette"], model
        assert len(v2["palette"]) in (3, 4), model
        assert v2["blendindices"].max() < len(v2["palette"]), (
            f"{model}: a vertex weights a palette slot that does not exist")
        assert np.allclose(v2["blendweights"].sum(axis=1), 1.0, atol=1e-3), model
        i2, i1 = _paired(v1, v2)
        assert len(i2) > 4000, model
        # the same palette slot and the same weight, vertex for vertex
        assert np.array_equal(v2["blendindices"][i2], v1["blendindices"][i1]), model
        # jaw_lift re-weights the moved crown, so a few weights differ by ~2e-3
        assert np.allclose(v2["blendweights"][i2], v1["blendweights"][i1], atol=5e-3), model


# ------------------------------------------------------------- what did move

def _paired(v1: dict, v2: dict) -> tuple[np.ndarray, np.ndarray]:
    """v2 vertex -> its v1 vertex: same uv0 cell, nearest position.

    Candidates are the v1 corners within 3e-3 UV (the two files store the same atlas
    cell with float32 rounding between them); among those the nearest in position is the
    one the vertex came from. The hair is in the mesh twice - v1 doubles it so the cutout
    cards read from inside - so more than one candidate is normal there.
    """
    near = _radii(v1["uv0"], v2["uv0"], 3e-3)
    i_v2, i_v1 = [], []
    for i, candidates in enumerate(near):
        if not len(candidates):
            continue
        i_v2.append(i)
        i_v1.append(int(min(candidates,
                            key=lambda q: np.linalg.norm(v1["verts"][q] - v2["verts"][i]))))
    return np.asarray(i_v2), np.asarray(i_v1)


def test_the_re_sculpt_is_present_and_small():
    """The reason the pack exists: a moved crown, and nothing else moved far."""
    v1 = _drawable(_members(V1)[SUIT_MODELS[0]])
    v2 = _drawable(_members(PACK)[SUIT_MODELS[0]])
    i2, i1 = _paired(v1, v2)
    assert len(i2) > 4000, f"only {len(i2)} of {len(v2['verts'])} v2 vertices paired with v1"
    moved = np.linalg.norm(v2["verts"][i2] - v1["verts"][i1], axis=1)
    assert np.median(moved) < 0.05, f"median vertex move {np.median(moved):.3f} cm: not a re-sculpt of v1"
    assert moved.max() < 1.0, f"a vertex moved {moved.max():.2f} cm: that is a different shape"
    # the change is the crown and the back of the skull, above the collar
    big = moved > 0.3
    assert big.sum() >= 40, "nothing moved: the packaged head is not the scene's"
    assert v2["verts"][i2][big][:, 2].min() > 165.0, (
        f"the neck moved: lowest large move at z {v2['verts'][i2][big][:, 2].min():.1f}")


def test_the_scene_supplies_the_normals_and_they_are_v1s():
    """v2's normals are the scene's own, and v1 stores the same ones.

    The comparison cannot be index-for-index: v1 ships the hair twice, at the same
    position and uv with opposite normals (so the cutout cards read from inside), and
    which copy a vertex pairs with is arbitrary. A v2 vertex therefore counts as
    agreeing when *any* v1 vertex at the same uv within 7 mm carries its normal.
    """
    v1 = _drawable(_members(V1)[SUIT_MODELS[0]])
    v2 = _drawable(_members(PACK)[SUIT_MODELS[0]])
    assert np.allclose(np.linalg.norm(v2["normals"], axis=1), 1.0, atol=1e-3)
    near = _radii(v1["uv0"], v2["uv0"], 3e-3)
    agree = total = 0
    for i in range(len(v2["verts"])):
        candidates = [q for q in near[i]
                      if np.linalg.norm(v1["verts"][q] - v2["verts"][i]) < 0.7]
        if not candidates:
            continue
        total += 1
        agree += max(float(np.dot(v2["normals"][i], v1["normals"][q])) for q in candidates) > 0.9
    assert total > 4500, f"only {total} v2 vertices have a v1 twin to compare with"
    assert agree / total > 0.95, f"only {agree / total * 100:.1f}% of normals agree with v1's"


@pytest.mark.parametrize("model", SUIT_MODELS)
def test_the_head_opens_no_neck_into_the_collar(model: str):
    """Stricter than `test_arivus_neck_fit`: the necklace must not be reachable.

    v2 ships the scene's skirt rather than a stitched one, so the guarantee is
    measured here on v2's own bytes: every vertex at the skirt's ring is inside the
    suit's closed neck, and the rim's lowest band stays under the collar.
    """
    members = _members(PACK)
    head = _drawable(members[model])
    body = _drawable(members[model], "g_body")
    ring = np.nonzero(np.abs(head["verts"][:, 2] - 148.0) < 0.05)[0]
    assert 20 <= len(ring) <= 26, f"{len(ring)} vertices at the skirt's ring, expected 22"
    outside = [int(i) for i in ring if not _enclosed(head["verts"][i], body)]
    assert not outside, f"{len(outside)} of {len(ring)} skirt vertices stick out of the suit"


def _enclosed(point: np.ndarray, body: dict) -> bool:
    """Ray parity along +-x and +-y against the suit's triangles."""
    verts, tris = body["verts"], body["tris"]
    v0 = verts[tris[:, 0]]
    e1 = verts[tris[:, 1]] - v0
    e2 = verts[tris[:, 2]] - v0
    for axis in (0, 1):
        direction = np.zeros(3)
        direction[axis] = 1.0
        h = np.cross(np.broadcast_to(direction, (len(tris), 3)), e2)
        a = np.einsum("ij,ij->i", h, e1)
        ok = np.abs(a) > 1e-12
        f = np.divide(1.0, a, out=np.zeros_like(a), where=ok)
        s = point - v0
        u = f * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = f * np.einsum("ij,ij->i", q, np.broadcast_to(direction, (len(tris), 3)))
        t = f * np.einsum("ij,ij->i", e2, q)
        hits = int((ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum())
        if hits % 2 == 0:
            return False
    return True
