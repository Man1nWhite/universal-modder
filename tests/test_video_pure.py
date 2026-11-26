"""The parts of `um/video.py` that do not need ffmpeg: timing, colours, filter strings, cards.

`um/video.py` was the least-covered module in the package (19% of its lines) because every test of
it that existed needed ffmpeg, so on a machine without it none ran. The timing helpers, the colour
parser, the ffmpeg filter builder and the Pillow card renderers are pure and decide the things
that are easy to get wrong: an EDL's seconds, the crop arithmetic, and whether a card's text fits.
"""
from __future__ import annotations

import json

import pytest

from um import video

Image = pytest.importorskip("PIL.Image", reason="the card renderers need pillow")


# --------------------------------------------------------------------------- timing


def test_frange_includes_both_ends_and_rounds():
    assert list(video.frange(0, 1, 0.5)) == [0.0, 0.5, 1.0]
    assert list(video.frange(0, 0.3, 0.1)) == [0.0, 0.1, 0.2, 0.3]
    assert list(video.frange(2, 2, 1)) == [2.0]
    assert list(video.frange(0, -1, 1)) == []


def test_segment_seconds_come_from_dur_or_from_beats():
    assert video._seg_dur({"dur": 3.5}, 120) == 3.5
    assert video._seg_dur({"beats": 4}, 120) == 2.0     # four beats at 120 bpm
    assert video._seg_dur({}, None) == 4.0              # the documented default


def test_beats_without_a_bpm_is_an_error_not_a_silent_four_seconds():
    with pytest.raises(SystemExit):
        video._seg_dur({"beats": 4}, None)


# --------------------------------------------------------------------------- colours and filters


@pytest.mark.parametrize("value, rgb", [
    ("#FFFFFF", (255, 255, 255, 255)),     # six digits: opaque
    ("FF8800", (255, 136, 0, 255)),
    ("#00000000", (0, 0, 0, 0)),           # eight digits: the alpha is explicit
    ("#11223344", (17, 34, 51, 68)),
])
def test_rgba_parses_six_and_eight_digit_hex(value, rgb):
    assert video._rgba(value) == rgb


def test_rgba_defaults_to_white():
    assert video._rgba(None) == (255, 255, 255, 255)
    assert video._rgba("") == (255, 255, 255, 255)


def test_crop_fill_scales_up_and_crops_to_the_frame():
    f = video._fill_filter("crop", 1920, 1080)
    assert f.startswith("scale=1920:1080:force_original_aspect_ratio=increase")
    assert f.endswith("crop=1920:1080")


def test_pad_fill_letterboxes_on_black():
    f = video._fill_filter("pad", 1080, 1920)
    assert "force_original_aspect_ratio=decrease" in f
    assert "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" in f


def test_blur_fill_splits_the_source_in_two():
    f = video._fill_filter("blur", 1920, 1080)
    assert f.startswith("split[fa][fb]")
    assert "boxblur" in f and "overlay=(W-w)/2:(H-h)/2" in f


def test_a_crop_argument_is_applied_before_the_scale():
    f = video._fill_filter("crop", 100, 50, crop=(10, 20, 200, 100))
    assert f.startswith("crop=200:100:10:20,scale=100:50")


def test_zoom_is_appended_as_a_scale_then_crop():
    f = video._fill_filter("crop", 640, 360, zoom=1.25)
    assert f.endswith(",scale=iw*1.25:ih*1.25,crop=640:360")


# --------------------------------------------------------------------------- cards


def test_the_tracked_fonts_are_present():
    """The card renderers load these by path; a wheel must carry them (pyproject: packages = um)."""
    for path in (video.TITLE_FONT, video.BODY_FONT, video.MONO_FONT):
        assert path.is_file(), path


def test_title_chip_draws_on_a_frame_of_the_asked_size(tmp_path):
    out = tmp_path / "chip.png"
    video.title_chip("A title", "@credit", 640, 360, {"accent": "#FF8800"}, out)
    with Image.open(out) as im:
        assert im.size == (640, 360)
        assert im.getbbox() is not None        # something was drawn


def test_hook_text_wraps_instead_of_overflowing(tmp_path):
    out = tmp_path / "hook.png"
    long = "an opening hook that is deliberately much longer than one line of a 480 wide card"
    video.hook_text(long, 480, 270, {"accent": "#FFFFFF"}, out)
    with Image.open(out) as im:
        assert im.size == (480, 270)


def test_badge_renders(tmp_path):
    out = tmp_path / "badge.png"
    video.badge("STEP 1", 320, 120, {"accent": "#00FF00"}, out)
    assert out.is_file()


def test_card_renders_every_documented_kind(tmp_path):
    for kind in ("title", "text", "quote"):
        out = tmp_path / kind / "card.png"
        out.parent.mkdir()
        spec = {"kind": kind, "title": "T", "text": "body text", "credit": "@me"}
        video.card(spec, 480, 270, {"accent": "#FFFFFF", "bg": "#101010"}, out)
        assert out.is_file(), kind


# --------------------------------------------------------------------------- the CLI surface


def test_register_exposes_every_subcommand():
    import argparse

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="group")
    video.register(sub)
    assert set(sub.choices) == {"video"}


def test_probe_falls_back_to_the_ffmpeg_banner(monkeypatch):
    """No ffprobe on the box is not an error: the banner has duration, size, fps and audio."""
    banner = (
        "Input #0, matroska,webm, from 'take.mkv':\n"
        "  Duration: 00:01:02.50, start: 0.000000, bitrate: 1000 kb/s\n"
        "  Stream #0:0: Video: h264, yuv420p, 1920x1080, 30 fps\n"
        "  Stream #0:1: Audio: pcm_s16le, 48000 Hz, mono\n")

    class R:
        returncode = 0
        stderr = banner
        stdout = ""

    monkeypatch.setattr(video.shutil, "which", lambda name: None)
    monkeypatch.setattr(video.subprocess, "run", lambda *a, **kw: R())
    p = video.probe("take.mkv")
    assert p["duration"] == pytest.approx(62.5)
    assert (p["width"], p["height"], p["fps"]) == (1920, 1080, 30.0)
    assert p["audio"] is True and p["audio_rate"] == 48000


def test_probe_reads_ffprobe_json_when_it_is_there(monkeypatch):
    payload = {"streams": [
        {"codec_type": "video", "width": 1280, "height": 720, "avg_frame_rate": "30000/1001"},
        {"codec_type": "audio", "sample_rate": "44100"},
    ], "format": {"duration": "12.34"}}

    class R:
        returncode = 0
        stdout = json.dumps(payload)
        stderr = ""

    monkeypatch.setattr(video.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(video.subprocess, "run", lambda *a, **kw: R())
    p = video.probe("take.mp4")
    assert p["duration"] == 12.34
    assert p["fps"] == pytest.approx(29.97, abs=0.01)
    assert p["audio_rate"] == 44100
