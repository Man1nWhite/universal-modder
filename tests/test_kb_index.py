"""The machine index is checked and regenerated alongside its Markdown counterpart."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("index", ["index.json", "INDEX.md"])
def test_check_index_rejects_a_missing_or_stale_index(tmp_path, index):
    root = tmp_path / "knowledge"
    folder = root / "techniques"
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text(
        "---\nkind: technique\ntitle: Café notes\ntags: [testing]\ndate: 2026-01-01\n"
        "agents: [test agent]\n---\nA test note.\n", encoding="utf-8",
    )

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "um", "kb", *args, "--root", str(root)],
                              cwd=REPO, capture_output=True, text=True, encoding="utf-8")

    assert cli("index").returncode == 0
    assert cli("check", "--index").returncode == 0
    rows = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert [row["title"] for row in rows] == ["Café notes"]
    counterpart = root / ("INDEX.md" if index == "index.json" else "index.json")
    original = counterpart.read_bytes()
    stale = root / index
    stale.write_text("[]\n")
    failed = cli("check", "--index")
    assert failed.returncode == 1 and stale.name in failed.stdout
    stale.unlink()
    failed = cli("check", "--index")
    assert failed.returncode == 1 and stale.name in failed.stdout
    assert counterpart.read_bytes() == original
    assert cli("index").returncode == 0
    assert cli("check", "--index").returncode == 0
