"""Every relative Markdown link in the repository resolves (`tools/pd2-port/check_links.py`).

The two links that were broken sat in the newest archived capture set, one `../` short each: the
evidence for D75 pointed at `docs/renders/pd2-las/DECISIONS.md`, which has never existed. Docs
are the product here, so the check runs in the suite and in `make -sC tools/pd2-las green`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_links", ROOT / "tools" / "pd2-port" / "check_links.py")
check_links = importlib.util.module_from_spec(_spec)
sys.modules["check_links"] = check_links
_spec.loader.exec_module(check_links)


def test_every_repository_link_resolves(capsys):
    assert check_links.main(["--root", str(ROOT), "--quiet"]) == 0, capsys.readouterr().out


def test_a_broken_link_is_reported(tmp_path, capsys):
    (tmp_path / "a.md").write_text("see [the guide](../nowhere/GUIDE.md)\n")
    assert check_links.main(["--root", str(tmp_path), "--quiet"]) == 1
    assert "BROKEN a.md -> ../nowhere/GUIDE.md" in capsys.readouterr().out


def test_links_are_resolved_from_the_linking_file(tmp_path, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text("# t\n")
    (tmp_path / "docs" / "a.md").write_text("[up](../docs/target.md#fragment)\n")
    assert check_links.main(["--root", str(tmp_path), "--quiet"]) == 0


def test_code_spans_and_fences_are_not_links(tmp_path, capsys):
    (tmp_path / "a.md").write_text(
        "Prose about `victim[\"Get Damage\"](...)` and `[..](path)`.\n\n"
        "```c\n// see [x](missing.md)\n```\n")
    assert check_links.main(["--root", str(tmp_path), "--quiet"]) == 0


def test_anchors_schemes_and_templates_are_skipped(tmp_path):
    (tmp_path / "a.md").write_text(
        "[top](#top) [web](https://example.com/x) [mail](mailto:a@b.c) [tpl](<name>.md)\n")
    assert check_links.main(["--root", str(tmp_path), "--quiet"]) == 0
