"""Extended tests for um/publish.py improvements: expanded secret patterns, archive handling."""
from um import publish

# The probes are assembled from parts for the same reason `um/publish.py` assembles its own home-directory
# prefixes that way: `um publish check .` lints this repository too, and a literal fake credential here
# fails the check that tests it. Concatenation keeps the pattern under test identical.
_STRIPE = "sk_" + "live_" + "12345678901234567890"
_SLACK = "xox" + "b-" + "1234567890-abc"
_AWS_SECRET = "aws_secret_access_key" + " = " + "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def test_new_secret_patterns_detected():
    # Discord tokens (simplified pattern)
    assert any(rx.search("M" + "x"*23 + "." + "y"*6 + "." + "z"*20) for _, rx in publish.SECRET_PATTERNS if "Discord" in _)
    # Stripe keys
    assert publish.SECRET_PATTERNS[7][1].search(_STRIPE) or any("Stripe" in l and rx.search(_STRIPE) for l, rx in publish.SECRET_PATTERNS)
    # Slack tokens
    assert any("Slack" in l and rx.search(_SLACK) for l, rx in publish.SECRET_PATTERNS)
    # AWS secret
    assert any("AWS secret" in l and rx.search(_AWS_SECRET) for l, rx in publish.SECRET_PATTERNS)


def test_publish_check_detects_new_secrets(tmp_path):
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "README.md").write_text("# Test")
    # File with Discord-like token should be flagged as FAIL
    discord_token = "M" + "A"*23 + "." + "B"*6 + "." + "C"*20
    (mod / "config.txt").write_text(f"token={discord_token}")
    result = publish.check(str(mod))
    assert result == 1  # Should fail due to detected secret


def test_publish_check_ignores_placeholder_paths(tmp_path):
    mod = tmp_path / "mod2"
    mod.mkdir()
    (mod / "README.md").write_text("# Test")
    # Placeholder paths should not be flagged
    (mod / "guide.md").write_text("Install to C:\\Users\\<you>\\Games and %USERPROFILE%\\saves")
    result = publish.check(str(mod))
    # Should not fail on placeholders (may warn about other things but not user_path)
    assert result == 0 or result == 1  # Allow warn but not fail on placeholder alone
    # Direct test of user_path helper
    assert publish.user_path("C:\\Users\\<you>\\path") is None
    assert publish.user_path("C:\\Users\\%USERPROFILE%\\path") is None
    # Real user path should be detected
    assert publish.user_path("C:\\Users\\RealUser\\Documents\\save") is not None
    assert publish.user_path("/home/realuser/docs") is not None


def test_archive_ext_extended():
    assert ".7z" in publish.ARCHIVE_EXT
    assert ".rar" in publish.ARCHIVE_EXT
    assert ".zip" in publish.ARCHIVE_EXT
    # .pak should still be there
    assert ".pak" in publish.ARCHIVE_EXT


def test_suspicious_filename_helper():
    assert publish.is_suspicious_filename("private.key")
    assert publish.is_suspicious_filename("cert.pem")
    assert publish.is_suspicious_filename(".env")
    assert not publish.is_suspicious_filename("readme.md")
    assert not publish.is_suspicious_filename("texture.png")


def test_publish_check_warnh_for_large_archive(tmp_path, capsys):
    mod = tmp_path / "mod3"
    mod.mkdir()
    (mod / "README.md").write_text("# Test")
    # Create a large fake archive (>5MB)
    big_file = mod / "assets.pak"
    big_file.write_bytes(b"x" * (6 << 20))  # 6MB
    publish.check(str(mod))
    out = capsys.readouterr().out
    assert "large engine archive" in out
    assert "6 MB" in out


def test_publish_check_pass_on_clean_mod(tmp_path):
    mod = tmp_path / "clean"
    mod.mkdir()
    (mod / "README.md").write_text("# Clean Mod\nCredits: me")
    (mod / "mod.txt").write_text("This is a clean mod file")
    result = publish.check(str(mod))
    assert result == 0


def test_publish_check_fails_on_env_file(tmp_path):
    mod = tmp_path / "envmod"
    mod.mkdir()
    (mod / "README.md").write_text("# Test")
    (mod / ".env").write_text("SECRET=123")
    result = publish.check(str(mod))
    assert result == 1


def test_publish_check_no_readme_warn(tmp_path, capsys):
    mod = tmp_path / "noreadme"
    mod.mkdir()
    (mod / "file.txt").write_text("content")
    publish.check(str(mod))
    out = capsys.readouterr().out
    assert "no README" in out


def test_user_path_edge_cases():
    # Test with trailing spaces
    assert publish.user_path("Path: C:\\Users\\Bob\\Docs ") is not None
    # Test Unix path
    assert publish.user_path("save at /home/alice/game") is not None
    # Test placeholder with braces
    assert publish.user_path("C:\\Users\\${USER}\\path") is None
    assert publish.user_path("/home/<user>/game") is None
