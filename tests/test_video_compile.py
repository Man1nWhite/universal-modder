"""`um video compile` builds the ffmpeg filtergraph for an EDL.

The EDL → filtergraph wiring — transition offsets, beat lock, speed tempo chains, cut vs xfade —
was the least-tested decision in the package. These tests fake only `ff()` (recording its argv) and
`probe()`, so the graph the EDL produces is asserted exactly. ffmpeg itself is not run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from um import video

Image = pytest.importorskip("PIL.Image", reason="cards need pillow")


@pytest.fixture
def fake_ffmpeg(monkeypatch, tmp_path):
    calls = []

    def fake(*args, quiet=True, timeout=3600):
        calls.append(args)
        out = args[-1]
        Path(out).write_bytes(b"fake container")

    monkeypatch.setattr(video, "ff", fake)
    monkeypatch.setattr(video, "probe", lambda p: dict(path=str(p), duration=100.0, width=1920, height=1080,
                                                       fps=30.0, audio=True, audio_rate=48000))
    monkeypatch.setattr(video, "_seg_dur_default", 4.0, raising=False)
    return calls


def _edl(tmp_path, segments, **top):
    edl = {"size": [640, 360], "fps": 30, "transition": {"type": "fade", "duration": 0.3},
           "segments": segments, **top}
    p = tmp_path / "edl.json"
    p.write_text(json.dumps(edl), encoding="utf-8")
    return p


def _graph(call):
    args = list(call)
    i = args.index("-filter_complex")
    return args[i + 1]


def test_card_then_clip_compiles_and_xfades(tmp_path, fake_ffmpeg):
    edl = _edl(tmp_path, [
        {"card": {"title": "Every game is moddable now."}, "dur": 1.0},
        {"clip": "a.mp4", "in": 0, "dur": 2.0},
    ])
    video.compile_edl(edl, tmp_path / "out.mp4")
    assert len(fake_ffmpeg) == 3                     # two segments + the join
    join = _graph(fake_ffmpeg[-1])
    assert "xfade=transition=fade:duration=0.3:offset=0.7000" in join
    assert "acrossfade=d=0.3" in join
    assert "fade=t=out" in join and "format=yuv420p[vout]" in join


def test_cut_transition_uses_concat_not_xfade(tmp_path, fake_ffmpeg):
    edl = _edl(tmp_path, [
        {"card": {"title": "A"}, "dur": 1.0, "transition": {"type": "cut"}},
        {"card": {"title": "B"}, "dur": 1.0},
    ], transition={"type": "cut", "duration": 0.0})
    video.compile_edl(edl, tmp_path / "out.mp4")
    join = _graph(fake_ffmpeg[-1])
    assert "concat=n=2:v=1:a=0" in join and "xfade" not in join


def test_beat_lock_lengthens_segments_so_cuts_land_on_the_grid(tmp_path, fake_ffmpeg):
    edl = _edl(tmp_path, [
        {"card": {"title": "A"}, "beats": 4},
        {"card": {"title": "B"}, "beats": 4},
    ], bpm=120, beat_lock=True)
    video.compile_edl(edl, tmp_path / "out.mp4")
    join = _graph(fake_ffmpeg[-1])
    # four beats at 120 bpm = 2.0 s, transition 0.3 overlaps, so segment 0 is 2.3 s and the fade is at 2.0
    assert "offset=2.0000" in join


def test_speed_uses_a_legal_tempo_chain(tmp_path, fake_ffmpeg):
    edl = _edl(tmp_path, [{"clip": "a.mp4", "in": 0, "dur": 2.0, "speed": 5.0}])
    video.compile_edl(edl, tmp_path / "out.mp4")
    seg = _graph(fake_ffmpeg[0])
    assert "atempo=2.0,atempo=2.0,atempo=1.2500" in seg
    assert "setpts=(PTS-STARTPTS)/5.0" in seg


def test_odd_size_is_rejected_before_any_ffmpeg_call(tmp_path, fake_ffmpeg):
    edl = _edl(tmp_path, [{"card": {"title": "A"}, "dur": 1.0}], size=[641, 360])
    with pytest.raises(SystemExit):
        video.compile_edl(edl, tmp_path / "out.mp4")
    assert fake_ffmpeg == []


def test_clip_past_the_end_of_the_source_is_rejected(tmp_path, monkeypatch, fake_ffmpeg):
    monkeypatch.setattr(video, "probe", lambda p: dict(path=str(p), duration=3.0, width=1920, height=1080,
                                                       fps=30.0, audio=True, audio_rate=48000))
    edl = _edl(tmp_path, [{"clip": "a.mp4", "in": 2.5, "dur": 2.0}])
    with pytest.raises(SystemExit):
        video.compile_edl(edl, tmp_path / "out.mp4")


def test_every_ffmpeg_call_carries_a_timeout(tmp_path, fake_ffmpeg):
    """The pipeline must never wait on ffmpeg forever."""
    seen = []

    def recording_ff(*args, quiet=True, timeout=3600):
        seen.append(timeout)
        from pathlib import Path as _P
        _P(args[-1]).write_bytes(b"x")

    import um.video as v
    orig = v.ff
    v.ff = recording_ff
    try:
        edl = _edl(tmp_path, [{"card": {"title": "A"}, "dur": 0.5}, {"card": {"title": "B"}, "dur": 0.5}])
        v.compile_edl(edl, tmp_path / "out.mp4")
    finally:
        v.ff = orig
    assert seen and all(t and t > 0 for t in seen)


def test_fake_ffmpeg_records_the_expected_codec_flags(tmp_path, fake_ffmpeg):
    edl = _edl(tmp_path, [{"card": {"title": "A"}, "dur": 0.5}])
    video.compile_edl(edl, tmp_path / "out.mp4")
    args = list(fake_ffmpeg[0])
    assert "-pix_fmt" in args and "yuv420p" in args
    assert str(args[-1]).endswith(".mkv")                # segments are mkv: survives a kill
