"""The per-character stream tables: slot -> bank -> id, and the bank module each target uses.

A VO pack replaces a line by writing the file the game streams, so the only two things that
decide whether a line is replaced are *the bank folder* the heister streams from and *the
numeric id* of the line. `tools/build_stream_tables.py` writes both to
`voice_lines_vox/targets/`; these tests keep them equal to the cut table and the picks, so a table
cannot drift into a second, stale copy of the keying.

The two facts these tests also pin, because both were inferred rather than read anywhere:

* a heister's *shared* bank is `regular_vox` and nothing else — a pack writing it replaces the
  line for everyone on the bank, which is why the three packs are alternatives;
* a *dedicated* bank folder is `char_<module>` — `char_rust` for Rust, whose `robber` switch is
  `rb16`, and no documented folder at all for Old Hoxton (his packs are shared-bank packs).

All of it reads tracked CSVs: no ffmpeg, no archives, no game install.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_stream_tables as tables  # noqa: E402
import build_hila_stream_mod as hila  # noqa: E402

TARGETS = ROOT / "voice_lines_vox" / "targets"


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _shared(target: str) -> list[dict]:
    return _rows(TARGETS / f"{target.replace('-', '_')}_shared_{tables.SHARED}.csv")


def _picks(rel: str) -> set[str]:
    with (ROOT / rel).open(newline="", encoding="utf-8") as f:
        return {r["slot"] for r in csv.DictReader(f) if r.get("slot")}


def test_every_target_has_a_shared_table_with_the_shared_ids():
    """One row per shared `regular_vox` id, and the id set is the Hila cut table's, nothing else."""
    expected = [hila_id for hila_id, _slot, _also in hila.load_ids()]
    for target in tables.TARGETS:
        rows = _shared(target)
        assert [r["id"] for r in rows] == expected, target
        assert {r["bank"] for r in rows} == {"regular_vox"}, target
        assert {r["slot"] for r in rows} <= {slot for _i, slot, _a in hila.load_ids()}


def test_the_written_column_is_the_picks_coverage_minus_the_vorbis_ids():
    """`written=yes` is exactly the non-Vorbis ids whose slot the picks name.

    The two packs that wrote these tables were retired and deleted from `dist/` on 2026-11-28
    (D88), so the coverage is pinned against the pick tables instead of a zip that no longer
    exists — the tables stay as the record of what the packs carried.
    """
    vorbis = set(hila.load_vorbis_ids())
    for target, cfg in tables.TARGETS.items():
        rows = _shared(target)
        picks = _picks(cfg["picks"])
        written = {r["id"] for r in rows if r["written"] == "yes"}
        assert not written & vorbis, f"{target} claims to write a Vorbis id"
        expected = {r["id"] for r in rows if r["slot"] in picks and r["id"] not in vorbis}
        assert written == expected, target


def test_a_slot_without_a_pick_is_vanilla_and_says_so():
    """The shared table may not invent coverage: every `no` row is a vorbis id or an unpicked slot."""
    vorbis = set(hila.load_vorbis_ids())
    for target, cfg in tables.TARGETS.items():
        picks = _picks(cfg["picks"])
        for row in _shared(target):
            if row["written"] == "no":
                assert row["id"] in vorbis or row["slot"] not in picks, row
                assert row["note"], row
            else:
                assert row["slot"] in picks and row["id"] not in vorbis, row


def test_the_bank_module_is_not_the_voice_switch():
    """`char_rust` and `rb16` name different things: a folder and a Wwise switch.

    The ModWorkshop wiki lists the switch values (`rust` = `rb16`, `Hoxton` = `rb5`); the bank
    dump lists the folders (`char_rust` exists, `char_hoxton` does not). A builder that swaps
    one for the other writes a folder the game does not read — the silent failure of D61 —
    so the module name may never be derived from the `rb` value.
    """
    assert tables.TARGETS["rust"]["bank"] == "char_rust"
    assert tables.TARGETS["rust"]["voice"] == "rb16"
    assert tables.TARGETS["old-hoxton"]["bank"] == "char_hoxton"
    assert "char_" + tables.TARGETS["rust"]["voice"] not in tables.TARGETS["rust"]["bank"]


def test_a_dedicated_table_is_measured_not_generated():
    """A dedicated bank's ids cannot be derived, so a table only exists with a reference pack.

    The one tracked is `char_rust`, measured in `references/voice/Marine VO for Rust.7z.001` — the ids
    of Rust's own bank, which share nothing with the shared `regular_vox` ids: that 0 is the
    measurement that keeps the two banks from being confused for one another.
    """
    paths = sorted(TARGETS.glob("*_dedicated_*.csv"))
    assert paths, "the measured char_rust table is tracked"
    shared = {r["id"] for r in _shared("rust")}
    for path in paths:
        rows = _rows(path)
        assert rows and all(r["id"].isdigit() for r in rows), path
        assert {r["bank"] for r in rows} == {"char_rust"}, path
        assert not {r["id"] for r in rows} & shared, f"{path.name} reuses a shared-bank id"
        assert all(r["slot"] == "" for r in rows), "a measured id has no slot until a source names it"


def test_the_workbook_names_the_tables_and_the_open_question():
    """The source of truth an agent reads before a Rust/Hoxton VO build names the tables and the gap.

    docs/pd2-voice-stream-tables.md was replaced by the VO workbook (voice_lines_vox/vo_master.xlsx,
    rebuilt by tools/build_vo_master.py); the per-tab CSVs in voice_lines_vox/vo_master/ are its
    tracked mirror. This keeps the same contract: tables named, the open bank question stated.
    """
    base = ROOT / "voice_lines_vox" / "vo_master"
    sources = (base / "SOURCES.csv").read_text(encoding="utf-8")
    fmt = (base / "format.csv").read_text(encoding="utf-8")
    readme = (base / "README.csv").read_text(encoding="utf-8")
    both = sources + fmt + readme
    for target, cfg in tables.TARGETS.items():
        name = f"{target.replace('-', '_')}_shared_{tables.SHARED}.csv"
        assert name in sources, target
        assert cfg["bank"] in both, target
        assert cfg["voice"] in both, target
    assert "open" in readme.lower() and "regular_vox" in readme
