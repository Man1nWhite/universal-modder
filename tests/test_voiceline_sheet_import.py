"""The community voice-line sheet import: preamble, ids, review flags, and slot leads.

`tests/fixtures/regular_vox_head.csv` is the first 25 data rows of the `regular_vox` sheet
(the tab that prompted the importer), status block and all, kept verbatim so the preamble
handling is pinned to the real shape rather than to a tidy one.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "tools"), str(REPO / "tools" / "pd2-las")]

import import_voiceline_sheet as sheet  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "regular_vox_head.csv"


def rows_of(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run(tmp_path: Path, *args: str) -> int:
    return sheet.main(["--sheet", str(FIXTURE), "--out", str(tmp_path), *args])


def test_the_status_block_is_not_data(tmp_path):
    """Rows 1-6 are 99.88% / 20293 complete / ... ; only id | who | what rows are data."""
    assert run(tmp_path, "--tab", "regular_vox") == 0
    rows = rows_of(tmp_path / "regular_vox.csv")
    assert rows and all(r["id"].isdigit() for r in rows)
    assert not [r for r in rows if r["id"] in {"99.88%", "50", "0", "32"}]
    assert rows[0] == {"id": "71550", "who": "Clover",
                       "what": "Woohoo, that Taser just went tits up!",
                       "notes": "", "needs_review": ""}


def test_every_row_survives_in_order(tmp_path):
    """25 data rows in the fixture, ids ascending, none dropped or reordered."""
    run(tmp_path, "--tab", "regular_vox")
    rows = rows_of(tmp_path / "regular_vox.csv")
    assert len(rows) == 25
    ids = [int(r["id"]) for r in rows]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_notes_are_kept_and_the_review_mark_is_carried(tmp_path):
    """A `(?)` in the line is the sheet's own `need review` flag; notes stay as written."""
    run(tmp_path, "--tab", "regular_vox")
    by_id = {r["id"]: r for r in rows_of(tmp_path / "regular_vox.csv")}
    assert by_id["413529"]["notes"] == "control phase"
    assert by_id["1255800"]["notes"] == "Houston callout"
    assert by_id["1808883"]["needs_review"] == "yes"       # "Speaking swedish (?)"
    assert by_id["1808883"]["what"] == "Speaking swedish (?)"


def test_who_keeps_one_speaker_and_names_it_when_missing(tmp_path):
    assert run(tmp_path, "--tab", "regular_vox", "--who", "Hoxton") == 0
    rows = rows_of(tmp_path / "regular_vox_hoxton.csv")
    assert rows and {r["who"] for r in rows} == {"Hoxton"}
    with pytest.raises(SystemExit) as caught:
        run(tmp_path, "--tab", "regular_vox", "--who", "Rust")
    assert "not in the sheet" in str(caught.value)
    assert "Hoxton" in str(caught.value)          # it lists who the tab does name


def test_leads_are_similarity_only_and_land_on_one_slot(tmp_path):
    assert run(tmp_path, "--tab", "regular_vox", "--keys") == 0
    leads = rows_of(tmp_path / "regular_vox_keys.csv")
    assert leads
    assert {r["slot"] for r in leads} <= {r["slot"] for r in sheet.vo.load_cuts()}
    top = {r["slot"]: r for r in leads if r["score"] == "1.00"}
    assert top["move.on_me"]["id"] == "236512"        # "On me"
    assert top["mark.taser"]["id"] == "413529"        # "Taser!"
    assert top["hurt.medic"]["id"] == "986174"        # "I need a medic bag"
    # a line must not be sold to a slot on one shared word
    assert not [r for r in leads if r["id"] == "1880135"]   # the Pager's sentence


def test_a_line_of_small_words_still_scores(tmp_path):
    """"On me." is all stop words; without a fallback it could never match `move.on_me`."""
    assert sheet.f1(sheet.tokens("On me."), sheet.tokens("On me.")) == 1.0
    assert sheet.f1(sheet.tokens("On me"), sheet.tokens("Follow me")) < 0.6


def test_the_importer_never_writes_a_bank_table_or_dist(tmp_path, monkeypatch):
    """The output directory is all it touches: no target table, no `dist/` member."""
    before = {p: p.stat().st_mtime for p in
              (REPO / "voice_lines_vox" / "targets").glob("*.csv")}
    run(tmp_path, "--tab", "regular_vox", "--keys")
    after = {p: p.stat().st_mtime for p in
             (REPO / "voice_lines_vox" / "targets").glob("*.csv")}
    assert before == after
    assert {p.name for p in tmp_path.iterdir()} == {"regular_vox.csv", "regular_vox_keys.csv"}


def test_a_pipe_table_is_read_like_the_export():
    """What a page reader returns: the id column is the unlabeled one before `Who`."""
    table = "\n".join([
        "|     |     |     |     |",
        "| --- | --- | --- | --- |",
        "| Status |  |  |  |",
        "| 99.88% | 20293 | complete |  |",
        "|  | Who | What | Notes |",
        "| 71550 | Clover | Woohoo, that Taser just went tits up! |  |",
        "| 413529 | Wolf | Taser! | control phase |",
    ])
    path = REPO / "tests" / "fixtures" / "_pipe_sheet.csv"
    try:
        path.write_text(table + "\n", encoding="utf-8")
        rows = sheet.normalize(sheet.read_rows(path), "pipe")
    finally:
        path.unlink()
    assert [r["id"] for r in rows] == ["71550", "413529"]
    assert rows[1]["notes"] == "control phase"
    assert rows[1]["who"] == "Wolf"


def test_the_tracked_import_is_what_the_importer_writes(tmp_path):
    """`voice_lines_vox/sheets/` is reproducible: same import command, same bytes."""
    run(tmp_path, "--tab", "regular_vox", "--keys")
    for name in ("regular_vox.csv", "regular_vox_keys.csv"):
        tracked = REPO / "voice_lines_vox" / "sheets" / name
        assert tracked.is_file(), f"missing {name}; re-run make voices_sheets"
        assert tracked.read_bytes() == (tmp_path / name).read_bytes(), name


def test_the_declared_coverage_is_read_from_the_status_block(tmp_path):
    """The status block is the only statement of how big the tab is, so it is parsed, not skipped."""
    rows = sheet.read_rows(FIXTURE)
    assert sheet.declared(rows) == {
        "complete": 20293, "partially complete": 50, "incomplete": 0,
        "need review": 32, "total": 20343,
    }
    out = tmp_path / "o"
    out.mkdir()
    assert sheet.main(["--sheet", str(FIXTURE), "--tab", "t", "--out", str(out)]) == 0


def test_incompleteness_is_reported_and_can_fail_a_gate(tmp_path, capsys):
    """A 25-row file of a 20,343-row tab must say so out loud, and `--require-full` must refuse.

    This is the guard against the mistake that matters here: calling a head a full import.
    """
    out = tmp_path / "o"
    out.mkdir()
    assert sheet.main(["--sheet", str(FIXTURE), "--tab", "t", "--out", str(out)]) == 0
    said = capsys.readouterr().out
    assert "INCOMPLETE" in said and "25 of 20343" in said

    assert sheet.main(["--sheet", str(FIXTURE), "--tab", "t", "--out", str(out),
                       "--require-full"]) == 2


def test_a_full_import_reports_full(tmp_path, capsys):
    """A file holding exactly what the tab declares is accepted by `--require-full`."""
    path = tmp_path / "tiny.csv"
    path.write_text(
        "Status,,,,\n100.00%,2,complete,,,\n,0,partially complete,,,\n,0,incomplete,,,\n"
        ",0,\"need review, marked with (?)\",,\n,Who,What,Notes,\n"
        "1,Clover,Oi,,,\n2,Dallas,Over here,,,\n", encoding="utf-8")
    out = tmp_path / "o"
    out.mkdir()
    assert sheet.main(["--sheet", str(path), "--tab", "tiny", "--out", str(out),
                       "--require-full"]) == 0
    assert "FULL: 2 of 2" in capsys.readouterr().out
