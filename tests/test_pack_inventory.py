"""One inventory contract: status.pack_names() is the source of tracked pack names."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "tools" / "pd2-las"), str(REPO / "tests")]

import fresh  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from status import LAS_TARGETS, pack_names  # noqa: E402
from test_pd2_las_invariants import ITEMS  # noqa: E402


def test_every_pack_inventory_agrees_with_status_pack_names():
    names = set(pack_names())
    tracked_zips = fresh.tracked_zips()
    assert len(names) == len(tracked_zips)
    assert {Path(path).stem for path in tracked_zips} == names

    outputs = fresh.build_plan("", tracked_zips)
    assert {Path(path).stem for paths in outputs.values() for path in paths} == names

    # The invariant suite keys internal asset folders, not public ZIP names.
    internal_to_public = {
        "Miranda_LAS": "Miranda_L4D2_LAS",
        "Miranda_Busty_LAS": "Miranda_L4D2_Busty_LAS",
        **{name: name for name in ITEMS if name not in {"Miranda_LAS", "Miranda_Busty_LAS"}},
    }
    expected_las = set(LAS_TARGETS) - {"Miranda_Romance_LAS"}
    assert set(internal_to_public.values()) == expected_las
    assert set(internal_to_public.values()) <= names

    folders = {dist_path(REPO, f"{name}.zip").parent.name for name in names}
    actual_folders = {path.name for path in (REPO / "dist").iterdir() if path.is_dir()}
    assert actual_folders == folders
