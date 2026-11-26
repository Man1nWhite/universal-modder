"""Shared test setup: the import paths, and the fixtures whose absence used to look like a bug.

Two problems are fixed here, both of them a fresh clone's first five minutes:

* Every test file prepended `tools/` and `tools/pd2-las/` to `sys.path` itself, in its own
  order. That is one `sys.path[:0] = [...]` per file to keep in sync; `pytest` imports this
  module before collecting, so one line here does the same job for all of them.

* The 2B reference templates (`references/2b.rar`, unpacked to `build/pd2-las/2b/`) are
  gitignored build inputs. Without them, `pytest tests` reported four *failures* with
  `FileNotFoundError: .../2b.model` and one *error* per test that imported py7zr — which reads
  like a broken checkout rather than "run `make -sC tools/pd2-las env`". Now the suite tries the
  documented extraction once and, if it still cannot, skips the tests that read the templates
  with `tools/pd2-las/extract_2b.MISSING` as the reason — the wording the skip budget already
  knows (`tools/pd2-port/check_skip_budget.py`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PD2_LAS = TOOLS / "pd2-las"

#: Tests import `um`, `dds_encode`, `extract_2b`, `test_gma` and friends directly.
for _path in (ROOT, TOOLS, PD2_LAS, ROOT / "tests"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def _extract_2b():
    """The documented extractor, imported lazily: stdlib only, and absent outside a clone."""
    import extract_2b  # tools/pd2-las is on sys.path above

    return extract_2b


def _templates_missing() -> str | None:
    """None when every template is there, else the reason to skip with."""
    try:
        extract_2b = _extract_2b()
    except Exception:  # noqa: BLE001 - any import problem means "the fixture is not available"
        return "2B templates not extracted (tools/pd2-las/extract_2b.py could not be imported)"
    if extract_2b.present():
        return None
    return extract_2b.MISSING


def pytest_collection_modifyitems(config, items):
    """Skip the tests that read the templates, once, with the command that fixes it."""
    reason = _templates_missing()
    if reason is None:
        return
    # Try the extraction the repository documents (`make -sC tools/pd2-las env` runs this).
    # It is idempotent and cached by SHA-256, and it needs `node`: if either is absent the
    # reason below still names the fix, so nothing is lost by trying.
    try:
        _extract_2b().main()
    except (Exception, SystemExit):  # noqa: BLE001 - a failed bootstrap is the skip, not an error
        pass
    if (reason := _templates_missing()) is None:
        return
    for item in items:
        module = getattr(item, "module", None)
        # The modules that read the templates import TEMPLATES from extract_2b at module level.
        if module is not None and (hasattr(module, "TEMPLATES") or hasattr(module, "TEMPLATE_FILES")):
            item.add_marker(pytest.mark.skip(reason=reason))
