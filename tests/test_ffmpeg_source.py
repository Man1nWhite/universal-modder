"""`um win shot`/`record` build an ffmpeg gfxcapture filtergraph from user input.

`window_title` and `window_exe` were interpolated raw, so a perfectly legal game title
(`PAYDAY 2: Crimewar`, `Warhammer 40,000`) broke the graph — and `foo,boxblur=...` was filter
injection. The value must be backslash-escaped for the filtergraph level, and hwnd/crop must be
integers.
"""
from __future__ import annotations

import hashlib
import io

import pytest

from um import win


@pytest.mark.parametrize("value, expected", [
    ("PAYDAY 2: Crimewar", r"PAYDAY 2\: Crimewar"),
    ("Warhammer 40,000", r"Warhammer 40\,000"),
    ("it's a game", r"it\'s a game"),
    ("back\\slash", r"back\\slash"),
    ("semi;colon", r"semi\;colon"),
    ("brackets[0]", r"brackets\[0\]"),
    ("plain-name_2.0.exe", "plain-name_2.0.exe"),
])
def test_filter_value_escapes_the_structural_characters(value, expected):
    assert win._ff_filter_value(value) == expected


def test_source_passes_a_colon_in_the_title_as_one_option():
    src = win._source(title="PAYDAY 2: Crimewar")
    assert src.startswith(r"gfxcapture=window_title=PAYDAY 2\: Crimewar:capture_cursor=0")
    # one option: exactly one unescaped colon between window_title= and the next option
    assert "PAYDAY 2\\: Crimewar:capture_cursor" in src


def test_source_accepts_a_regex_window_exe():
    src = win._source(exe="AoE2DE_s")
    assert "window_exe=AoE2DE_s.exe:" in src
    src = win._source(exe="aoe2de.*\\.exe")
    # the backslash in the regex reaches the filtergraph doubled (it is the escape character)
    assert "window_exe=" + win._ff_filter_value("aoe2de.*\\.exe") + ":" in src


def test_source_appends_exe_extension_once():
    assert "window_exe=foo.exe:" in win._source(exe="foo")
    assert "window_exe=foo.exe:" in win._source(exe="foo.exe")


def test_source_hwnd_must_be_an_integer():
    assert win._source(hwnd=123456).startswith("gfxcapture=hwnd=123456:")
    with pytest.raises(SystemExit):
        win._source(hwnd="1;select=1:default=1")   # not an int -> die, not a filtergraph


def test_source_crop_must_be_four_integers():
    src = win._source(exe="foo", crop=[0, 10, 200, 100])
    assert ":crop_left=0:crop_top=10:crop_right=200:crop_bottom=100," in src
    with pytest.raises(SystemExit):
        win._source(exe="foo", crop=["0", "10", "x", "100"])


def test_source_requires_exactly_one_selector():
    with pytest.raises(SystemExit):
        win._source()


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_ffmpeg_setup_download_verifies_the_checksum(monkeypatch, tmp_path):
    payload = b"a fake ffmpeg build"
    want = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(win, "FFMPEG_SUMS", "https://example.invalid/checksums.sha256")
    monkeypatch.setattr(win, "FFMPEG_URL", "https://example.invalid/ffmpeg.zip")
    monkeypatch.setattr(win, "ffmpeg_sha256", lambda: want)

    def fake_urlopen(url, timeout=None):
        assert timeout and timeout > 0          # no hanging forever on a stalled connection
        return _FakeResponse(payload)

    monkeypatch.setattr(win.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "ffmpeg.zip"
    win.download_ffmpeg(out)
    assert out.read_bytes() == payload


def test_ffmpeg_setup_download_deletes_a_bad_archive(monkeypatch, tmp_path):
    payload = b"tampered bytes"
    monkeypatch.setattr(win, "FFMPEG_SUMS", "https://example.invalid/checksums.sha256")
    monkeypatch.setattr(win, "FFMPEG_URL", "https://example.invalid/ffmpeg.zip")
    monkeypatch.setattr(win, "ffmpeg_sha256", lambda: "0" * 64)
    monkeypatch.setattr(win.urllib.request, "urlopen", lambda url, timeout=None: _FakeResponse(payload))
    out = tmp_path / "ffmpeg.zip"
    with pytest.raises(SystemExit):
        win.download_ffmpeg(out)
    assert not out.exists()


def test_ffmpeg_sha256_reads_the_published_sum(monkeypatch):
    name = win.FFMPEG_URL.rsplit("/", 1)[1]
    body = f"{'a' * 64}  {name}\n{'b' * 64}  other-file.zip\n".encode()
    monkeypatch.setattr(win.urllib.request, "urlopen", lambda url, timeout=None: _FakeResponse(body))
    assert win.ffmpeg_sha256() == "a" * 64


def test_ffmpeg_sha256_honours_the_env_pin(monkeypatch):
    monkeypatch.delenv("UM_FFMPEG_SHA256", raising=False)
    monkeypatch.setenv("UM_FFMPEG_SHA256", "  " + "C" * 64 + "  ")
    assert win.ffmpeg_sha256() == "c" * 64


def test_ffmpeg_sha256_dies_when_the_build_is_missing_from_the_sums(monkeypatch):
    monkeypatch.delenv("UM_FFMPEG_SHA256", raising=False)
    monkeypatch.setattr(win.urllib.request, "urlopen", lambda url, timeout=None: _FakeResponse(b"c" * 64 + b"  other.zip\n"))
    with pytest.raises(SystemExit):
        win.ffmpeg_sha256()
