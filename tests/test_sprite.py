"""The 2D sprite operations, on synthetic images: no game assets, no ffmpeg, no network.

`um/sprite.py` had no test file at all, which is how `border_color` came to raise IndexError
for every image thinner or shorter than its 4x4 corner sample: a 64x2 hair strip, a 3x3 icon,
a 1x1 swatch. `um sprite info` and `um sprite cutout` both read the corner colour, so both
died with a traceback instead of a report. These tests pin the shapes a sheet slice or an
icon actually produces, and the one-line promise of each operation.
"""
from __future__ import annotations

import pytest

from um import sprite

Image = pytest.importorskip("PIL.Image", reason="sprite operations need pillow")

RED = (200, 30, 30, 255)
BG = (255, 255, 255, 255)


def flat(w: int, h: int, color=RED, bg=BG, border: int = 1):
    """An image of `color` on a `bg` border, the way a generated sprite arrives."""
    im = Image.new("RGBA", (w, h), bg)
    if w > 2 * border and h > 2 * border:
        im.paste(Image.new("RGBA", (w - 2 * border, h - 2 * border), color), (border, border))
    return im


@pytest.mark.parametrize("size", [(1, 1), (3, 3), (4, 4), (64, 2), (3, 64), (2, 300), (300, 2)])
def test_border_color_never_indexes_past_a_small_image(size):
    """Every corner sample is clamped to the image: no IndexError, whatever the shape."""
    im = Image.new("RGBA", size, BG)
    assert sprite.border_color(im) == BG[:3]


def test_border_color_reads_the_corners_not_the_middle():
    # the 4x4 corner sample has to sit inside the border: a 1-px frame is mostly subject
    im = flat(32, 32, RED, BG, border=6)
    assert sprite.border_color(im) == BG[:3]
    assert sprite.border_color(im, k=1) == BG[:3]
    # a subject that reaches the corners is what the corner colour becomes
    assert sprite.border_color(Image.new("RGBA", (8, 8), RED)) == RED[:3]


def test_border_color_of_a_zero_sized_image_is_defined():
    """An empty canvas has no corner to sample; answering (0, 0, 0) beats a traceback."""
    assert sprite.border_color(Image.new("RGBA", (0, 0))) == (0, 0, 0)
    assert sprite.border_color(Image.new("RGBA", (0, 8))) == (0, 0, 0)


@pytest.mark.parametrize("size", [(64, 2), (3, 64), (8, 8)])
def test_cutout_handles_thin_sprites_and_trims(size):
    """A thin sprite is a real input (a hair strip, a beam) and used to crash in cutout()."""
    im = Image.new("RGBA", size, BG)
    im.paste(Image.new("RGBA", (max(1, size[0] - 2), max(1, size[1] - 2)), RED), (1, 1))
    out = sprite.cutout(im)
    assert out.mode == "RGBA"
    assert out.width <= size[0] and out.height <= size[1]
    # the flat border is gone, so the bounding box is the content and not the frame
    assert out.getbbox() is not None


def test_cutout_keeps_interior_background_coloured_pixels():
    """A white eye inside a red sprite is not background: the fill starts at the border."""
    im = flat(9, 9, RED, BG, border=2)
    im.putpixel((4, 4), BG)
    out = sprite.cutout(im, tol=10)
    assert out.size == (5, 5)               # the border is gone, the content is trimmed to it
    assert out.getpixel((2, 2))[3] == 255   # the enclosed white pixel survives


def test_cutout_holes_clears_enclosed_background():
    im = flat(9, 9, RED, BG, border=2)
    im.putpixel((4, 4), BG)
    out = sprite.cutout(im, tol=10, holes=True)
    assert out.getpixel((2, 2))[3] == 0     # the enclosed white pixel is cleared too


def test_cutout_of_an_already_transparent_image_only_trims():
    im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (4, 4), RED), (3, 3))
    out = sprite.cutout(im)
    assert out.size == (4, 4)


def test_info_reports_a_thin_image_instead_of_raising():
    info = sprite.info(Image.new("RGBA", (64, 2), BG))
    assert info["size"] == (64, 2)
    assert info["corner_color"] == BG[:3]
    assert info["opaque"] == 1.0


def test_fit_returns_exactly_the_frame_size_and_keeps_aspect():
    out = sprite.fit(flat(20, 10), 16, 16)
    assert out.size == (16, 16)
    # a 2:1 sprite fits the width; the frame keeps it centred
    assert out.getbbox() is not None
    assert out.getbbox()[3] - out.getbbox()[1] == 8


def test_fit_anchor_bottom_and_no_upscale():
    out = sprite.fit(flat(4, 4), 8, 8, anchor="bottom", allow_upscale=False)
    bbox = out.getbbox()
    assert out.size == (8, 8)
    assert bbox[1] == 4 and bbox[3] == 8


def test_fit_rejects_an_unknown_anchor():
    with pytest.raises(KeyError):
        sprite.fit(flat(4, 4), 8, 8, anchor="middle")


def test_hard_alpha_is_binary():
    im = Image.new("RGBA", (4, 1))
    im.putdata([(1, 2, 3, 0), (1, 2, 3, 127), (1, 2, 3, 128), (1, 2, 3, 255)])
    out = sprite.hard_alpha(im, 128)
    assert list(out.getchannel("A").tobytes()) == [0, 0, 255, 255]


def test_pixelate_fits_the_frame_and_limits_the_palette():
    out = sprite.pixelate(flat(40, 20), 16, 16, colors=4)
    assert out.size == (16, 16)
    rgb, a = out.convert("RGB").tobytes(), out.getchannel("A").tobytes()
    opaque = {(rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2]) for i in range(len(a)) if a[i]}
    assert 1 <= len(opaque) <= 4


def test_sheet_then_slice_round_trips_the_frames():
    frames = [flat(8, 8), flat(8, 8), flat(8, 8)]
    sheet = sprite.sheet(frames, cols=3)
    assert sheet.size == (24, 8)
    cut = sprite.slice_sheet(sheet, 8, 8)
    assert len(cut) == 3
    assert all(f.size == (8, 8) for f in cut)


def test_vertical_sheet_is_a_strip():
    assert sprite.sheet([flat(6, 4), flat(6, 4)], vertical=True).size == (6, 8)


def test_snap_palette_maps_every_pixel_to_the_reference_colours():
    im = Image.new("RGBA", (2, 1))
    im.putdata([(250, 5, 5, 255), (10, 10, 240, 255)])
    out = sprite.snap_palette(im, [(255, 0, 0), (0, 0, 255)])
    b = out.convert("RGB").tobytes()   # getdata() is deprecated from Pillow 14
    assert [(b[0], b[1], b[2]), (b[3], b[4], b[5])] == [(255, 0, 0), (0, 0, 255)]


def test_palette_from_ignores_transparent_pixels():
    im = Image.new("RGBA", (3, 1))
    im.putdata([(1, 2, 3, 255), (1, 2, 3, 255), (9, 9, 9, 0)])
    assert sprite.palette_from(im) == [(1, 2, 3)]


def test_team_mask_returns_a_mask_matching_the_sprite():
    im = Image.new("RGBA", (4, 1))
    im.putdata([(0, 0, 255, 255), (255, 0, 0, 255), (10, 10, 10, 255), (0, 0, 0, 0)])
    sprite_out, mask = sprite.team_mask(im, hue="blue")
    assert mask.mode == "L" and mask.size == im.size
    assert mask.getpixel((0, 0)) == 255   # the blue accent becomes the player-colour mask
    assert mask.getpixel((2, 0)) == 0     # grey shading does not
    assert mask.getpixel((3, 0)) == 0     # nor does a transparent pixel


def test_preview_scales_and_stays_opaque():
    out = sprite.preview(flat(4, 4), scale=3)
    assert out.size == (12, 12)
    assert out.getextrema()[3][0] == 255


def test_trim_and_outline_are_no_ops_on_an_empty_image():
    empty = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
    assert sprite.trim(empty).size == (5, 5)
    assert sprite.add_outline(empty).getbbox() is None
