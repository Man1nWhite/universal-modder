"""`tools/pd2-las/packs.py` is the table; every other view of the packs must agree with it.

A pack used to be named in six places: `dist_paths._GROUPS` (its folder), `status.TARGETS`
(its make target), `fresh.BUILDERS` (its builder), `tools/tasks.py`, the `Makefile` and the
test literals. Adding or retiring one meant six edits, and a missed one failed only in the
view nobody ran that day. Now the table is edited once and these tests fail wherever a view
still disagrees.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PD2 = ROOT / "tools" / "pd2-las"
sys.path.insert(0, str(PD2))
sys.path.insert(0, str(ROOT / "tools"))

import packs  # noqa: E402
import status  # noqa: E402
import dist_paths  # noqa: E402


def test_the_table_matches_the_tree():
    """One `.zip` per pack in its folder, and nothing else in `dist/`."""
    on_disk = {path.stem: path.parent.name for path in (ROOT / "dist").rglob("*.zip")}
    assert on_disk == packs.GROUPS, (
        "dist/ and tools/pd2-las/packs.py disagree:\n"
        f"  only on disk: {sorted(set(on_disk.items()) - set(packs.GROUPS.items()))}\n"
        f"  only in the table: {sorted(set(packs.GROUPS.items()) - set(on_disk.items()))}"
    )


def test_every_pack_has_a_sidecar():
    missing = sorted(pack.name for pack in packs.PACKS.values()
                     if not (ROOT / pack.rel).with_suffix(".zip.sha256").is_file())
    assert not missing, f"packs without a .sha256 beside them: {missing}"


def test_dist_path_agrees_with_the_table():
    wrong = [(pack.name, dist_paths.dist_path(ROOT, f"{pack.name}.zip").relative_to(ROOT).as_posix(), pack.rel)
             for pack in packs.PACKS.values()
             if dist_paths.dist_path(ROOT, f"{pack.name}.zip") != ROOT / pack.rel]
    assert not wrong, f"dist_paths puts a pack in another folder: {wrong}"


def test_status_targets_are_the_table():
    assert status.TARGETS == packs.TARGETS
    for name, make in packs.TARGETS.items():
        assert status.target(name) == make, name


def test_the_makefile_builds_every_target_in_the_table():
    text = (PD2 / "Makefile").read_text(encoding="utf-8")
    rules = set(re.findall(r"^([a-z_]+):(?!=)", text, flags=re.M))
    missing = sorted(set(packs.TARGETS.values()) - rules)
    assert not missing, f"packs.py names make targets the Makefile does not define: {missing}"
    for make, argv in packs.builders().items():
        # the rules spell the builder as $(HERE)/<name>, so match the file name
        assert Path(argv[0]).name in text, f"{make}: the Makefile never runs its builder {argv[0]}"


def test_tasks_runs_the_builder_the_table_names():
    sys.path.insert(0, str(ROOT / "tools"))
    import tasks  # noqa: E402

    for make, argv in packs.builders().items():
        assert make in tasks.TASKS, f"tools/tasks.py has no {make!r} target"
        command = tasks.TASKS[make][0]
        assert command[:1] == ["{py}"], f"{make}: tasks.py must run the pinned interpreter"
        assert tuple(command[1:]) == argv, f"{make}: tasks.py runs {command[1:]}, the table says {argv}"


def test_fresh_rebuilds_every_builder_the_table_names():
    import fresh  # noqa: E402

    by_argv = {argv: make for make, argv in packs.builders().items()}
    for name, argv in fresh.BUILDERS.items():
        assert tuple(argv) in by_argv, (
            f"fresh.py builds {name!r} with {tuple(argv)}, which is not a builder in packs.py"
        )
        make = by_argv[tuple(argv)]
        assert name == packs.FRESH_NAMES.get(make, make), (
            f"fresh.py calls {name!r} what packs.py calls {packs.FRESH_NAMES.get(make, make)!r}"
        )


def test_every_pack_is_reachable_from_one_builder():
    for pack in packs.PACKS.values():
        assert pack.make in packs.builders(), pack.name
        assert pack.builder[0].endswith(".py"), pack.name
        assert pack.what and len(pack.what) > 10, pack.name


def test_a_builder_cannot_claim_two_argument_lists():
    with pytest.raises(SystemExit):
        original = dict(packs.PACKS)
        try:
            packs.PACKS["Probe"] = packs.Pack("Probe", "Miranda", "heads", ("other.py",), "a pack that is not real")
            packs.builders()
        finally:
            packs.PACKS.clear()
            packs.PACKS.update(original)
