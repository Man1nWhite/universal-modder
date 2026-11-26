"""The clean-shaven Arivus face: what `shave_arivus_face` removes, keeps and leaves behind (D64).

Random4 has no beard geometry - its beard, moustache and sideburns are painted into
`head_diff_000_a_whi`, one dark blob from the temples around the jaw - so a clean shave means
inpainting most of the lower face. These tests pin the three things that read wrong before D64:
stubble left behind as a reddish stipple (the mask stopped at a geometric U, short of the beard's
soft edge), a hard rectangle where the relaxation box ended, and a flat, detail-free jaw. They also
pin what must survive: the ears, eyebrows and lips are pasted back byte for byte, the alpha channel
is not touched at all, and the same raster always produces the same bytes.

The numbers are measured on the source raster, so they move with it: the beard box is 73% "dark"
before the shave and ~1% after, and the jaw's high-frequency structure lands at ~0.7 of the clean
cheek's instead of zero. D70 also pins that the clean upper face is not repainted at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_joy_head_mods as bjh  # noqa: E402
import rw_dff as rwd  # noqa: E402

#: the Random4 ped the Arivus pack is built from
ARIVUS_ARCHIVE = ROOT / "references" / bjh.ARIVUS_ARCHIVE
needs_arivus = pytest.mark.skipif(
    not ARIVUS_ARCHIVE.exists(),
    reason=f"{ARIVUS_ARCHIVE.name} is a game asset; see references/README.md",
)

#: the beard, minus the mouth itself: rows below the hairline's centre, columns between the ears
BEARD_BOX = (slice(250, 340), slice(145, 385))
MOUTH_BOX = (slice(250, 296), slice(208, 302))
#: patches used as references for tone and structure: clean cheek, jaw inside the shaved area
CHEEK_PATCH = (slice(196, 216), slice(178, 225))
JAW_PATCH = (slice(255, 330), slice(150, 200))
#: features that must come back untouched: ear centres, eyebrows, the body of the lips
FEATURE_BOXES = {
    "left ear": (slice(205, 220), slice(102, 120)),
    "right ear": (slice(205, 220), slice(411, 429)),
    "left brow": (slice(176, 186), slice(200, 240)),
    "right brow": (slice(176, 186), slice(275, 315)),
    "upper lip and mouth slit": (slice(262, 276), slice(238, 272)),
}
#: the mask's bottom edge (the jaw) and a row well inside the filled area, for the seam check
SEAM_ROW, INTERIOR_ROW = 344, 330
SEAM_COLS = slice(150, 380)
#: clean upper face: what D64/D66's geometric U and wide sideburn boxes used to repaint
UPPER_FACE_BOXES = {
    "left eye": (slice(180, 205), slice(180, 240)),
    "right eye": (slice(180, 205), slice(280, 340)),
    "nose bridge": (slice(205, 230), slice(240, 280)),
    "left cheek": (slice(205, 230), slice(160, 200)),
}


def _lum(cell: np.ndarray) -> np.ndarray:
    return cell[:, :, :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _high_pass_std(cell: np.ndarray, rows: slice, cols: slice) -> float:
    """How much structure a patch carries at the pore/freckle scale."""
    patch = cell[rows, cols, :3].astype(np.float32)
    low = np.stack(
        [
            np.asarray(
                Image.fromarray(patch[:, :, c].astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
            )
            for c in range(3)
        ],
        axis=2,
    )
    return float((patch - low).std())


@pytest.fixture(scope="module")
def head_cell() -> np.ndarray:
    root = bjh.ensure_arivus_extracted(bjh.EXTRACT_DIR / "arivus_extract")
    rasters = {r.name: r for r in rwd.read_txd((root / "Random4.txd").read_bytes())}
    return rasters["head_diff_000_a_whi"].rgba


@pytest.fixture(scope="module")
def shaved(head_cell: np.ndarray) -> np.ndarray:
    return bjh.shave_arivus_face(head_cell)


needs_assets = needs_arivus


@needs_assets
def test_the_ped_really_has_a_painted_beard(head_cell: np.ndarray) -> None:
    """The starting point: most of the beard box is darker than skin before anything runs."""
    skin = float(np.median(_lum(head_cell)[CHEEK_PATCH]))
    dark = float((_lum(head_cell)[BEARD_BOX] < 0.72 * skin).mean())
    assert dark > 0.5, f"only {dark:.0%} of the beard box is dark: the box is not the beard"


@needs_assets
def test_the_beard_is_gone(head_cell: np.ndarray, shaved: np.ndarray) -> None:
    """No stubble is left behind: the beard box comes out as skin, not as a reddish stipple."""
    skin = float(np.median(_lum(head_cell)[CHEEK_PATCH]))
    before = _lum(head_cell)
    after = _lum(shaved)
    # the mouth is protected and keeps its own dark lip and slit
    box = np.zeros(before.shape, dtype=bool)
    box[BEARD_BOX[0], BEARD_BOX[1]] = True
    box[MOUTH_BOX[0], MOUTH_BOX[1]] = False
    before_dark = float((before[box] < 0.72 * skin).mean())
    after_dark = float((after[box] < 0.72 * skin).mean())
    assert before_dark > 0.5
    # D69 keeps the zone's own luminance, so a shaded jaw still dips under 72% of the pale
    # cheek: 73% -> 12% dark, but that 12% is smooth shade, not hair. The strokes are what
    # has to go, so the high-pass energy is the second pin (18.2 -> 7.0 over the whole box).
    assert after_dark < 0.20, f"{after_dark:.1%} of the shaved jaw is still beard-dark"
    assert after_dark < 0.25 * before_dark, f"{after_dark:.1%} dark against {before_dark:.1%} before"
    grain = _high_pass_std(shaved, *BEARD_BOX) / _high_pass_std(head_cell, *BEARD_BOX)
    assert grain < 0.55, f"the beard box still carries {grain:.0%} of its hair strokes"


@needs_assets
@pytest.mark.parametrize("name", sorted(UPPER_FACE_BOXES))
def test_the_clean_upper_face_is_not_repainted(
    name: str, head_cell: np.ndarray, shaved: np.ndarray
) -> None:
    """D70: the inpaint follows the beard, not a rectangle up to the temples.

    The old sideburn boxes reached from y 140 to 344 and 88 px into each cheek; the
    eyes, the bridge of the nose and the upper cheeks came out darker, with a straight
    edge visible in the portrait. Only the beard's soft fringe may touch these boxes.
    """
    rows, cols = UPPER_FACE_BOXES[name]
    before = head_cell[rows, cols, :3].astype(np.int32)
    after = shaved[rows, cols, :3].astype(np.int32)
    changed = float((np.abs(before - after).max(axis=2) > 2).mean())
    assert changed < 0.10, f"{changed:.0%} of the {name} was repainted"


@needs_assets
def test_the_jaw_keeps_skin_structure(shaved: np.ndarray) -> None:
    """The fill is not a flat panel: it carries the pore/freckle grain of the clean skin next door."""
    cheek = _high_pass_std(shaved, *CHEEK_PATCH)
    jaw = _high_pass_std(shaved, *JAW_PATCH)
    assert cheek > 4.0, "the reference patch has no structure to copy"
    assert 0.4 <= jaw / cheek <= 1.4, f"jaw/cheek structure is {jaw / cheek:.2f}"


@needs_assets
def test_the_fill_has_no_hard_edge(shaved: np.ndarray) -> None:
    """Where the inpaint ends, the tone steps no more than it does inside the face."""
    lum = _lum(shaved)
    across = float(np.abs(np.diff(lum[SEAM_ROW - 1:SEAM_ROW + 1, SEAM_COLS], axis=0)).mean())
    inside = float(np.abs(np.diff(lum[INTERIOR_ROW - 1:INTERIOR_ROW + 1, SEAM_COLS], axis=0)).mean())
    assert across <= 2.0 * inside + 1.0, f"seam step {across:.2f} against {inside:.2f} inside"


@needs_assets
@pytest.mark.parametrize("name", sorted(FEATURE_BOXES))
def test_the_face_keeps_its_features(name: str, head_cell: np.ndarray, shaved: np.ndarray) -> None:
    """Ears, eyebrows and lips are pasted back, not repainted."""
    box = FEATURE_BOXES[name]
    before = head_cell[box].astype(np.int32)
    after = shaved[box].astype(np.int32)
    changed = int((np.abs(before - after).max(axis=2) > 0).sum())
    # the feather's outermost pixel can touch a feature's rim; a repaint would move hundreds
    assert changed <= 4, f"{changed} pixels of the {name} changed"


@needs_assets
def test_the_lower_lip_is_not_a_shadow_patch(shaved: np.ndarray, head_cell: np.ndarray) -> None:
    """The chin hairs under the lower lip are gone, and the lip above them is not.

    The ped paints sparse hairs onto the skin below the lower lip; they are darker than 70% of
    skin, which is the line D66 gives back to the mask. The lip itself sits above that line, so
    the two rows under the mouth must come out brighter than they went in, by a lot.
    """
    before = _lum(head_cell)[285:305, 230:285]
    after = _lum(shaved)[285:305, 230:285]
    # 94.3 before, 112.5 after: the hairs and their shadow are skin now. D69 keeps the fill's
    # own luminance instead of flattening it (123.4 there), so the lift is 18, not 29.
    assert float(after.mean()) > float(before.mean()) + 15.0


@needs_assets
def test_the_alpha_and_the_layout_are_untouched(head_cell: np.ndarray, shaved: np.ndarray) -> None:
    """The mask lives in RGB only: the atlas' alpha cutout and the 512x512 layout stay as they were."""
    assert shaved.shape == head_cell.shape == (512, 512, 4)
    assert np.array_equal(shaved[:, :, 3], head_cell[:, :, 3])


@needs_assets
def test_the_shave_is_reproducible(head_cell: np.ndarray, shaved: np.ndarray) -> None:
    """No randomness anywhere: a rebuild produces the same bytes, so the pack's checksum holds."""
    again = bjh.shave_arivus_face(head_cell)
    assert np.array_equal(again, shaved)
