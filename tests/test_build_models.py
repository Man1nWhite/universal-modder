"""Tests for the miranda -> 2B LAS skin authoring pipeline (build_models).

Unit tests cover the Procrustes fit. Integration tests run the full authoring
into memory and assert the structural contract of the produced models
(group/material wiring, faces+UVs preserved verbatim, blend weights valid,
geometry sane, assembled bytes re-readable). They need the extracted 2B LAS
templates at /tmp/2bsrc (`unrar x 2b.rar` after downloading the archive;
tools/pd2-las/README.md has the exact steps).
"""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
from source_model import load_model  # noqa: E402
from vpk import VpkArchive  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b")
needs_templates = pytest.mark.skipif(
    not TEMPLATES.exists(), reason="extracted 2B templates at /tmp/2bsrc not present"
)


# ---------------------------------------------------------------- unit: fit


def _apply(m, p):
    x, y, z = p
    return (
        x * m[0] + y * m[4] + z * m[8] + m[12],
        x * m[1] + y * m[5] + z * m[9] + m[13],
        x * m[2] + y * m[6] + z * m[10] + m[14],
    )


def test_umeyama_recovers_similarity():
    # known similarity: yaw 37 deg, scale 2.5, translation (4, -1, 7)
    a = math.radians(37.0)
    c, s = math.cos(a), math.sin(a)
    scale = 2.5
    t = (4.0, -1.0, 7.0)
    colR = (c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0)  # column-major yaw about z

    def fwd(p):
        x, y, z = p
        rx = colR[0] * x + colR[3] * y + colR[6] * z
        ry = colR[1] * x + colR[4] * y + colR[7] * z
        rz = colR[2] * x + colR[5] * y + colR[8] * z
        return (scale * rx + t[0], scale * ry + t[1], scale * rz + t[2])

    src = [(i * 1.3, (i * -0.7) % 3.1, i * 0.9) for i in range(8)]
    tgt = [fwd(p) for p in src]
    m = bm._umeyama_fit(src, tgt, [1.0] * len(src))
    for p, q in zip(src, tgt):
        got = _apply(m, p)
        for a_, b_ in zip(got, q):
            assert abs(a_ - b_) < 1e-6


def test_umeyama_scale_clamped():
    src = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    tgt = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 100.0, 0.0)]
    m = bm._umeyama_fit(src, tgt, [1.0] * 3)
    sc = (m[0] ** 2 + m[1] ** 2 + m[2] ** 2) ** 0.5
    assert sc <= bm.FIT_SCALE_CLAMP[1] + 1e-9


def test_render_textured_sampler_orientation(tmp_path):
    """The UV probe's sampler: (u, v) -> (u*(w-1), v*(h-1)), nearest texel.

    An 8x8 gradient (r grows with u, g grows with v) sampled through a
    triangle with known corner uvs locks both the mapping and the flip
    orientation used to compare our UVs with the 2B reference (uv_check.py).
    """
    import preview

    class Tex:
        size = (8, 8)

        def getpixel(self, xy):
            i, j = xy
            return (i * 28, j * 28, 40)

    # triangle in the z=0 plane: uv (0,0) at world origin, u along +x, v along +y
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    out = tmp_path / "t.png"
    preview.render_textured(verts, [(0, 1, 2)], uvs, Tex(), out, view="top", size=64)
    from PIL import Image

    im = Image.open(out)
    w, h = im.size

    def px(fx, fy):
        return im.getpixel((int(w * fx), int(h * fy)))[:3]

    bl = px(0.32, 0.68)   # near uv (0,0): both channels low
    br = px(0.68, 0.68)   # near uv (1,0): r high
    tl = px(0.32, 0.32)   # near uv (0,1): g high
    assert br[0] > bl[0] + 100, (bl, br)      # u axis -> r channel
    assert tl[1] > bl[1] + 100, (bl, tl)      # v axis -> g channel
    assert bl[0] < 80 and bl[1] < 80, bl      # corner (0,0) stays dark


# ------------------------------------------------------- integration: author


def _author():
    arc = VpkArchive.from_zip(str(REPO / "l4d2_miranda_lawson_1.zip"), "miranda_rochelle.vpk")
    tpp = load_model(*(arc.read(p) for p in bm.TPP_MDLS))
    fps = load_model(*(arc.read(p) for p in bm.FPS_MDLS))
    skel_map = json.loads((REPO / "tools/pd2-las/skeleton_map.json").read_text())
    out = {}
    for label, model, tpl_name, specs in (
            ("tpp", tpp, "2b.model", bm.TPP_GROUPS),
            ("fps", fps, "fps_2b.model", bm.FPS_GROUPS)):
        template = bm.load_template(TEMPLATES / tpl_name)
        groups = {}
        share = {}
        for gname, spec in specs.items():
            groups[gname] = bm.transfer_group(model, spec, skel_map, template, gname)
            for d in spec["drawables"]:
                share[d] = gname
        mf = bm.assemble_model(template, groups, share)
        out[label] = {"model": model, "groups": groups, "mf": mf, "template": template}
    return out


@pytest.fixture(scope="module")
def authored():
    if not TEMPLATES.exists():
        pytest.skip("templates")
    return _author()


def _slice_verts(g, material):
    verts, uvs, ntris = [], [], 0
    for (mat, base_v, base_i, tris, nverts) in g.slices:
        if mat == material:
            verts += g.verts[base_v:base_v + nverts]
            uvs += g.uvs[base_v:base_v + nverts]
            ntris += tris
    return verts, uvs, ntris


@needs_templates
def test_tpp_groups_and_counts(authored):
    groups = authored["tpp"]["groups"]
    assert len(groups["body"].verts) == 5645 and len(groups["body"].faces) == 9548
    assert len(groups["head"].verts) == 4229 and len(groups["head"].faces) == 6885
    assert len(groups["shadow"].verts) == 9874 and len(groups["shadow"].faces) == 16433
    # fps
    fgroups = authored["fps"]["groups"]
    assert len(fgroups["arms"].verts) == 1774 and len(fgroups["arms"].faces) == 2892
    # palettes compact and weights valid
    for g in list(groups.values()) + list(fgroups.values()):
        assert 0 < len(g.palette) <= 53
        for infl in g.weights:
            assert infl and all(0 <= i < len(g.palette) for i, _ in infl)
            assert abs(sum(w for _, w in infl) - 1.0) < 1e-4


@needs_templates
def test_faces_and_uvs_preserved(authored):
    tpp = authored["tpp"]
    src_by_mat = {}
    for mesh in tpp["model"].meshes:
        d = src_by_mat.setdefault(mesh.material, {"tris": 0, "uvs": []})
        d["tris"] += len(mesh.triangle_indices) // 3
        seen = []
        for vi in mesh.triangle_indices:
            if vi not in seen:
                seen.append(vi)
        d["uvs"] += [tpp["model"].vertices[vi].uv for vi in seen]
    dst_by_mat = {}
    for gname, material in (("body", "miranda_body"), ("head", "miranda_head"),
                            ("head", "miranda_face"), ("head", "miranda_hair")):
        _, uvs, ntris = _slice_verts(tpp["groups"][gname], material)
        d = dst_by_mat.setdefault(material, {"tris": 0, "uvs": []})
        d["tris"] += ntris
        d["uvs"] += uvs
    for mat in ("miranda_body", "miranda_head", "miranda_face", "miranda_hair"):
        s, d = src_by_mat[mat], dst_by_mat[mat]
        assert s["tris"] == d["tris"], mat
        # slice vertex order is first-appearance, so compare UV multisets;
        # authoring writes the p2mt GLTF-import convention (u, 1 - v_src)
        key = lambda u: (round(u[0], 5), round(u[1], 5))
        src_uv = [(u, 1.0 - v) for u, v in s["uvs"]]
        assert sorted(map(key, src_uv)) == sorted(map(key, d["uvs"])), mat


@needs_templates
def test_geometry_sane_and_winding_positive(authored):
    g = authored["tpp"]["groups"]["shadow"]
    vol = 0.0
    v = g.verts
    for (a, b, c) in g.faces:
        p, q, r = v[a], v[b], v[c]
        vol += (p[0] * (q[1] * r[2] - q[2] * r[1])
                - p[1] * (q[0] * r[2] - q[2] * r[0])
                + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6.0
    # healthy transfer ≈ 16x the source signed volume (4141.8 in^3 -> cm^3)
    assert 50000 < vol < 100000, vol
    zs = [p[2] for p in v]
    # loose envelope only: exact ground contact is an in-game check
    assert min(zs) > -25 and max(zs) < 250, (min(zs), max(zs))


@needs_templates
def test_face_region_upright_near_head(authored):
    """Face verts must land in the head box of the target rig, not at the origin."""
    verts, _, _ = _slice_verts(authored["tpp"]["groups"]["head"], "miranda_face")
    assert verts
    xs = [p[0] for p in verts]
    ys = [p[1] for p in verts]
    zs = [p[2] for p in verts]
    # head sits high (z ~ 150-185 cm), face near the centerline
    assert 120 < sum(zs) / len(zs) < 200, sum(zs) / len(zs)
    assert abs(sum(xs) / len(xs)) < 15, sum(xs) / len(xs)
    assert (max(zs) - min(zs)) < 60  # not exploded


@needs_templates
def test_written_models_roundtrip(authored):
    for label, name in (("tpp", "miranda.model"), ("fps", "fps_miranda.model")):
        data = authored[label]["mf"].write()
        assert len(data) > 10000
        mf = dm.ModelFile.read(data)
        geos = [dm.decode_geometry(s.payload) for s in mf.by_type(dm.GEOMETRY)]
        # authored geometry carries blend weights of arity 3
        assert any(len(g["blendweights"][0]) == 3 for g in geos)
        # geometry sections we authored are named "<group>.DieselGeometry"
        expected = 0
        for gname, g in authored[label]["groups"].items():
            expected += len(g.verts)
            hit = [x for x in geos if x["name_hash"] == dm.hash64(f"{gname}.DieselGeometry")]
            assert len(hit) == 1 and len(hit[0]["verts"]) == len(g.verts), gname
