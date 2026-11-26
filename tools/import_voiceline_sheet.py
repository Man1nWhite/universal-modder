#!/usr/bin/env python3
"""Import a community voice-line sheet into a tracked `id -> who -> what` table.

The sheets people keep for PAYDAY 2 (`regular_vox`, per-heister tabs, …) are the only public
place where a *numeric stream id* is paired with the *spoken text*. Wwise keeps no name for a
streamed file, so a sheet like this is what turns "1,046 measured ids" into "these ids say these
words" — the input `voice_lines_vox/geralt/char_rust_ids.csv` waits for (D76).

What it does, in one pass:

* **reads a Google export as it comes.** `File -> Download -> CSV` from the sheet, or the same CSV
  from `.../export?format=csv&gid=<id>` when this machine can reach it. The pipe-table form
  (`| id | who | what | notes |`) that a page reader returns is accepted too.
  **A tab is selected by `gid`, never by name:** `&gid=<number>` from the tab's URL works, while
  `&sheet=<name>` falls back to the first tab whatever the name is.
* **skips the sheet's preamble.** The `regular_vox` sheet starts with a status block
  (`99.88% | 20293 | complete`, …, `Who | What | Notes`); the data header is the `Who`/`What` row and
  the id column is the unlabeled one before it.
* **normalizes one file per tab**: `id,who,what,notes,needs_review`, ids as digits.
* **derives leads** (`--keys`): for each row whose text reads like one of the repo's intent slots
  (`voice_lines_vox/miranda_lawson/hila_intent_cuts.csv`), writes `slot,id,score,what`. A lead is a
  similarity, **not** a verified id → slot mapping; nothing in `dist/` is built from a lead.

    python tools/import_voiceline_sheet.py --sheet references/regular_vox.csv --tab regular_vox
    python tools/import_voiceline_sheet.py --sheet references/regular_vox.csv --who Rust
    python tools/import_voiceline_sheet.py --sheet references/regular_vox.csv --keys --who Rust

Outputs land in `voice_lines_vox/sheets/`: `<tab>.csv` (whole tab), `<tab>_<who>.csv` (one
speaker), `<tab>_<who>_keys.csv` (the leads). The tool never writes into `dist/` and never into a
bank table: a lead has to be checked against the line before it becomes a mapping.

**Which bank a sheet covers is the sheet's own title.** `regular_vox` is the shared bank that the
original crew stream from; a dedicated bank (`char_rust`, `char_sydney`, …) needs its own tab or
extraction. Importing the `regular_vox` sheet says nothing about `char_rust` ids, even for the same
heister.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import hila_voice_clips as vo  # noqa: E402  (the repository's slot -> `cut_line` table)

OUT = ROOT / "voice_lines_vox" / "sheets"
HEADER = ["id", "who", "what", "notes", "needs_review"]
#: words too common to say two lines are about the same thing
STOP = {"the", "a", "an", "to", "of", "and", "you", "your", "me", "my", "is", "it", "in", "on",
        "for", "that", "this", "with", "get", "got", "now", "up", "go", "we", "i", "im", "s",
        "are", "be", "he", "she", "they", "them", "him", "her", "at", "as", "so", "do", "dont"}


def read_rows(path: Path) -> list[list[str]]:
    """Rows of the sheet, from a CSV export or from a pipe table. Blank and short rows dropped."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if text.lstrip().startswith("|"):
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip().strip("\\").strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue                                  # the markdown separator
            rows.append(cells)
        return rows
    return [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]


def data_start(rows: list[list[str]]) -> int:
    """Index of the first data row: the row after the `Who | What` header of the sheet."""
    for i, row in enumerate(rows):
        cells = [c.strip().lower() for c in row]
        if "who" in cells and "what" in cells:
            return i + 1
    raise SystemExit("no `Who`/`What` header row: is this the right export? "
                     "(File -> Download -> CSV, not the browser page)")


def declared(rows: list[list[str]]) -> dict[str, int]:
    """The sheet's own coverage block, e.g. `{"complete": 20293, "incomplete": 2407, "total": ...}`.

    Rows 2-5 of the tab read `<pct> | <n> | complete | partially complete | incomplete | need
    review`. They are the only statement of how big the tab is, and therefore the only way to say
    whether an import is the whole tab. A block that is absent (an older export) yields `{}`.
    """
    out: dict[str, int] = {}
    for row in rows[:data_start(rows)]:
        cells = [c.strip() for c in row]
        for i, cell in enumerate(cells):
            label = cell.lower()
            if label.startswith(("complete", "partially", "incomplete", "need review")):
                for prev in reversed(cells[:i]):
                    if prev.replace(",", "").isdigit():
                        out[label.split(",")[0]] = int(prev.replace(",", ""))
                        break
                break
    if out:
        out["total"] = out.get("complete", 0) + out.get("partially complete", 0) \
            + out.get("incomplete", 0)
    return out


def normalize(rows: list[list[str]], tab: str) -> list[dict]:
    """id / who / what / notes per data row; a non-numeric id is kept and flagged."""
    out = []
    for row in rows[data_start(rows):]:
        cells = list(row)
        while cells and not cells[0].strip():
            cells.pop(0)                                  # the unlabeled id column, in a pipe table
        while cells and not cells[-1].strip():
            cells.pop()
        cells = (cells + ["", "", "", ""])[:4]
        raw_id, who, what, notes = (c.strip() for c in cells)
        if not raw_id and not what:
            continue
        clean = raw_id.rstrip("?").strip()
        # the sheet marks "listener, check this one" with a `(?)` on the line; carry it through
        unsure = not clean.isdigit() or raw_id.endswith("?") or "(?)" in what
        out.append({
            "id": clean if clean.isdigit() else raw_id,
            "who": who,
            "what": what,
            "notes": notes,
            "needs_review": "yes" if unsure else "",
        })
    if not out:
        raise SystemExit(f"{tab}: no data rows after the header")
    return out


def tokens(text: str) -> set[str]:
    """Content words of a line; a line made only of small words keeps them ("On me.")."""
    words = {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 1}
    return {w for w in words if len(w) > 2 and w not in STOP} or words


def f1(got: set[str], want: set[str]) -> float:
    """Word overlap that penalizes a long line as well as a short one.

    Dividing by the slot's line alone scores "I need a medic bag" as a perfect `downed.need_help`
    (it shares "need"); the harmonic mean of both directions does not, because most of what the
    line says is not part of the slot.
    """
    if not got or not want:
        return 0.0
    both = len(got & want)
    if not both:
        return 0.0
    precision, recall = both / len(got), both / len(want)
    return 2 * precision * recall / (precision + recall)


def key_leads(rows: list[dict], threshold: float = 0.6) -> list[dict]:
    """slot leads: rows whose text reads like a slot's canonical line. A lead, never a mapping."""
    slots = {r["slot"]: tokens(r["cut_line"]) for r in vo.load_cuts() if r.get("slot")}
    leads = []
    for row in rows:
        got = tokens(row["what"])
        if not got:
            continue
        best, best_slot = 0.0, ""
        for slot, want in slots.items():
            score = f1(got, want)
            if score > best:
                best, best_slot = score, slot
        if best_slot and best >= threshold:
            leads.append({"slot": best_slot, "id": row["id"], "score": f"{best:.2f}",
                          "what": row["what"], "who": row["who"]})
    return sorted(leads, key=lambda r: (r["slot"], -float(r["score"]), r["id"]))


def write(path: Path, rows: list[dict], fields: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sheet", type=Path, required=True,
                    help="the exported CSV of one tab (File -> Download -> CSV), or a pipe table")
    ap.add_argument("--tab", default=None,
                    help="tab name for the output file (default: the sheet's own title if the "
                         "export names one, else the file stem)")
    ap.add_argument("--who", default=None,
                    help="keep one speaker only, e.g. Rust (case-insensitive)")
    ap.add_argument("--keys", action="store_true",
                    help="also write the slot leads this tab's text supports")
    ap.add_argument("--require-full", action="store_true",
                    help="exit 2 unless the file holds every row the tab declares (for gates)")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"where the CSVs go (default: {OUT.relative_to(ROOT).as_posix()})")
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="word overlap a lead needs against a slot's line (default 0.6)")
    args = ap.parse_args(argv)
    out_dir = args.out if args.out else OUT
    tab = (args.tab or args.sheet.stem).replace(" ", "_")
    rows = normalize(read_rows(args.sheet), tab)
    if args.who:
        wanted = args.who.strip().lower()
        rows = [r for r in rows if r["who"].strip().lower() == wanted]
        if not rows:
            who = sorted({r["who"] for r in normalize(read_rows(args.sheet), tab)})
            raise SystemExit(f"--who {args.who!r} is not in the sheet; it names: " + ", ".join(who))
    reviewed = sum(1 for r in rows if r["needs_review"])
    suffix = f"_{args.who.strip().lower()}" if args.who else ""
    path = write(out_dir / f"{tab}{suffix}.csv", rows, HEADER)
    dupes = len(rows) - len({r["id"] for r in rows})
    print(f"{path}: {len(rows)} rows"
          + (f", {dupes} duplicate id(s) kept as they are" if dupes else "")
          + (f", {reviewed} row(s) need review" if reviewed else ""))
    coverage = declared(read_rows(args.sheet))
    if coverage:
        total = coverage.get("total", 0)
        have = len(rows) if not args.who else 0
        print(f"tab declares {total} rows: {coverage.get('complete', 0)} complete, "
              f"{coverage.get('partially complete', 0)} partial, "
              f"{coverage.get('incomplete', 0)} incomplete, "
              f"{coverage.get('need review', 0)} to review")
        if total and have and have < total:
            print(f"INCOMPLETE: this file holds {have} of {total} rows "
                  f"({have / total:.1%}) - the rest needs the sheet's own CSV export")
        elif total and have >= total:
            print(f"FULL: {have} of {total} rows")
        else:
            print("speaker slice: coverage is reported for the whole tab by the unfiltered import")
        if args.require_full and have < total:
            return 2
    if args.keys:
        leads = key_leads(rows, args.threshold)
        kpath = write(out_dir / f"{tab}{suffix}_keys.csv", leads,
                      ["slot", "id", "score", "what", "who"])
        print(f"{kpath}: {len(leads)} slot leads "
              f"(similarity only - check each line before it becomes a mapping)")
    print("the bank this covers is the tab's own: `regular_vox` says nothing about char_rust ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
