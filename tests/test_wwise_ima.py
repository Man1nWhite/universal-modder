"""The Wwise IMA ADPCM container: the bytes a real `.stream` file starts with, and a round trip.

The 64-byte headers below are copied from `references/Tokoyami Hila.7z`
(`soundbanks/streamed/regular_vox/100412034.stream`, mono, 612 data bytes; and
`1001973360.stream`, stereo, 100,224). They are the contract the encoder has to
reproduce: get the `fmt ` payload, the `JUNK` filler or the byte rate wrong and
the game may still play the file, or may not - nothing offline would say which.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import wwise_ima as w  # noqa: E402

MONO_HEADER = bytes.fromhex(
    "524946469c02000057415645666d742018000000"  # RIFF/WAVE, fmt , 24
    "0200 0100 44ac0000 e4600000 2400 0400 0600"  # tag 2, 1 ch, 44100, 24804, 36, 4 bits, cbSize 6
    "000004000000"                                # Wwise's six-byte tail, mono flavour
    "4a554e4b0400000000000000"                    # JUNK, 4 zero bytes
    "6461746164020000"                            # data, 612
)
STEREO_HEADER = bytes.fromhex(
    "52494646b887010057415645666d742018000000"
    "0200 0200 44ac0000 c8c10000 4800 0400 0600"
    "000003000000"
    "4a554e4b0400000000000000"
    "6461746180870100"
)


def test_the_mono_header_is_byte_identical_to_a_real_stream_file():
    assert w.header(1, 612) == MONO_HEADER


def test_the_stereo_header_is_byte_identical_to_a_real_stream_file():
    assert w.header(2, 100224) == STEREO_HEADER


def test_a_header_is_sixty_four_bytes_and_declares_the_whole_file():
    blob = w.encode(np.zeros(64, np.int16), 1)
    assert len(blob) == 64 + 36
    assert struct.unpack("<I", blob[4:8])[0] == len(blob) - 8
    assert blob[56:60] == b"data"  # 64-byte header, then the first block


def test_the_byte_rate_is_the_integer_blocks_per_second_the_game_writes():
    # 44100 / 64 = 689 blocks a second, times 36 bytes; not rate * align / 64 = 24806.
    assert struct.unpack("<I", w.header(1, 36)[28:32])[0] == 689 * 36
    assert struct.unpack("<I", w.header(2, 72)[28:32])[0] == 689 * 72


def test_a_round_trip_stays_within_ima_quantisation():
    rate = 44100
    t = np.arange(rate) / rate
    source = (9000 * np.sin(2 * np.pi * 220 * t) + 2500 * np.sin(2 * np.pi * 660 * t)).astype(np.int16)
    decoded = w.decode_file(w.encode(source, 1))[1][:, 0][:len(source)]
    error = decoded.astype(np.float64) - source.astype(np.float64)
    snr = 10 * np.log10((source.astype(np.float64) ** 2).sum() / (error ** 2).sum())
    assert snr > 25, f"{snr:.1f} dB is worse than IMA ADPCM should do at 4 bits"


def test_a_block_is_sixty_four_frames_and_the_tail_is_padding():
    decoded = w.decode_file(w.encode(np.arange(100, dtype=np.int16), 1))[1]
    assert len(decoded) == 128  # 100 samples, zero-padded to two blocks
    assert decoded.shape[1] == 1


def test_stereo_blocks_interleave_channel_by_channel():
    left = np.full(64, 1000, np.int16)
    right = np.full(64, -1000, np.int16)
    blob = w.encode(np.stack([left, right], axis=1), 2)
    channels, _rate, data = w.read(blob)
    assert channels == 2 and len(data) == 72
    decoded = w.decode(data, 2)
    assert decoded[0, 0] == 1000 and decoded[0, 1] == -1000


def test_the_same_audio_encodes_to_the_same_bytes():
    rng = np.random.default_rng(20261125)
    source = (rng.integers(-4000, 4000, 4096)).astype(np.int16)
    assert w.encode(source, 1) == w.encode(source.copy(), 1)


@pytest.mark.parametrize("blob, message", [
    (b"", "not a RIFF/WAVE file"),
    (b"RIFF" + b"\x00" * 60, "not a RIFF/WAVE file"),
    (MONO_HEADER[:40], "not a RIFF/WAVE file"),
])
def test_read_refuses_what_it_cannot_decode(blob, message):
    with pytest.raises(w.FormatError, match=message):
        w.read(blob)


def test_read_refuses_a_wwise_vorbis_file():
    """27 of the reference pack's 1,089 files are tag 0xFFFF; an ADPCM reader must say so."""
    vorbis = (b"RIFF" + struct.pack("<I", 66 + 8 + 94 - 8) + b"WAVE"
              + b"fmt " + struct.pack("<I", 66)
              + struct.pack("<HHIIHHH", 0xFFFF, 2, 44100, 14449, 0, 0, 48) + b"\x00" * 48
              + b"data" + struct.pack("<I", 94) + b"\x00" * 94)
    with pytest.raises(w.FormatError, match="not IMA ADPCM"):
        w.read(vorbis)


def test_a_data_size_that_is_not_whole_blocks_is_refused():
    blob = bytearray(w.header(1, 36) + bytes(36))
    blob[60:64] = struct.pack("<I", 30)
    with pytest.raises(w.FormatError, match="whole number of"):
        w.read(bytes(blob))
