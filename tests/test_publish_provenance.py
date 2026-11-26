"""A warning that always fires is a warning nobody reads.

`um publish check .` on this repository printed 34 warnings: 32 large archives under
`references/` that `references/README.md` names in full, and two absolute user paths in test
fixtures (`/home/<user>/…`) that exist to exercise the rule being warned about. The check now
treats a mentioned archive as provenance-recorded and skips the user-path rule in test files, so
a clean tree prints PASS and a new warning means something.
"""
from __future__ import annotations

from um import publish


def make_mod(tmp_path, readme: str = "# Mod\n") -> "object":
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "README.md").write_text(readme)
    return mod


def big(mod, name: str):
    path = mod / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * (6 << 20))
    return path


def test_a_large_archive_the_readme_names_is_not_a_warning(tmp_path, capsys):
    mod = make_mod(tmp_path, "# Mod\n\nSource: assets.pak comes from the retail install, named here.\n")
    big(mod, "assets.pak")
    assert publish.check(str(mod)) == 0
    out = capsys.readouterr().out
    assert "large engine archive" not in out
    assert out.startswith("PASS:")


def test_a_large_archive_nothing_names_is_still_a_warning(tmp_path, capsys):
    mod = make_mod(tmp_path, "# Mod\n\nNo provenance here.\n")
    big(mod, "assets.pak")
    assert publish.check(str(mod)) == 0        # a warning, not a failure
    assert "large engine archive (6 MB)" in capsys.readouterr().out


def test_provenance_may_live_in_a_credits_file(tmp_path, capsys):
    mod = make_mod(tmp_path)
    big(mod, "big.pak")
    (mod / "CREDITS.md").write_text("big.pak comes from the game's data folder")
    publish.check(str(mod))
    assert "large engine archive" not in capsys.readouterr().out


def test_a_nested_readme_counts_too(tmp_path, capsys):
    mod = make_mod(tmp_path)
    big(mod, "references/source.pak")
    (mod / "references" / "README.md").write_text("`source.pak` is the user's own extract")
    publish.check(str(mod))
    assert "large engine archive" not in capsys.readouterr().out


def test_absolute_user_paths_are_skipped_in_test_fixtures(tmp_path, capsys):
    mod = make_mod(tmp_path)
    (mod / "tests").mkdir()
    (mod / "tests" / "test_saves.py").write_text("SAVES = 'C:\\Users\\RealUser\\Documents'\n")
    publish.check(str(mod))
    assert "absolute user path" not in capsys.readouterr().out


def test_absolute_user_paths_are_still_reported_in_real_sources(tmp_path, capsys):
    mod = make_mod(tmp_path)
    (mod / "src").mkdir()
    (mod / "src" / "mod.lua").write_text("local dir = 'C:\\Users\\RealUser\\Documents'\n")
    publish.check(str(mod))
    assert "absolute user path in src/mod.lua" in capsys.readouterr().out


def test_is_test_path():
    assert publish.is_test_path("tests/test_publish_extended.py")
    assert publish.is_test_path("t/mod_test.py")
    assert publish.is_test_path("fixtures/save.ini")
    assert not publish.is_test_path("src/main.lua")
    assert not publish.is_test_path("README.md")
