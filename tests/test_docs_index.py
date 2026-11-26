"""`docs/README.md` is generated and current: it is the only entry point `docs/` has.

`knowledge/` has had `INDEX.md` + `um kb check --index` for a long time. `docs/` grew to 25 guides,
audits and handoffs across three directories without one, so the first question a new agent had —
"which file is the install contract?" — had no answer short of `ls -R`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("gen_docs_index", ROOT / "tools" / "gen_docs_index.py")
gen = importlib.util.module_from_spec(_spec)
sys.modules["gen_docs_index"] = gen
_spec.loader.exec_module(gen)


def test_the_index_is_up_to_date(capsys):
    assert gen.main(["--check"]) == 0, capsys.readouterr().err


def test_every_document_outside_renders_is_listed():
    content = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    missing = [p.relative_to(ROOT / "docs").as_posix() for p in gen.documents()
               if p.relative_to(ROOT / "docs").as_posix() not in content]
    assert not missing, missing


def test_entries_carry_a_heading_not_only_a_filename():
    """A row says what the document is for: its own `# ` heading."""
    content = gen.build()
    assert "| [HANDOFF — where the pd2-las packs stand](pd2-las/HANDOFF.md) | `pd2-las/HANDOFF.md` |" in content


def test_the_render_tree_is_one_entry():
    assert "renders/README.md" in gen.build()
    assert "renders/honoka/in-game" not in gen.build()
