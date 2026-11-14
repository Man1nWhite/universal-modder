"""The skip budget judges a report: every reason a test skips for is named and counted.

`tools/pd2-port/check_all.py --full` (`make -sC tools/pd2-las green`) used to run the suite twice,
once for its verdict and once more inside `check_skip_budget.py`: two minutes of seven. It now hands
the budget the report of the one run. These tests hold the judging of a report to what the tool's own
run decides, on the cases that matter: a reason with no budget, growth over a budget, an expected
failure nobody named, and the one file the budget leaves out.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "pd2-port" / "check_skip_budget.py"

#: what `pytest -q -rsxX tests` prints at its end, with every kind of line the budget reads
REPORT = """\
=========================== short test summary info ============================
SKIPPED [2] tests/test_gma.py:31: sourcepp is an optional extra
SKIPPED [1] tests/test_um.py:900: needs ffmpeg
SKIPPED [13] tests/test_render_mesh_skeleton.py:39: Christie base pack not built (run make -sC tools/pd2-las christie)
800 passed, 16 skipped in 120.00s
"""


def _budget():
    spec = importlib.util.spec_from_file_location("check_skip_budget", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_report_within_the_budget_passes_and_the_left_out_file_is_left_out():
    budget = _budget()
    said, failures = budget.judge(REPORT)
    assert failures == [], failures
    assert said[-1].strip() == (f"OK: 3 budgeted skip(s) across {len(budget.ALLOWED)} reason(s), "
                                "0 expected failure(s) within budget."), said[-1]
    # the tool's own run passes --ignore for this file; in a report of the whole suite its lines are dropped
    assert budget.IGNORED == ("tests/test_render_mesh_skeleton.py",)


def test_what_has_no_budget_fails():
    """The reason below is real. On 2026-11-13 a test skipped with it while a pack was rebuilt and not
    committed, and `green` would have failed in the one state where `status` names it as the next command."""
    budget = _budget()
    reason = "Christie_LAS_Slim is not the tracked zip in this checkout"
    _, failures = budget.judge(REPORT + f"SKIPPED [1] tests/test_pd2_las_status.py:114: {reason}\n")
    assert failures == [f"unbudgeted skip reason: {reason!r} (1x)"]

    _, failures = budget.judge(REPORT.replace("SKIPPED [2] tests/test_gma.py", "SKIPPED [3] tests/test_gma.py"))
    assert failures == ["skip reason over budget: 'sourcepp is an optional extra' (3x, budget 2x)"]

    _, failures = budget.judge(REPORT + "XFAIL tests/test_um.py::test_anything - somebody wanted it out of the way\n")
    assert failures == ["unbudgeted expected failure (xfail): tests/test_um.py::test_anything (1x)"]

    _, failures = budget.judge(REPORT + "SKIPPED [4] tests/test_pd2_las.py:20: 2B templates not extracted: run make env\n")
    assert failures == ["skip reason over budget: '2B templates not extracted' (4x, budget 0x)"]


def test_no_budget_is_kept_for_a_reason_nothing_skips_with():
    """A budget outlives its tests quietly. Until 2026-11-13 four reasons had room for 21 tests that waited
    for the archives and the pack of a cancelled outfit; none of them had run since the archives went."""
    budget = _budget()
    said = "".join(path.read_text(encoding="utf-8") for path in sorted((REPO / "tests").glob("*.py"))
                   if path.name != Path(__file__).name)
    said += (REPO / "tools" / "pd2-las" / "extract_2b.py").read_text(encoding="utf-8")      # MISSING, the 2B reason
    stale = [reason for reason in budget.ALLOWED if reason not in said]
    assert not stale, f"check_skip_budget.ALLOWED has a budget for a reason no test skips with: {stale}"
    gone = [node for node in budget.ALLOWED_XFAIL if not (REPO / node.split("::")[0]).is_file()
            or node.split("::")[1] not in (REPO / node.split("::")[0]).read_text(encoding="utf-8")]
    assert not gone, f"check_skip_budget.ALLOWED_XFAIL names a test that is not there: {gone}"


def test_a_saved_report_is_judged_without_running_the_suite(tmp_path, capsys):
    budget = _budget()
    budget.run_suite = lambda: (_ for _ in ()).throw(AssertionError("--report must not start the suite"))
    saved = tmp_path / "report.txt"
    saved.write_text(REPORT)
    assert budget.main(["--report", str(saved)]) == 0
    assert "OK: 3 budgeted skip(s)" in capsys.readouterr().out
    saved.write_text(REPORT + "SKIPPED [1] tests/test_x.py:1: a reason nobody budgeted\n")
    assert budget.main(["--report", str(saved)]) == 1
    assert "unbudgeted skip reason: 'a reason nobody budgeted' (1x)" in capsys.readouterr().out


def test_green_runs_the_suite_once():
    source = (REPO / "tools" / "pd2-port" / "check_all.py").read_text()
    assert source.count('"-m", "pytest"') == 1, "check_all.py starts the suite more than once"
    assert '"check_skip_budget.py"), "--report", str(report)]' in source, "the skip budget no longer reads the suite's report"
