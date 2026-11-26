"""`docs/pd2-las/DECISIONS.md` stays a record: one number per entry, in a section, cited by id.

The record is append-only and its numbers are cited from documents, tests and tools, so its
structure is a contract rather than a style. It broke twice before this test existed:

* **one number, twice.** The re-key entry was written as `D74` on top of the day's other `D74`
  (game-derived exports), so `(D74)` meant two things and a reader following a citation landed in
  the wrong decision.
* **appended outside the sections.** D67-D76 were appended after the last section, at `##` in a
  file where every other entry is `###`, so the table of contents lost them.

`tools/check_decisions_index.py` prints the numbers and checks the same rules; this runs it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import check_decisions_index as record  # noqa: E402


def test_the_record_is_structurally_sound():
    """Unique, gapless numbers; one heading level; every entry inside a section."""
    assert record.audit() == [], "\n".join(record.audit())


def test_every_citation_resolves_to_one_entry():
    """A `D<n>` in a doc, a test or a tool must name exactly one decision."""
    numbers = {entry["num"] for entry in record.entries()}
    cited = set()
    for path in record._citers():
        text = record._citable(path.read_text(encoding="utf-8", errors="replace"))
        cited |= {int(m.group(1)) for m in record.CITE.finditer(text)}
    dangling = sorted(cited - numbers)
    assert not dangling, f"cited, never defined: {', '.join(f'D{n}' for n in dangling)}"


def test_the_numbers_documented_as_never_used_stay_unused():
    """D11, D12 and D18 never existed; a renumbering must not quietly resurrect them."""
    numbers = {entry["num"] for entry in record.entries()}
    assert numbers & record.DOCUMENTED_GAPS == set()
    # the gaps are named here, so this file is excluded from the audit's citations
    assert numbers == set(range(1, max(numbers) + 1)) - record.DOCUMENTED_GAPS


def test_the_index_links_reach_every_entry():
    """Every entry has an index link, and every link lands on a heading GitHub will render."""
    text = (REPO / "docs" / "pd2-las" / "DECISIONS.md").read_text(encoding="utf-8")

    def slug(heading: str) -> str:
        return re.sub(r"[^\w\- ]", "", heading.lower(), flags=re.UNICODE).replace(" ", "-")

    headings = {slug(h) for h in re.findall(r"^### (.+)$", text, flags=re.M)}
    links = re.findall(r"\]\(#([^)]+)\)", text)
    assert len(links) == len(record.entries()), "the index does not link every entry once"
    assert [link for link in links if link not in headings] == [], "an index link has no heading"


def test_the_record_says_how_it_is_organised():
    """The reader has to know that sections are subject-based and numbers are identity."""
    header = (REPO / "docs" / "pd2-las" / "DECISIONS.md").read_text(encoding="utf-8")[:4000]
    assert "**Index.**" in header
    assert "never reuse one" in header


def test_the_check_runs_on_its_own():
    """A failing record must fail a gate, not just print: exit 1 is the contract."""
    done = subprocess.run([sys.executable, str(REPO / "tools" / "check_decisions_index.py")],
                          capture_output=True, text=True, cwd=REPO)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "OK:" in done.stdout
