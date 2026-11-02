"""Tests for the authored skin texture (`tools/pd2-las/skin_texture.py`).

The point of these tests is that the texture is *derived*, not hand-painted:
given a mesh, the baker must cover exactly the UV islands, darken creases,
produce a mip-chained DXT5 DDS whose normal map is in Diesel's channel packing,
and never leave an island surrounded by black (which mip-mapping would bleed
into the seams in game).
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
sys.path.insert(0, str(ROOT / "tools" / "skyrim-nif"))

import nif  # noqa: E402
import skin_texture as st  # noqa: E402


def test_mip_pyramid_halves_until_one_texel():
    img = np.zeros((64, 64, 4), np.uint8)
    chain = st.mip_pyramid(img)
    assert [c.shape[0] for c in chain] == [64, 32, 16, 8, 4, 2, 1]


def test_mip_levels_are_box_filtered():
    img = np.zeros((4, 4, 4), np.uint8)
    img[0, 0, 0] = 255
    level = st.mip_pyramid(img)[1]
    assert level.shape[0] == 2
    assert int(level[0, 0, 0]) == 255 // 4              # one of four texels


def test_bc3_with_mips_has_a_matching_header():
    img = np.full((32, 32, 4), 200, np.uint8)
    data = st.encode_bc3_mips(img)
    height, width = struct.unpack("<II", data[12:20])
    mips = struct.unpack("<I", data[28:32])[0]
    assert (width, height) == (32, 32)
    assert mips == 6
    assert data[84:88] == b"DXT5"
    assert len(data) > 128


def test_cavity_is_negative_on_a_convex_sphere():
    """Outward-curving surface reads as convex (negative concavity)."""
    n = 32
    theta = np.linspace(0, np.pi, n)
    phi = np.linspace(0, 2 * np.pi, n)
    verts = np.array([[np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)]
                      for t in theta for p in phi], dtype=np.float64)
    normals = verts.copy()
    faces = [[i * n + j, i * n + (j + 1) % n, ((i + 1) % n) * n + j]
             for i in range(n) for j in range(n)]
    cav = st.cavity(verts, normals, np.array(faces))
    assert float(np.median(cav)) < -0.05


def test_cavity_is_positive_in_a_crease():
    """A valley (z = |x|): the wall normals converge on the crease line."""
    r = 2 ** -0.5
    crease = 1
    verts = np.array([[-1, 0, 1], [0, 0, 0], [1, 0, 1],
                      [-1, 1, 1], [0, 1, 0], [1, 1, 1]], dtype=np.float64)
    normals = np.array([[r, 0, r], [0, 0, 1], [-r, 0, r],
                        [r, 0, r], [0, 0, 1], [-r, 0, r]], dtype=np.float64)
    tris = np.array([[0, 1, 4], [0, 4, 3],          # left wall
                     [1, 2, 5], [1, 5, 4]])         # right wall
    cav = st.cavity(verts, normals, tris)
    assert cav[crease] > 0.0, cav
    assert cav[crease + 3] > 0.0, cav


def test_bake_covers_the_uv_island_and_not_the_background():
    quad = {
        "verts": np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float64),
        "normals": np.array([[0, 0, 1.0]] * 4),
        "uvs": np.array([[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]),
        "tris": np.array([[0, 1, 2], [0, 2, 3]]),
    }
    bake = st.rasterize(quad, 64)
    cov = bake["coverage"]
    assert cov[32, 32]
    assert not cov[2, 2]
    assert 0.25 < cov.mean() < 0.45          # a 0.6 x 0.6 island
    assert bake["position"][32, 32, 2] == pytest.approx(0.0, abs=1e-6)


def test_diffuse_is_filled_and_skin_coloured():
    quad = {
        "verts": np.array([[0, 0, 60], [1, 0, 60], [1, 1, 60], [0, 1, 60]], np.float64),
        "normals": np.array([[0, 0, 1.0]] * 4),
        "uvs": np.array([[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]),
        "tris": np.array([[0, 1, 2], [0, 2, 3]]),
    }
    bake = st.rasterize(quad, 64)
    rgba = st.build_diffuse(bake, np.random.default_rng(0))
    assert rgba.shape == (64, 64, 4)
    assert rgba.dtype == np.uint8
    # alpha is gloss, not opacity: low sheen, never fully matte or mirrored
    assert st.SKIN_GLOSS_BASE <= int(rgba[..., 3].min())
    assert int(rgba[..., 3].max()) <= st.SKIN_GLOSS_BASE + st.SKIN_GLOSS_RANGE
    assert int(rgba[..., 3].std()) > 0                  # the field actually varies
    # nothing is left black: the dilation must reach every texel
    assert int(rgba[..., :3].max(axis=2).min()) > 40
    r, g, b = rgba[32, 32, :3].astype(int)
    assert r > g > b                                    # a warm skin tone


def test_normal_map_is_packed_the_way_diesel_reads_it():
    quad = {
        "verts": np.array([[0, 0, 60], [1, 0, 60], [1, 1, 60], [0, 1, 60]], np.float64),
        "normals": np.array([[0, 0, 1.0]] * 4),
        "uvs": np.array([[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]),
        "tris": np.array([[0, 1, 2], [0, 2, 3]]),
    }
    bake = st.rasterize(quad, 64)
    nm = st.build_normal(bake, np.random.default_rng(1))
    covered = bake["coverage"]
    inside = nm[covered]
    assert (inside[:, 0] == 255).all()                  # red: unused, white
    assert (inside[:, 2] == 0).all()                    # blue: unused, black
    assert 100 < inside[:, 1].mean() < 160              # green: Y around neutral
    assert 100 < inside[:, 3].mean() < 160              # alpha: X around neutral


def test_smooth_normals_replaces_a_missing_attribute():
    """BodySlide ships the 3BA body with the normal flag off."""
    verts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float64)
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    normals = nif.smooth_normals(verts, tris)
    np.testing.assert_allclose(normals, np.tile([0, 0, 1.0], (4, 1)), atol=1e-6)


@pytest.mark.skipif(not (ROOT / "4.zip").exists(), reason="4.zip absent")
def test_real_body_bakes(tmp_path):
    """End-to-end on the real meshes at a small resolution."""
    import zipfile

    with zipfile.ZipFile(ROOT / "4.zip") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".nif"):
                (tmp_path / Path(name).name).write_bytes(zf.read(name))
    mesh = st.load_body(tmp_path)
    assert len(mesh["verts"]) > 20_000
    bake = st.rasterize(mesh, 128)
    assert bake["coverage"].mean() > 0.3
    diffuse = st.build_diffuse(bake, np.random.default_rng(3))
    assert diffuse.shape == (128, 128, 4)
    assert int(diffuse[..., :3].max(axis=2).min()) > 40
