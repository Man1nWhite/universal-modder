"""The office-suit source board must stay honest and regenerable.

`tools/pd2-las/suit_source_board.py` is a *recon* artifact: it ranks candidate
games to borrow an office-suit body from, and every claim on it goes into
`docs/pd2-las/SUIT-SOURCES.md` where a human will read it. Two failure modes are
worth a test:

1. the checked-in board drifts from the script that supposedly made it;
2. a claim slips in that is not measured (a "verdict" with no cited still, a
   candidate whose still is missing from the repo).

The heavy generation lives in `main()`; these tests call the composition helpers
directly and compare against the tracked PNG, so they are fast and offline.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "pd2-las" / "suit_source_board.py"
DOCS = REPO / "docs" / "pd2-las" / "suit-sources"
MARKDOWN = REPO / "docs" / "pd2-las" / "SUIT-SOURCES.md"


def _load():
    spec = importlib.util.spec_from_file_location("suit_source_board", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def board_mod():
    return _load()


def test_branded_suit_is_the_top_candidate(board_mod):
    """The ranked order must put the full suit (blazer + skirt) first."""
    ranked = sorted(board_mod.CANDIDATES, key=lambda c: (-float(c.star), c.slot))
    assert ranked[0].slot == "01-re4r-ada-agent-officewear"
    assert "blazer" in ranked[0].outfit and "skirt" in ranked[0].outfit


def test_every_claim_has_a_source(board_mod):
    """No candidate may cite a still that isn't in the repo, or a bare URL-less note."""
    for c in board_mod.CANDIDATES:
        assert c.url, f"{c.slot}: no source url"
        for still in c.stills:
            assert board_mod._find_still(still).exists(), f"{c.slot}: missing {still}"
        if c.stills:
            assert board_mod._find_still(board_mod._hero(c)).exists(), c.slot


def test_failed_skyrim_source_is_kept_as_the_baseline(board_mod):
    """The cancelled 3BA attempt stays on the board, ranked last, with no still."""
    baseline = [c for c in board_mod.CANDIDATES if c.slot.endswith("3ba-business-woman")]
    assert len(baseline) == 1
    c = baseline[0]
    assert c.star == "1.0"
    assert c.stills == ()
    assert "physics" in c.skirt


def test_tracked_board_matches_a_fresh_render(board_mod, tmp_path):
    """The checked-in board must be exactly what the script draws today."""
    fresh = tmp_path / "board.png"
    board_mod.board([board_mod._card(c) for c in board_mod.CANDIDATES]).save(fresh)
    tracked = DOCS / "board.png"
    assert tracked.exists(), "missing docs/pd2-las/suit-sources/board.png"
    assert fresh.read_bytes() == tracked.read_bytes(), (
        "board.png is stale — re-run tools/pd2-las/suit_source_board.py"
    )
    # only the board ships; per-card sheets would just duplicate its pixels
    assert sorted(p.name for p in DOCS.glob("*.png")) == ["board.png"]


def test_markdown_is_generated_from_the_same_candidates(board_mod):
    """Every candidate must appear in the notes, with its url, once."""
    text = MARKDOWN.read_text(encoding="utf-8")
    assert "do not hand-edit" in text.lower()
    for c in board_mod.CANDIDATES:
        assert c.mod in text, c.slot
        assert c.url in text, c.slot
    # the pipeline commands quoted must actually exist in this repo
    for path in ("tools/pd2-las/build_business_woman.py", "docs/skyrim-nif/FIXES-2026-11-04.md"):
        assert (REPO / path).exists(), path


def test_board_and_cards_are_one_image_per_candidate(board_mod):
    """No collages: the board is a vertical stack of full-width cards."""
    from PIL import Image

    with Image.open(DOCS / "board.png") as im:
        assert im.width == board_mod.WIDTH
        cards = [board_mod._card(c) for c in board_mod.CANDIDATES]
        expected = board_mod.board(cards)
        assert (im.width, im.height) == (expected.width, expected.height)
