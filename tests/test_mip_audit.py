"""`tools/pd2-las/mip_audit.py`: its arithmetic, and that the tracked pack is where it says.

The audit judges the two Miranda textures the build encodes itself. Its limits
were written before anything was measured against them; the last test here is
what keeps the tracked pack inside them, and keeps the list of known misses
honest in both directions.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_las  # noqa: E402
import dds_encode  # noqa: E402
import mip_audit  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mip_audit.PACK.is_file() or not (REPO / "models" / "l4d2_miranda_lawson_1.zip").is_file(),
    reason="the tracked Miranda_LAS.zip or the source zip is missing; restore them with `git checkout -- dist models`")


def test_ciede2000_matches_the_published_test_pairs():
    """The first twelve pairs of Sharma, Wu and Dalal's test data (2005).

    They are chosen by its authors to trip an implementation: hue angles on both
    sides of 180 degrees, a grey sample, chroma near zero. scikit-image 0.26.0
    gives the same twelve values (checked on 2026-11-11).
    """
    blue = (50.0, 0.0, -82.7485)
    pairs = [
        ((50.0, 2.6772, -79.7751), blue, 2.0425),
        ((50.0, 3.1571, -77.2803), blue, 2.8615),
        ((50.0, 2.8361, -74.0200), blue, 3.4412),
        ((50.0, -1.3802, -84.2814), blue, 1.0000),
        ((50.0, -1.1848, -84.8006), blue, 1.0000),
        ((50.0, -0.9009, -85.5211), blue, 1.0000),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, -1.0, 2.0), (50.0, 0.0, 0.0), 2.3669),
        ((50.0, 2.49, -0.001), (50.0, -2.49, 0.0009), 7.1792),
        ((50.0, 2.49, -0.001), (50.0, -2.49, 0.0010), 7.1792),
        ((50.0, 2.49, -0.001), (50.0, -2.49, 0.0011), 7.2195),
        ((50.0, 2.49, -0.001), (50.0, -2.49, 0.0012), 7.2195),
    ]
    for first, second, want in pairs:
        assert round(float(mip_audit.delta_e2000(np.array(first), np.array(second))), 4) == want
    lab = np.array([[40.0, 10.0, -30.0], [70.0, -5.0, 12.0]])
    assert (mip_audit.delta_e2000(lab, lab) == 0).all()
    assert mip_audit.delta_e2000(lab[0], lab[1]) == pytest.approx(mip_audit.delta_e2000(lab[1], lab[0]))


def test_srgb_to_lab_on_known_colours():
    """White, black, mid grey and pure red, to two decimals (the same as scikit-image gives)."""
    for rgb, want in (((255, 255, 255), (100.0, 0.0, 0.0)), ((0, 0, 0), (0.0, 0.0, 0.0)),
                      ((128, 128, 128), (53.59, 0.0, 0.0)), ((255, 0, 0), (53.24, 80.09, 67.20)),
                      ((22, 61, 126), (26.77, 12.07, -40.69))):
        assert np.abs(mip_audit.srgb_to_lab(np.array(rgb, dtype=float)) - want).max() < 0.006, rgb
    image = np.array([[[10, 20, 30, 0], [200, 100, 50, 0]]], dtype=np.uint8)
    assert (mip_audit.colour_difference(image, image) == 0).all()
    assert mip_audit.colour_difference(image, image[:, ::-1]).min() > 40


def test_the_limits_are_the_ones_written_before_measuring():
    """Changing a limit is allowed, as a decision. It is not allowed as a way to pass."""
    assert mip_audit.LIMITS == {
        "near": {"colour_mean": 2.0, "colour_p99": 6.0, "iris": 3.0, "gloss_mean": 1.0, "gloss_max": 4},
        "far": {"colour_mean": 3.0, "colour_p99": 10.0, "iris": 6.0, "gloss_mean": 1.5, "gloss_max": 8},
    }
    assert (mip_audit.DISTANCES_M, mip_audit.SCREENS, mip_audit.NEAR_M) == ((1, 2, 4, 8, 16), (1080, 2160), (1, 8))
    figures = {"colour_mean": 2.5, "colour_p99": 5.0, "gloss_mean": 0.1, "gloss_max": 9, "iris": 4.0}
    assert set(mip_audit.verdict(figures, near=True)) == {"colour_mean", "iris", "gloss_max"}
    assert set(mip_audit.verdict(figures, near=False)) == {"gloss_max"}


def test_level_on_screen_is_log2_of_texels_per_pixel():
    ppc = mip_audit.pixels_per_cm(1, 1080)
    assert ppc == pytest.approx(1080 / (200 * math.tan(math.radians(mip_audit.GAME_FOV_DEG / 2))))
    assert ppc == pytest.approx(8.476, abs=0.001)                # one centimetre is 8.5 pixels at 1 m
    assert mip_audit.pixels_per_cm(2, 2160) == pytest.approx(ppc)
    level = mip_audit.level_on_screen(100.0, 2, 1080)
    assert level == pytest.approx(math.log2(100.0 / (ppc / 2)))
    assert mip_audit.level_on_screen(100.0, 4, 1080) == pytest.approx(level + 1)      # twice as far: one level down
    assert mip_audit.level_on_screen(100.0, 2, 2160) == pytest.approx(level - 1)      # twice the pixels: one level up
    assert mip_audit.level_on_screen(1.0, 1, 2160) == 0.0                             # never finer than level 0
    # the densities measured on the tracked head: every level that is on screen up to 8 m at 1080p
    assert mip_audit.near_levels(103.0, 10) == set(range(8))
    assert mip_audit.near_levels(46.0, 11) == set(range(7))
    assert mip_audit.near_levels(5000.0, 4) == set(range(4))


def test_texel_density_of_the_tracked_head():
    """The eye texture is twice as dense on the mesh as the face: its small levels are on screen sooner."""
    head = mip_audit.Head()
    assert set(mip_audit.ROLES.values()) <= set(head.parts)
    eyes, low, high = head.density("mtr_eyes", 512)
    face = head.density("mtr_face", 1024)[0]
    # measured: 103 texels per cm (47 to 137) and 46
    assert 95 < eyes < 110 and low < eyes < high
    assert 42 < face < 50


def test_sampling_is_trilinear():
    white, black = np.full((4, 4, 3), 255.0), np.zeros((2, 2, 3))
    u = v = np.array([0.3, 0.8])
    assert (mip_audit.sample([white, black], u, v, 0.0) == 255).all()
    assert (mip_audit.sample([white, black], u, v, 1.0) == 0).all()
    assert mip_audit.sample([white, black], u, v, 0.25) == pytest.approx(255 * 0.75)
    assert (mip_audit.sample([white, black], u, v, 7.0) == 0).all()          # past the last level: the last level
    assert (mip_audit.sample([white], u, v, 5.0) == 255).all()               # one level: there is nothing to blend
    # bilinear inside a level, and the texture repeats
    ramp = np.zeros((1, 4, 3))
    ramp[0, :, 0] = (0, 100, 200, 100)
    centre = mip_audit.sample([ramp], np.array([0.375, 0.5, 0.0]), np.array([0.5, 0.5, 0.5]), 0.0)[:, 0]
    assert centre == pytest.approx([100.0, 150.0, 50.0])


def test_render_draws_the_head_from_the_front():
    head = mip_audit.Head()
    textures = mip_audit.pack_textures(head, dds_encode.decode_bc3_level)
    picture = mip_audit.render(head, textures, ppc=1.5)
    assert picture.shape == (33, 33, 3) and picture.dtype == np.uint8
    skin = picture[14:24, 12:21].reshape(-1, 3).astype(int).mean(axis=0)
    assert skin[0] > skin[2] + 20 and skin.sum() > 250, skin            # the face: warm and light
    assert picture[0, 0].astype(int).sum() < 150, picture[0, 0]         # the corner: hair or nothing
    ideal = mip_audit.render(head, textures, ppc=1.5, ideal=True)
    assert ideal.shape == picture.shape
    assert np.abs(ideal.astype(int) - picture.astype(int)).mean() < 25


def test_the_decoders_of_this_repository_agree_on_the_tracked_textures():
    """Pillow and `tools/pd2-port/dds.py` read the same bytes to within one step of 255.

    The report adds `texture2ddecoder`, which this repository did not write, when
    it is installed; it agreed with Pillow exactly on 2026-11-11.
    """
    import zipfile

    available = mip_audit.decoders()
    assert {"Pillow", "tools/pd2-port/dds.py"} <= set(available)
    with zipfile.ZipFile(mip_audit.PACK) as z:
        for role in mip_audit.ROLES:
            raw = z.read(f"{mip_audit.UNIT}/miranda_{role}.texture")
            for level in range(len(dds_encode.bc3_levels(raw))):
                a = available["Pillow"](raw, level).astype(int)
                b = available["tools/pd2-port/dds.py"](raw, level).astype(int)
                assert a.shape == b.shape and np.abs(a - b).max() <= 1, (role, level)


def test_the_eye_levels_are_the_picture_a_finer_drawing_gives():
    """The eye is drawn once and averaged down. Drawn again at each size it is another picture.

    The yardstick is the eye drawn with sixteen points per texel of level 0 and
    averaged. The build's levels, one point per texel of level 0 and averaged,
    stay within 2 of it in every texel of every level (measured: at most 1.66)
    and keep its iris. The eye drawn again with one point per texel of a level
    is as good at 512 and 256 and falls apart below, because the fibres of the
    iris fall between the points: at 32x32 one texel in a hundred is off by more
    than 13, and at 4x4 the iris is off by 11. That is why the levels are
    averages of one drawing (D24).
    """
    fine, built = mip_audit.eye_drawn_finer(), build_las.mip_levels(build_las.draw_eye())
    assert [level.shape for level in fine] == [level.shape for level in built]
    assert len(built) == 10 and built[0].shape == (512, 512, 4)
    for level, (want, got) in enumerate(zip(fine, built)):
        figures = mip_audit.measure(want, got, True)
        assert figures["colour_max"] < 2.0 and figures["gloss_max"] <= 4, (level, figures)
        assert figures.get("iris", 0.0) < 0.05, (level, figures)
    each = {level: mip_audit.measure(fine[level], build_las.draw_eye(fine[level].shape[0], check=False), True) for level in (1, 4, 7)}
    assert each[1]["colour_max"] < 2.0
    assert each[4]["colour_p99"] > 10 and each[7]["iris"] > 6, each


def test_the_tracked_pack_meets_the_limits_except_the_known_misses():
    """Every level of both textures, against `LIMITS`; what it misses is `KNOWN_MISSES`, exactly.

    The face passes at every level. The eyes miss the per-texel colour limits
    from 64x64 down to 4x4, as every encoder that was tried does on that picture,
    and meet the iris limit at every level: the list says so, and a level that
    gets worse or better than the list fails here.
    """
    results = mip_audit.audit_pack()
    assert sorted(results) == sorted([("face_df", k) for k in range(11)] + [("eyes", k) for k in range(10)])
    assert not mip_audit.unexpected(results), "\n".join(mip_audit.unexpected(results))
    assert all(role == "eyes" and 3 <= level <= 7 for role, level in mip_audit.KNOWN_MISSES)
    assert not any("iris" in names or "gloss_max" in names or "gloss_mean" in names
                   for names in mip_audit.KNOWN_MISSES.values())
    irises = {level: figures["iris"] for (role, level), figures in results.items() if "iris" in figures}
    assert sorted(irises) == list(range(8))                      # 512x512 down to 4x4
    assert max(irises.values()) < 2.0                            # measured: at most 1.71
    assert max(figures["gloss_max"] for figures in results.values()) <= 3
    assert {level for (role, level), figures in results.items() if role == "face_df" and figures["near"]} == set(range(7))
    assert {level for (role, level), figures in results.items() if role == "eyes" and figures["near"]} == set(range(8))
