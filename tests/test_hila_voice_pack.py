"""The keying contract of the Hila VO pack: slot -> PD2 bark event name -> `main.xml`.

The builder asserts these while it runs, but nothing in the suite did, so the pack that
shipped keyed on numeric voice-line ids (`712675`) — correct file names for the `.stream`
route, meaningless to `SoundManager:CheckSoundID` — passed every check. These tests read the
tracked CSVs and the emitted XML without ffmpeg or py7zr, and fail on that regression.
"""
from __future__ import annotations

import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_hila_voice_mod as vo  # noqa: E402

DIR = ROOT / "voice_lines_vox" / "miranda_lawson"
#: a Wwise event name: lowercase, no spaces, may carry a `_sin`/`_plu`/`_any` suffix
EVENT_NAME = re.compile(r"[a-z][a-z0-9_]*")
NAME_ADDRESS = re.compile(r"\b(shepard|commander|commando)\b", re.I)


def _rows(name):
    with (DIR / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_every_slot_cut_by_the_builder_is_answered_and_nothing_is_answered_twice():
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


def test_every_slot_has_a_curated_pick_and_that_pick_names_no_rank():
    """A pick is what the builder plays; the fallback heuristic is not allowed to decide."""
    picks = {r["slot"]: r for r in _rows("slot_picks.csv")}
    cuts = {r["slot"] for r in _rows("hila_intent_cuts.csv")}
    assert cuts == set(picks), sorted(cuts ^ set(picks))
    for slot, row in picks.items():
        # `note` may quote the name that was trimmed; only what is heard has to be clean
        for column in ("cut_line", "clip_text"):
            assert not NAME_ADDRESS.search(row.get(column) or ""), (slot, column)


def test_main_xml_keys_on_the_posted_event_with_the_hila_prefix():
    events = vo.load_events()
    slot_file = {slot: f"clip{idx:03d}.ogg" for idx, slot in enumerate(sorted(events))}
    root = ET.fromstring(vo.build_xml(slot_file, events))

    sounds = root.find("Sounds")
    assert sounds is not None
    assert sounds.get("prefix") == "rb21", "b21 is Hila's robber switch; without it other heisters lose lines"
    assert sounds.get("directory") == "sounds"

    entries = sounds.findall("sound")
    # the builder walks slots in order, so compare as a multiset: one entry per posted event
    assert sorted(e.get("id") for e in entries) == sorted(
        ev for evs in events.values() for ev in evs
    ), "one <sound> per posted event name"
    for entry in entries:
        assert entry.get("stop_id") == entry.get("id") + "_stop"
        assert entry.get("path") in slot_file.values()


def test_build_xml_refuses_a_slot_the_game_would_never_answer():
    with pytest.raises(SystemExit, match="slot without a PD2 event id"):
        vo.build_xml({"ammo.low": "a.ogg", "hurt.generic": "b.ogg"}, {"ammo.low": ["g81x_plu"]})


def test_build_xml_refuses_two_slots_fighting_over_one_event():
    with pytest.raises(SystemExit, match="claimed by both"):
        vo.build_xml({"a": "a.ogg", "b": "b.ogg"}, {"a": ["g18"], "b": ["g18"]})
