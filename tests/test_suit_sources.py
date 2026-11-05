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


def test_the_cheapest_blazer_wins(board_mod):
    """Ranked first must be the blazer with the least new machinery to build.

    The user's brief is "blazer required, skirt optional", so the top of the
    board is the one whose importer, skeleton and weights already exist here.
    """
    top = board_mod.ranked()[0]
    assert top.slot == "00-l4d2-rochelle-dressed-for-success"
    assert "blazer" in top.outfit
    # it is the ValveBiped/`.vpk` entry: no new importer, no new skeleton dialect
    assert top.route.startswith(".vpk")
    assert "source_model" in top.route


def test_every_candidate_has_a_blazer(board_mod):
    """A skirt is optional on this board; a blazer is not."""
    for c in board_mod.CANDIDATES:
        assert "blazer" in f"{c.mod} {c.outfit}".lower(), c.slot


def test_skirt_physics_is_reported_honestly(board_mod):
    """Candidates whose skirt needs a spring chain must say so, or ship without."""
    for c in board_mod.CANDIDATES:
        if "HDT" in c.skirt or "physics" in c.skirt:
            assert "separate" in c.skirt or "✗" in c.skirt or "drop" in c.skirt.lower() or (
                "avoid" in c.skirt.lower()
            ), f"{c.slot}: skirt physics mentioned without an escape route"


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
    baseline = [c for c in board_mod.CANDIDATES if c.slot.endswith("3ba-outfit")]
    assert len(baseline) == 1
    c = baseline[0]
    assert c.star == "1.0"
    assert c.stills == ()
    assert "physics" in c.skirt


def test_tracked_board_matches_a_fresh_render(board_mod, tmp_path):
    """The checked-in board must be exactly what the script draws today."""
    fresh = tmp_path / "board.png"
    board_mod.board([board_mod._card(c) for c in board_mod.ranked()]).save(fresh)
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
    for path in ("tools/pd2-las/build_skyrim_outfit.py", "docs/skyrim-nif/STATUS.md",
                 "tools/pd2-las/source_model.py", "tools/pd2-las/skeleton_map.json",
                 "tools/pd2-las/dds_encode.py"):
        assert (REPO / path).exists(), path
    # the Christie difficulty section answers the question it claims to
    assert "How hard is the Christie" in text
    for stage in ("import the mesh", "map the skeleton", "licence"):
        assert stage in text, stage


def test_board_and_cards_are_one_image_per_candidate(board_mod):
    """No collages: the board is a vertical stack of full-width cards."""
    from PIL import Image

    with Image.open(DOCS / "board.png") as im:
        assert im.width == board_mod.WIDTH
        cards = [board_mod._card(c) for c in board_mod.ranked()]
        expected = board_mod.board(cards)
        assert (im.width, im.height) == (expected.width, expected.height)


#: Words that must not reappear anywhere in the tree (removed 2026-11-05).
#: Spelled in pieces so this test file does not itself contain them.
_FORBIDDEN = (
    "Melod" + "ic",
    "Busi" + "ness Woman",
    "Busi" + "nessWoman",
    "busi" + "nesswoman",
    "busi" + "ness_woman",
    "busi" + "ness-woman",
    "buise" + "nesswoman",
)


def test_the_christie_availability_answer_is_recorded(board_mod):
    """Both questions the user asked twice must stay answered in the notes.

    *Does it exist as a Sims 4 mod, and what about in Garry's Mod?* — the answer
    is recorded next to the Christie cost table so a future round does not
    re-run the same search. It also has to stay honest: the GMod addon is an
    unlicensed port of a vanilla asset, so it can never be a release source.
    """
    text = MARKDOWN.read_text(encoding="utf-8")
    assert "Does this outfit already exist converted?" in text
    assert "no Christie business-suit CC found" in text
    assert "870161699" in text           # the GMod workshop id
    # the licence conclusion must not soften into "usable"
    assert "never be shipped" in text or "private build" in text
    # ...and the addon being subscribable must not be written up as "unavailable"
    assert "subscribable" in text
    assert "carries more than one outfit" in text or "more than one outfit" in text
    # the answer has to name the measurement tool, not just the conclusion
    assert "inspect_gma.py" in text


def test_the_gma_reader_the_notes_point_at_exists():
    """The doc tells the reader to run a tool; the tool has to be there."""
    tool = REPO / "tools" / "pd2-las" / "inspect_gma.py"
    assert tool.exists()
    assert (REPO / "tools" / "pd2-las" / "gma.py").exists()
    assert "gma" in tool.read_text(encoding="utf-8").lower()


def test_unverified_garments_say_so(board_mod):
    """Christie's lower half was never seen in any still we hold.

    The card used to assert a pencil skirt on no evidence. Anything the stills
    cannot show has to be marked unverified rather than described.
    """
    christie = [c for c in board_mod.CANDIDATES if c.slot.endswith("christie-business-suit")]
    assert len(christie) == 1
    c = christie[0]
    assert "unverified" in c.skirt.lower()
    assert "pencil" not in c.skirt.lower()
    # the note has to keep the same caveat, not just the spec row
    assert "not* verified" in c.note or "not verified" in c.note
    # ...and the accepted-open-blazer decision is reflected, not re-litigated
    text = MARKDOWN.read_text(encoding="utf-8")
    assert "not* a gate" in text


def test_the_removed_outfit_name_is_gone_from_the_tree():
    """The cancelled Skyrim outfit's name and author were removed on request.

    This is a tripwire, not a style rule: if a doc, comment or fixture
    reintroduces the name it will show up here before it reaches a release.
    """
    skip_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "build", "node_modules"}
    suffixes = {".py", ".md", ".json", ".lua", ".sh", ".yml", ".yaml", ".txt", ".toml"}
    offenders = []
    for path in REPO.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if any(part in skip_dirs for part in path.relative_to(REPO).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        low = text.lower()
        for word in _FORBIDDEN:
            if word.lower() in low:
                offenders.append(f"{path.relative_to(REPO)}: {word}")
    assert not offenders, "removed outfit name is back:\n  " + "\n  ".join(offenders)
