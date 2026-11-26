"""The Arivus head must meet Old Hoxton's collar from every angle (D72, D79).

D72 cut the ped's neck and then dragged the whole cone down and up again to hide
the cut; that squashed the neck and still left its open rim in the collar
opening as a jagged skin line. D79 leaves the ped where it lands, drops only the
cut rim to the collar's height, and closes it with a skirt tucked inside the
suit.

These are measurements on the shipped models (heist, menu and Safe House), not
on a render: the offline sheets are bind-pose and cannot see skinning at all,
which is why the D72 regression survived them. Every assertion below failed on
the D72 bytes.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import diesel_model as dm  # noqa: E402
from dist_paths import dist_path  # noqa: E402

PACK = dist_path(ROOT, "Arivus_over_Hoxton.zip")
PREFIX = "Arivus over Hoxton"
MODELS = (
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_1.model",
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_menu_1.model",
    "units/pd2_dlc_chill/characters/shared_character/npc_criminals_suit_chill.model",
)
HEAD = "g_head_old_hoxton"
BODY = "g_body"
#: where the suit still surrounds the neck on all three models, measured from
#: the vanilla extract; the skirt ends at z 148 and must be inside above that.
SKIRT_Z = 148.0


def _drawable(mf: dm.ModelFile, name: str) -> tuple[np.ndarray, np.ndarray, dict]:
    want = dm.hash64(name)
    for shape in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(shape.payload)
        if md.get("version") != 3 or not md.get("atoms") or md.get("name_hash") != want:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = np.array(dm.decode_topology(mf.by_id(gp["topology"]).payload)["indices"],
                        np.int64).reshape(-1, 3)
        a0 = md["atoms"][0]
        tris = topo[a0["base_index"] // 3: a0["base_index"] // 3 + a0["tri_count"]]
        return np.asarray(geo["verts"], np.float64), tris, {"geometry": geo, "model_data": md}
    raise AssertionError(f"{name} missing from the pack")


def _model(model_rel: str) -> dm.ModelFile:
    with zipfile.ZipFile(PACK) as zf:
        return dm.ModelFile.read(zf.read(f"{PREFIX}/{model_rel}"))


def _boundary_edges(tris: np.ndarray) -> list[tuple[int, int]]:
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            if u == w:
                continue
            key = (min(int(u), int(w)), max(int(u), int(w)))
            counts[key] = counts.get(key, 0) + 1
    return [k for k, n in counts.items() if n == 1]


def _enclosed(point: np.ndarray, body_v: np.ndarray, body_t: np.ndarray) -> bool:
    """Ray-parity inside test: odd crossings along +-x and +-y."""
    for axis in (0, 1):
        for sign in (1.0, -1.0):
            direction = np.zeros(3)
            direction[axis] = sign
            v0 = body_v[body_t[:, 0]]
            e1 = body_v[body_t[:, 1]] - v0
            e2 = body_v[body_t[:, 2]] - v0
            h = np.cross(np.broadcast_to(direction, (len(body_t), 3)), e2)
            a = np.einsum("ij,ij->i", h, e1)
            ok = np.abs(a) > 1e-12
            f = np.divide(1.0, a, out=np.zeros_like(a), where=ok)
            s = point - v0
            u = f * np.einsum("ij,ij->i", s, h)
            q = np.cross(s, e1)
            v = f * np.einsum("ij,ij->i", q, np.broadcast_to(direction, (len(body_t), 3)))
            t = f * np.einsum("ij,ij->i", e2, q)
            hits = int((ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum())
            if hits % 2 == 0:
                return False
    return True


@pytest.mark.parametrize("model_rel", MODELS)
def test_the_cut_rim_ends_under_the_collar(model_rel: str) -> None:
    """The ped's V of a cut must not stand above the collar's own rim (~160)."""
    head_v, head_t, _ = _drawable(_model(model_rel), HEAD)
    boundary = _boundary_edges(head_t)
    near_axis = [e for e in boundary
                 if max(head_v[e[0], 2], head_v[e[1], 2]) < 170.0
                 and max(np.hypot(head_v[e[0], 0], head_v[e[0], 1]),
                         np.hypot(head_v[e[1], 0], head_v[e[1], 1])) < 9.5]
    rim_z = np.array([max(head_v[a, 2], head_v[b, 2]) for a, b in near_axis])
    # D79: nothing of the cut ring is left standing above the collar.
    assert len(rim_z) > 0, "no neck rim found: the rim must exist to be closed"
    assert rim_z.max() <= 160.5, f"cut rim reaches z {rim_z.max():.2f}, above the collar"


@pytest.mark.parametrize("model_rel", MODELS)
def test_the_skirt_ends_inside_the_suit(model_rel: str) -> None:
    """The face and hair do not need an open neck edge; the suit hides it."""
    mf = _model(model_rel)
    head_v, _, _ = _drawable(mf, HEAD)
    body_v, body_t, _ = _drawable(mf, BODY)
    skirt = np.nonzero(np.abs(head_v[:, 2] - SKIRT_Z) < 0.05)[0]
    assert len(skirt) >= 20, "the skirt ring is missing from the pack"
    outside = [int(i) for i in skirt if not _enclosed(head_v[i], body_v, body_t)]
    assert len(outside) <= 1, (
        f"{len(outside)} of {len(skirt)} skirt vertices stick out of the suit; "
        "the neck's open edge would show in the collar opening")


@pytest.mark.parametrize("model_rel", MODELS)
def test_the_head_is_not_squashed(model_rel: str) -> None:
    """D72 pulled the cone down 6 cm and up 4; the ped's own throat must stay."""
    head_v, _, _ = _drawable(_model(model_rel), HEAD)
    # the throat's front, where D72 shortened the neck the most
    throat = (np.abs(head_v[:, 0]) < 3.0) & (head_v[:, 1] > 7.0) & (head_v[:, 2] < 168.0)
    assert int(throat.sum()) > 0
    # the ped's own cut is at z 159.4; a squashed neck leaves the throat below it
    assert head_v[throat, 2].max() >= 159.0, "the throat has been shortened again"


@pytest.mark.parametrize("model_rel", MODELS)
def test_every_head_vertex_indexes_its_own_skin_palette(model_rel: str) -> None:
    """`bone_offset` bug (D73/D79): the palette is [Spine2, Neck, Head], indices 0-2."""
    mf = _model(model_rel)
    _, _, extra = _drawable(mf, HEAD)
    md = extra["model_data"]
    sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
    palette = sb["maps"][0]
    blend = np.asarray(extra["geometry"]["blendindices"], dtype=np.int64)
    out_of_range = int((blend >= len(palette)).any(axis=1).sum())
    assert out_of_range == 0, (
        f"{out_of_range} of {len(blend)} vertices weight a palette slot that does not exist "
        f"(palette {palette}, SkinBones objects {sb['objects']})")
    weights = np.asarray(extra["geometry"]["blendweights"], dtype=np.float64)
    assert np.allclose(weights.sum(axis=1), 1.0, atol=1e-3)


# ---------------------------------------------------------------- the helpers
# These pin the two geometric moves the pack ships, so a future edit to either
# shows up as a test change rather than as a different-looking neck.

def test_the_skirt_tucks_inward_and_lands_at_the_bottom():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_joy_head_mods as bj

    rim = np.array([[2.0, 3.0, 160.0], [0.0, 5.0, 160.0], [-2.0, 3.0, 160.0]])
    out = bj.neck_skirt_ring(rim, (0.0, 1.0), 148.0, 0.5)
    assert np.allclose(out[:, 2], 148.0)
    # every column is half as far from the axis, and none of them moved outward
    before = np.hypot(rim[:, 0], rim[:, 1] - 1.0)
    after = np.hypot(out[:, 0], out[:, 1] - 1.0)
    assert np.allclose(after, before * 0.5)
    assert np.all(after < before)


def test_the_rim_push_keeps_the_throat_and_drops_the_back():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_joy_head_mods as bj

    p = np.array([[0.0, 8.0, 159.4],    # the throat's lowest cut point
                  [6.0, 1.0, 164.8],    # the side
                  [0.0, -6.0, 169.8]])  # the back, the highest point of the V
    bj.push_neck_rim(p, [0, 1, 2], target_z=159.0, fade_deg=60.0)
    assert p[0, 2] == pytest.approx(159.4), "the throat must keep its length"
    assert p[1, 2] == pytest.approx(159.0)
    assert p[2, 2] == pytest.approx(159.0)
    # nothing is ever pushed up
    assert np.all(p[:, 2] <= np.array([159.4, 164.8, 169.8]))
