#!/usr/bin/env python3
"""Read-only audit of `docs/pd2-las/DECISIONS.md`: the record's structure, not its prose.

`tests/test_decisions_index.py` pins what this prints. Run it after appending an entry:

    python tools/check_decisions_index.py

It checks five things a 2,000-line append-only record loses quietly:

* **one number, one entry.** Two entries sharing a number make every citation ambiguous — that is
  how `D74` came to mean both "game-derived exports may be committed" and "the Geralt re-key".
* **no gaps.** A number that no entry holds means a reference to it goes nowhere.
* **appended entries sit in a topic section**, at the same heading level as their siblings. The
  sections are thematic, so numbers jump *between* sections by design; inside one section they must
  only ever go up, because that is the order they were appended in.
* **fields.** Each entry states `Decision` and `Status`; `Decided` is required from D53 on (the
  earlier entries were reconstructed before the date was recorded). Only the presence is checked:
  the other labels are narrative by design (`Why 4 cm.`, `Held to`, `What was wrong in game`).
* **citations.** Every `D<n>` named from a document, a test or a tool resolves to exactly one entry.
  A comment is skipped, and so is a hex digest that happens to contain `D74`.

Exit status is 1 when any check fails, so a gate can call it directly.
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "docs/pd2-las/DECISIONS.md"
#: documents, tests and tools that cite entries; `DECISIONS.md` itself is the record
CITERS = ("docs", "tools", "tests", "voice_lines_vox", "knowledge", "AGENTS.md", "README.md",
          "CONTRIBUTING.md")
#: the numbers that never existed: reserved or dropped in the 2026-11-11 reconstruction
DOCUMENTED_GAPS = {11, 12, 18}
ALWAYS = ("Decision", "Status")
#: required from this entry on; older entries were reconstructed without a date
DECIDED_FROM = 53
#: labels the record uses; not enforced (the narrative labels are prose by design), kept as a
#: reference for anyone rewriting an entry
KNOWN = ("Decided", "Decision", "Why", "Context", "Measured, not asserted", "Not this", "Held to",
         "Not measured", "Rejected", "Source", "Status", "Superseded", "Renumbered", "Read",
         "Found", "Amended the same day, from the render", "What was wrong in game",
         "What was wrong", "What blocks a full re-key", "What the limits are not",
         "What files the game accepts show", "The two hooks are opposites and must never both ship",
         "The Hila override is a replacement, not a LAS pack",
         "Two exceptions that were written down, and are gone",
         "Two ways to make them agree, and why this one",
         "Why they were there, measured on the source raster",
         "Why the eye is drawn once and averaged", "Why 4 cm", "Why 4 cm was too much, measured",
         "Why the eye is drawn once", "Lashes",
         "Findings that change what can be claimed")

ENTRY = re.compile(r"^(#{2,3}) D(\d+)\b(.*)$")
SECTION = re.compile(r"^## (?!D\d)(.+)$")
FIELD = re.compile(r"^- \*\*([^*]+?)\*\*")
#: `D<n>` inside prose or a comment; not inside a hex digest or an identifier
CITE = re.compile(r"(?<![A-Za-z0-9])D(\d{1,2})(?![0-9A-Za-z])")


def entries() -> list[dict]:
    """Each entry: its number, heading level, line and the field labels it carries."""
    found: list[dict] = []
    current: dict | None = None
    for number, line in enumerate(DECISIONS.read_text(encoding="utf-8").splitlines(), 1):
        match = ENTRY.match(line)
        if match:
            current = {"num": int(match.group(2)), "level": len(match.group(1)),
                       "line": number, "head": line, "fields": []}
            found.append(current)
        elif SECTION.match(line):
            current = None                      # a topic heading ends the previous entry
        elif current is not None:
            field = FIELD.match(line)
            if field:
                current["fields"].append(field.group(1).strip())
    return found


def sections(found: list[dict]) -> list[dict]:
    """Topic sections, each with the entries that follow it, in file order."""
    lines = DECISIONS.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for number, line in enumerate(lines, 1):
        match = SECTION.match(line)
        if match:
            out.append({"name": match.group(1).strip(), "line": number, "entries": []})
        elif out and ENTRY.match(line):
            out[-1]["entries"].append(int(ENTRY.match(line).group(2)))
    return out


def _citable(text: str) -> str:
    """The text minus comments, digests and hex byte runs, so only real citations remain."""
    text = re.sub(r"#[^\n]*", "", text)                 # a Python comment
    text = re.sub(r"\b[0-9A-Fa-f]{8,}\b", "", text)     # a digest
    # `FA 11 D0` / `0x45ECD0`: a byte pair written like a citation is not one
    text = re.sub(r"\b(?:[0-9A-Fa-f]{2} )+[0-9A-Fa-f]{2}\b", "", text)
    text = re.sub(r"\b0x[0-9A-Fa-f]+\b", "", text)
    return text


def audit() -> list[str]:
    found = entries()
    problems: list[str] = []
    by_number = collections.Counter(entry["num"] for entry in found)

    for number, count in sorted(by_number.items()):
        if count > 1:
            where = ", ".join(str(e["line"]) for e in found if e["num"] == number)
            problems.append(f"D{number} is defined {count} times (lines {where})")

    numbers = sorted(by_number)
    gaps = sorted(set(range(1, numbers[-1] + 1)) - set(numbers) - DOCUMENTED_GAPS)
    if gaps:
        problems.append("no entry holds " + ", ".join(f"D{n}" for n in gaps))

    for section in sections(found):
        previous = 0
        for number in section["entries"]:
            if number < previous:
                problems.append(f"D{number} sits after D{previous} inside "
                                f"\"{section['name']}\"")
            previous = max(previous, number)

    levels = collections.Counter(entry["level"] for entry in found)
    majority = levels.most_common(1)[0][0]
    for entry in found:
        if entry["level"] != majority:
            problems.append(f"D{entry['num']} (line {entry['line']}) is `{'#' * entry['level']}`; "
                            f"its siblings are `{'#' * majority}`")
        if not any(entry["num"] in section["entries"] for section in sections(found)):
            problems.append(f"D{entry['num']} (line {entry['line']}) is outside every topic section")

    for entry in found:
        required = ALWAYS + (("Decided",) if entry["num"] >= DECIDED_FROM else ())
        missing = [field for field in required
                   if not any(f.startswith(field) for f in entry["fields"])]
        if missing:
            problems.append(f"D{entry['num']} (line {entry['line']}) lacks "
                            + ", ".join(f"**{field}**" for field in missing))


    for path in _citers():
        text = _citable(path.read_text(encoding="utf-8", errors="replace"))
        for match in CITE.finditer(text):
            number = int(match.group(1))
            if number and number not in by_number:
                problems.append(f"{path.relative_to(ROOT).as_posix()} cites D{number}, which no "
                                f"entry defines")
    return problems


def _citers() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for name in CITERS:
        target = ROOT / name
        if target.is_file():
            out.append(target)
        elif target.is_dir():
            out.extend(path for path in target.rglob("*")
                       if path.suffix in (".md", ".py") and ".venv" not in path.parts)
    # the audit's own test names the gaps it forbids; that is not a citation
    return [path for path in out if path != DECISIONS
            and path.name != "test_decisions_index.py"]


def main() -> int:
    found = entries()
    sections_ = sections(found)
    print(f"{len(found)} entries, D{min(e['num'] for e in found)}-D{max(e['num'] for e in found)}, "
          f"in {len(sections_)} sections:")
    for section in sections_:
        print(f"  {section['name']}: {len(section['entries'])} entries "
              f"(D{min(section['entries'])}-D{max(section['entries'])})" if section["entries"]
              else f"  {section['name']}: 0 entries")
    problems = audit()
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nOK: numbers unique and gapless, one heading level, every entry in a section, "
          "fields present, every citation resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
