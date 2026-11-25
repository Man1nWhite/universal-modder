"""Where a clip's cut lands: in a gap between words, never inside one.

The pack answers Hila's lines with *sub-ranges* of Miranda's scene dialogue, so the
one thing a pick has to get right is its two edges. Two of them did not, and the
2026-11-25 report heard it in the game: `civ.down` ended at 1.020 s of
`procer_cover_tutorial_a_S_INT.011.ogg`, which is inside "Shepard" ("keep you head
down, Shep"), and `call_teammate.hey_you` started at 1.310 s of
`profre_cover_tutorial_a_S_INT.002.ogg`, on the "-ard" of the same name. That slot has since
been re-picked twice - once to three words from the same take, then (2026-11-25, D67) to one
shouted "You" - so its test now measures that word instead.

Both are now measured rather than guessed, and these tests measure them again: the
edges are decoded from the tracked archive with the pinned `py7zr` and
`imageio-ffmpeg`, so this runs offline like the rest of the suite. A voice is
distinguishable from the silence around it - and "sh" from the "n" before it - by
the share of energy above 4 kHz, which is what the checks below use.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import hila_voice_clips as vo  # noqa: E402

DIR = ROOT / "voice_lines_vox" / "miranda_lawson"
RATE = 44100
#: below 4 kHz is voice, above it is a fricative: "sh" is 65-85% high, "n" is 0%
HF_BAND = (4000, 9000)
#: the source oggs the pinned picks cut from
SOURCES = (
    "procer_cover_tutorial_a_S_INT.011.ogg",   # civ.down
    "twrvxl_oldfriend_d_S_INT.043.ogg",        # call_teammate.hey_you
    "norvx_relationship_03_h_S_INT.037.ogg",   # cop.hands
    "norvx_starter_h_S_INT.006.ogg",           # civ.nophone
)


def _pick(slot: str) -> dict:
    with (DIR / "slot_picks.csv").open(newline="", encoding="utf-8") as f:
        picks = {r["slot"]: r for r in csv.DictReader(f)}
    assert slot in picks, f"{slot} has no curated pick"
    return picks[slot]


@pytest.fixture(scope="module")
def decode_source(tmp_path_factory):
    """`filename -> mono 44.1 kHz float samples`, unpacked from the tracked archive."""
    import py7zr

    archive = ROOT / "references" / "Голос Лоусон.7z"
    if not archive.is_file():
        raise AssertionError(f"{archive.relative_to(ROOT)} is tracked; it is missing here")
    out = tmp_path_factory.mktemp("hila_src")
    with py7zr.SevenZipFile(archive) as z:
        names = z.getnames()
        targets = [n for n in names if any(stem in n for stem in SOURCES)]
        assert len(targets) == len(SOURCES), targets
        z.extract(path=str(out), targets=targets)

    ff = vo.ffmpeg_bin()
    assert ff, "imageio-ffmpeg is a pinned build dependency"

    cache: dict[str, np.ndarray] = {}

    def decode(name: str) -> np.ndarray:
        if name not in cache:
            hits = [p for p in out.rglob(name)]
            assert hits, f"{name} is not in the archive"
            raw = subprocess.run(
                [ff, "-v", "quiet", "-i", str(hits[0]), "-ac", "1", "-ar", str(RATE),
                 "-f", "s16le", "-"], check=True, capture_output=True).stdout
            cache[name] = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
        return cache[name]

    return decode


def _window(pcm: np.ndarray, start: float, end: float) -> np.ndarray:
    return pcm[max(0, int(start * RATE)):max(0, int(end * RATE))]


def _level_db(seg: np.ndarray) -> float:
    if not len(seg):
        return -120.0
    return 20 * np.log10(max(float(np.sqrt((seg ** 2).mean())), 1e-9))


def _loudest_db(pcm: np.ndarray, start: float, end: float, window: float = 0.020) -> float:
    """The loudest 20 ms of a span: what "quiet" is measured against."""
    hop = int(window * RATE)
    levels = [_level_db(pcm[i:i + hop]) for i in range(0, len(pcm) - hop, hop)]
    return max(levels[int(start / window):int(end / window)] or [-120.0])


def _hf_share(seg: np.ndarray) -> float:
    """Share of the segment's energy between 4 and 9 kHz: a fricative detector."""
    if not len(seg):
        return 0.0
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / RATE)
    total = float((spec ** 2).sum())
    if not total:
        return 0.0
    band = (spec[(freqs >= HF_BAND[0]) & (freqs < HF_BAND[1])] ** 2).sum()
    return float(band) / total


def test_the_down_line_ends_before_the_name(decode_source):
    """`civ.down`: "Keep your head down," stops before the "sh" of "Shepard"."""
    pick = _pick("civ.down")
    pcm = decode_source(pick["source_ogg"])
    start, end = float(pick["t_start"]), float(pick["t_end"])

    # The last 20 ms of the clip are the nasal tail of "down": no high band at
    # all (the decoded source measures 0.00 there, against 0.80 for the name).
    assert _hf_share(_window(pcm, end - 0.020, end)) < 0.05, \
        "the cut ends on a fricative, not on the 'n' of 'down'"

    # The name starts immediately after the edge, and it starts with "sh": 80% of
    # the next 80 ms is high band. The first 20 ms already are, which is what makes
    # the edge tight rather than merely early.
    assert _hf_share(_window(pcm, end, end + 0.080)) > 0.50, \
        "the name's 'sh' is not where the pick says it is"
    assert _hf_share(_window(pcm, end, end + 0.020)) > 0.15, \
        "the cut is far from the name; the clip is shorter than the line"

    # Nothing of the name is inside the clip - which is exactly what the 1.020 s
    # edge broke, played back as "keep you head down, Shep".
    assert _hf_share(_window(pcm, end - 0.060, end)) < 0.05

    # Still a bark, and it does not run on into "Shield yourself from the blast.".
    assert 0.5 < end - start < 1.0


def test_the_hey_you_line_is_one_shouted_word(decode_source):
    """`call_teammate.hey_you`: one emphatic "You", gap to gap.

    The slot asks a teammate to come to you, so the whole line is the call: the pick is the
    "You" of "You don't know what my father wants for her." - the /j/ onset, the stressed /u/
    and the decay into the /d/ closure of "don't", which is where the cut ends. The pack has
    no "hey" anywhere in its 866 transcripts (see `voice_lines_vox/README.md`), and the
    2026-11-25 report heard the three-word pick as just "you", so one word it is.
    """
    pick = _pick("call_teammate.hey_you")
    pcm = decode_source(pick["source_ogg"])
    start, end = float(pick["t_start"]), float(pick["t_end"])
    loudest = _loudest_db(pcm, start, end)

    # It starts in silence, then the /j/ glide brings the voice in.
    assert start <= 0.010
    assert _level_db(_window(pcm, start, start + 0.015)) < loudest - 15
    # One stressed word: the vowel peaks within 6 dB of the loudest point ...
    assert _level_db(_window(pcm, start + 0.15, start + 0.20)) > loudest - 3
    # ... and the clip is over inside the /d/ closure, before "don't" starts at 0.33 s.
    assert end <= 0.32, "the cut runs into the next word"
    assert _level_db(_window(pcm, end - 0.015, end)) < loudest - 15
    assert _level_db(_window(pcm, 0.33, 0.36)) > loudest - 20, \
        "the next word is no longer where the cut assumes it is; this diagnosis is stale"

    # A call-out, not a sentence: a third of a second, and nothing else in it.
    assert 0.20 < end - start < 0.40


def test_the_stop_line_is_the_word_and_not_the_next_one(decode_source):
    """`cop.hands`: "Stop." is the word from "and stop smiling, dammit.", whole.

    The D61 pick took 0.420-0.650 s of that file and played a chopped "smi": the
    phrase's /s/ is at 0.41 and the word "stop" *ends* before it. The clip now
    starts on the word's own /s/, keeps the /t/ closure and the vowel, and stops in
    the gap that follows the /p/.
    """
    pick = _pick("cop.hands")
    pcm = decode_source(pick["source_ogg"])
    start, end = float(pick["t_start"]), float(pick["t_end"])
    loudest = _loudest_db(pcm, start, end)

    # It opens on the /s/ of "stop": a fricative in the first tenth of a second ...
    assert max(_hf_share(_window(pcm, start + 0.01 * i, start + 0.01 * i + 0.02))
               for i in range(0, 9)) > 0.25, \
        "there is no 's' in the head of the clip"
    # ... then the /t/ closure and the open vowel, which carry no high band at all.
    assert _hf_share(_window(pcm, start + 0.14, start + 0.22)) < 0.05, \
        "the vowel of 'stop' is not inside the clip"
    assert _level_db(_window(pcm, start + 0.16, start + 0.22)) > loudest - 6
    # The end is the gap after the /p/, not speech - the word's release decays into it.
    assert _level_db(_window(pcm, end - 0.015, end)) < loudest - 20
    assert _level_db(_window(pcm, end, end + 0.030)) < loudest - 20

    # It is the word: short, and over before the next word's /s/ at 0.41 s - which is
    # where the old 0.420-0.650 window started, on a 53%-high-band fricative that
    # belongs to "smiling".
    assert 0.20 < end - start < 0.35
    assert end < 0.40
    assert _hf_share(_window(pcm, 0.420, 0.440)) > 0.30, \
        "the old window no longer lands on a fricative; this diagnosis is stale"


def test_the_no_calls_line_is_the_whole_take(decode_source):
    """`civ.nophone`: the whole line, from its first sound to the gap after it."""
    pick = _pick("civ.nophone")
    pcm = decode_source(pick["source_ogg"])
    start, end = float(pick["t_start"]), float(pick["t_end"])
    loudest = _loudest_db(pcm, start, end)

    # Nothing is cut off the head: the line starts with the file.
    assert start <= 0.010
    assert _level_db(_window(pcm, start, start + 0.020)) > loudest - 20
    # And the tail lands in the gap after "didn't", so no release is clipped.
    assert _level_db(_window(pcm, end - 0.015, end)) < loudest - 20
    assert _level_db(_window(pcm, end, end + 0.020)) < loudest - 20
    # A bark, not a speech.
    assert 0.85 < end - start < 1.05
