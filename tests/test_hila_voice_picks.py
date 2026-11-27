"""The contract of the voice picks, and the one pack that ships them (D61).

The clip table is route-independent: `hila_intent_cuts.csv` says which Hila slot
answers which intent, `slot_picks.csv` says which Miranda ogg and which window
answers each slot, and both routes read it. These tests read those CSVs without
ffmpeg or py7zr and fail on the regressions that got through before: a slot with
no pick, a pick whose text carries the name that was supposed to be cut out, and -
since the BeardLib `SoundsModule` pack was dropped on 2026-11-25 (D61) - a
`dist/Hila` that grows a second package back, or a build target that would.

The event-name table (`slot_event_ids.csv`) stays: it records which PD2 bark each
slot stands for, which is how "does this line make sense here" is written down.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import hila_voice_clips as vo  # noqa: E402
from dist_paths import dist_path  # noqa: E402

DIR = ROOT / "voice_lines_vox" / "miranda_lawson"
#: a Wwise event name: lowercase, no spaces, may carry a `_sin`/`_plu`/`_any` suffix
EVENT_NAME = re.compile(r"[a-z][a-z0-9_]*")
NAME_ADDRESS = re.compile(r"\b(shepard|commander|commando)\b", re.I)
STREAM = "Miranda_Lawson_VO_over_Hila_Stream"
BEARDLIB = "Miranda_Lawson_VO_over_Hila"


def _rows(name):
    with (DIR / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_every_slot_in_the_cut_table_is_answered_by_an_event_and_nothing_is_answered_twice():
    cuts = {r["slot"] for r in _rows("hila_intent_cuts.csv")}
    events = {r["slot"] for r in _rows("slot_event_ids.csv")}
    assert cuts and cuts == events, (sorted(cuts - events), sorted(events - cuts))


def test_the_event_table_has_one_row_per_slot():
    slots = [r["slot"] for r in _rows("slot_event_ids.csv")]
    assert len(slots) == len(set(slots)), "a slot appears twice; the later row would win"


def test_an_event_name_is_claimed_by_one_slot_only():
    seen = {}
    for slot, ids in vo.load_events().items():
        for ev in ids:
            assert ev not in seen, f"{ev} claimed by {seen[ev]} and {slot}"
            seen[ev] = slot
    assert seen


def test_event_ids_are_wwise_event_names_not_voice_line_ids():
    """The shipped bug: `<sound id="712675">` never matches, because PD2 posts `g18`."""
    hila_ids = {r["hila_id"] for r in _rows("hila_intent_cuts.csv")}
    ids = [ev for evs in vo.load_events().values() for ev in evs]
    assert ids
    assert [ev for ev in ids if not EVENT_NAME.fullmatch(ev)] == []
    assert [ev for ev in ids if ev.isdigit()] == [], "numeric ids are .stream file names"
    assert [ev for ev in ids if ev in hila_ids] == []


def test_every_slot_has_a_curated_pick_or_is_removed_and_neither_names_a_rank():
    """A pick is what both routes play; the fallback heuristic is not allowed to decide.

    Slots whose best clip scored below semantic fit 8 with no take in either source
    archive are removed in `removed_slots.csv`: those ids are left vanilla on
    purpose, so they must not come back as picks, and the table records what they
    used to play.
    """
    picks = {r["slot"]: r for r in _rows("slot_picks.csv")}
    removed = {r["slot"]: r for r in _rows("removed_slots.csv")}
    cuts = {r["slot"] for r in _rows("hila_intent_cuts.csv")}
    assert cuts == set(picks) | set(removed), sorted(cuts ^ (set(picks) | set(removed)))
    assert not (set(picks) & set(removed)), "a slot is both picked and removed"
    # `note` may quote the name that was trimmed; only what is heard has to be clean
    for slot, row in picks.items():
        for column in ("cut_line", "clip_text"):
            assert not NAME_ADDRESS.search(row.get(column) or ""), (slot, column)
    for slot, row in removed.items():
        assert row["reason"], slot
        for column in ("cut_line", "old_clip_text"):
            assert not NAME_ADDRESS.search(row.get(column) or ""), (slot, column)


def test_a_pick_window_is_a_positive_window_inside_its_source():
    """A pick is either one window, or `splits` phrases spliced in that order.

    A spliced pick leaves `t_start`/`t_end` at 0: the window is the span its splits
    cover, which is what the builders cut. Both forms have to be a real, short window.
    """
    for row in _rows("slot_picks.csv"):
        ranges = vo.parse_splits(row.get("splits") or "")
        if ranges:
            assert len(ranges) > 1, row["slot"]
            assert all(0.0 <= a < b for a, b in ranges), row["slot"]
            assert ranges == sorted(ranges), row["slot"]
            start, end = ranges[0][0], ranges[-1][1]
            heard = sum(b - a for a, b in ranges)
        else:
            start, end = float(row["t_start"]), float(row["t_end"])
            assert 0.0 <= start < end, row["slot"]
            heard = end - start
        assert 0.0 <= start < end, row["slot"]
        assert heard < 6.0, row["slot"]


def test_only_the_stream_pack_ships():
    """D61: the BeardLib `SoundsModule` pack is gone, and nothing builds it back."""
    beardlib = dist_path(ROOT, f"{BEARDLIB}.zip")
    assert not beardlib.exists(), f"{beardlib.name} is back in dist/"
    assert not beardlib.with_suffix(".zip.sha256").exists()

    makefile = (ROOT / "tools" / "pd2-las" / "Makefile").read_text(encoding="utf-8")
    assert "build_hila_voice_mod.py" not in makefile
    assert f"dist/Hila/{BEARDLIB}" not in makefile
    fresh = (ROOT / "tools" / "pd2-las" / "fresh.py").read_text(encoding="utf-8")
    assert "build_hila_voice_mod.py" not in fresh
    # and the builder that wrote it is gone rather than merely unused
    assert not (ROOT / "tools" / "build_hila_voice_mod.py").exists()


def test_the_stream_pack_carries_its_own_map():
    path = dist_path(ROOT, f"{STREAM}.zip")
    if not path.is_file():
        pytest.skip("dist/ is absent from this sandbox snapshot")
    import zipfile

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    assert any(n.endswith("hila_stream_map.csv") for n in names), names[:5]
    streams = [n for n in names if n.endswith(".stream")]
    assert len(streams) > 600, len(streams)


def test_the_tracked_pieces_manifest_is_what_the_picks_say():
    """`hila_slot_pieces.csv` is the build record; it must be the picks, rebuilt.

    Nothing ships it any more (D61), which is exactly why it has to be checkable:
    it is the only line-by-line record of which source window each slot is cut from.
    """
    import io

    if not vo.ARCHIVE.is_file():
        pytest.skip("references/voice/Голос Лоусон.7z is absent from this sandbox snapshot")
    pytest.importorskip("py7zr", reason="the picks are resolved against the archive listing")
    oggs = vo.list_archive_oggs() + vo.list_mira_files()
    rows = vo.manifest_rows(vo.load_cuts(), vo.load_picks(), oggs, vo.load_splits())
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    with (DIR / "hila_slot_pieces.csv").open(newline="", encoding="utf-8") as f:
        tracked = f.read()
    assert buf.getvalue() == tracked, "hila_slot_pieces.csv is stale: run tools/hila_voice_clips.py"
