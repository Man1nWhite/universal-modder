#!/usr/bin/env python3
"""Wwise IMA ADPCM in a RIFF ``.stream`` file: read, decode, encode, write.

PAYDAY 2 keeps heister voice lines in ``soundbanks/streamed/<bank>/<id>.stream``:
one audio file per voice-line id, no event table, so a voice pack replaces a
line by naming its file after the id. Almost all of them are Wwise's IMA
ADPCM in a plain RIFF container, and this module is the whole format, checked
byte for byte against the 1,062 ADPCM files of ``references/voice/Tokoyami Hila.7z``
(see the ``format`` tab of ``voice_lines_vox/vo_master.xlsx``):

* A 64-byte header: ``RIFF``/``WAVE``, ``fmt `` with a **24-byte** payload,
  a ``JUNK`` chunk of 4 zero bytes, then ``data``.
* ``fmt ``: tag 2 (IMA ADPCM), channel count, sample rate, byte rate,
  block align, 4 bits per sample, ``cbSize`` 6, and six bytes Wwise fills with
  ``00 00 04 00 00 00`` for mono / ``00 00 03 00 00 00`` for stereo.
  The byte rate is ``(rate // 64) * block_align``, not ``rate * block_align / 64``.
* ``data``: blocks of one 36-byte sub-block per channel, 72 bytes for stereo.
  Each sub-block is a 4-byte header (``int16`` predictor, ``uint8`` step index,
  one reserved byte) and 32 bytes of nibbles = **64 frames**. Nibbles are
  low first, each holds 3 bits of magnitude and a sign bit, and the last
  nibble of a sub-block is padding: 63 coded samples after the header sample.

The encoder is the reason this is a module rather than fifty lines in the
builder. Blocks are independent, so the step index and the predictor cannot
run across a whole file the way a streaming encoder does; encoding 64 frames
at a time, a block that starts on the wrong step index spends its first
samples crawling out of the wrong resolution and the line audibly smears
(measured: 13 dB SNR against 35 dB when the start index is chosen per block).
``encode`` therefore tries a handful of start indices per block, and the level
estimate is integer-only so the bytes do not depend on the machine.
"""
from __future__ import annotations

import struct

import numpy as np

#: IMA's step table and per-nibble index steps (the standard tables).
STEPS = (
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41,
    45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190,
    209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724,
    796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272,
    2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132,
    7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350,
    22385, 24623, 27086, 29794, 32767,
)
INDEX_STEP = (-1, -1, -1, -1, 2, 4, 6, 8)
_STEP = np.array(STEPS, dtype=np.int32)
_INDEX_STEP = np.array(INDEX_STEP * 2, dtype=np.int32)  # indexed by the low 3 bits
#: frames in one sub-block: the header sample plus 63 coded samples
FRAMES = 64
#: bytes of one sub-block: 4 header bytes + 32 nibble bytes
SUBBLOCK = 36
SAMPLE_RATE = 44100


class FormatError(ValueError):
    """A .stream file that is not IMA ADPCM in the layout the game writes."""


def block_align(channels: int) -> int:
    return SUBBLOCK * channels


def header(channels: int, data_bytes: int, rate: int = SAMPLE_RATE) -> bytes:
    """The 64-byte RIFF header Wwise writes in front of ``data_bytes`` of ADPCM."""
    if channels not in (1, 2):
        raise ValueError(f"channels must be 1 or 2, not {channels}")
    if data_bytes % block_align(channels):
        raise ValueError(f"{data_bytes} data bytes is not a whole number of "
                         f"{block_align(channels)}-byte blocks")
    ba = block_align(channels)
    byte_rate = (rate // FRAMES) * ba
    # Wwise writes cbSize 6 and six bytes that differ by channel count; the
    # meaning is not in any public header, the bytes are copied from the game.
    extra = b"\x00\x00" + (b"\x04\x00" if channels == 1 else b"\x03\x00") + b"\x00\x00"
    fmt = struct.pack("<HHIIHHH", 2, channels, rate, byte_rate, ba, 4, 6) + extra
    return b"".join((
        b"RIFF", struct.pack("<I", 56 + data_bytes), b"WAVE",
        b"fmt ", struct.pack("<I", len(fmt)), fmt,
        b"JUNK", struct.pack("<I", 4), b"\x00" * 4,
        b"data", struct.pack("<I", data_bytes),
    ))


def encode(pcm, channels: int, rate: int = SAMPLE_RATE) -> bytes:
    """A whole ``.stream`` file from int16 PCM, shape (frames,) or (frames, channels)."""
    samples = np.asarray(pcm)
    if samples.ndim == 1:
        if channels != 1:
            raise ValueError("stereo needs a (frames, 2) array")
        samples = samples[:, None]
    elif samples.shape[1] != channels:
        raise ValueError(f"got {samples.shape[1]} channels, asked for {channels}")
    if samples.dtype != np.int16:
        samples = np.clip(np.rint(samples), -32768, 32767).astype(np.int16)
    blocks = _pad_blocks(samples.astype(np.int32))
    data = _interleave(blocks, channels) if channels == 2 else _encode_channel(blocks[:, :, 0])
    return header(channels, len(data), rate) + data


def _pad_blocks(samples: np.ndarray) -> np.ndarray:
    """(frames, channels) -> (blocks, FRAMES, channels), zero-padded to whole blocks."""
    frames, channels = samples.shape
    missing = -frames % FRAMES
    if missing:
        samples = np.concatenate([samples, np.zeros((missing, channels), np.int32)])
    return samples.reshape(-1, FRAMES, channels)


def _interleave(blocks: np.ndarray, channels: int) -> bytes:
    parts = [_encode_channel(blocks[:, :, c]) for c in range(channels)]
    # One block is channel 0's sub-block followed by channel 1's, so the
    # per-channel byte strings are shuffled back together block by block.
    out = bytearray()
    for b in range(blocks.shape[0]):
        for c in range(channels):
            out += parts[c][b * SUBBLOCK:(b + 1) * SUBBLOCK]
    return bytes(out)


def _level_guess(step: np.ndarray, residual: np.ndarray) -> np.ndarray:
    """Integer estimate of the nibble magnitude that best steps towards the target."""
    magnitude = np.abs(residual)
    return np.clip(((magnitude * 8) // step - 1) // 2, 0, 7).astype(np.int32)


def _choose(step: np.ndarray, predictor: np.ndarray, target: np.ndarray):
    """Best nibble per block, integer-only: magnitude estimate plus its neighbours."""
    residual = target - predictor
    level = _level_guess(step, residual)
    best_err = np.full(predictor.shape, np.iinfo(np.int64).max, np.int64)
    best_nibble = np.zeros(predictor.shape, np.int32)
    best_value = predictor.copy()
    for delta_level in (-1, 0, 1):
        k = np.clip(level + delta_level, 0, 7)
        step_delta = ((2 * k + 1) * step) >> 3
        for sign in (0, 8):  # positive first: a tie keeps the earlier candidate
            candidate = predictor - step_delta if sign else predictor + step_delta
            candidate = np.clip(candidate, -32768, 32767)
            error = np.abs(candidate - target)
            better = error < best_err
            best_err = np.where(better, error, best_err)
            best_nibble = np.where(better, k | sign, best_nibble)
            best_value = np.where(better, candidate, best_value)
    return best_nibble, best_value, best_err


def _run(blocks: np.ndarray, start: np.ndarray):
    """Encode one channel's blocks from the given start indices.

    Returns (nibbles (blocks, FRAMES), end index per block, squared error per block).
    """
    count = blocks.shape[0]
    predictor = blocks[:, 0].copy()
    index = start.astype(np.int32).copy()
    step = _STEP[index]
    nibbles = np.zeros((count, FRAMES), np.int32)
    squared = np.zeros(count, np.int64)
    for t in range(1, FRAMES):
        nibble, predictor, error = _choose(step, predictor, blocks[:, t])
        nibbles[:, t] = nibble
        squared += error * error
        index = np.clip(index + _INDEX_STEP[nibble & 7], 0, 88)
        step = _STEP[index]
    return nibbles, index, squared


def _candidates(blocks: np.ndarray, previous: np.ndarray) -> np.ndarray:
    """Start-index candidates per block: (candidates, blocks), from cheap estimates."""
    first = np.abs(np.diff(blocks[:, :5], axis=1)).mean(axis=1)
    # the step whose size is closest to the opening slope of the block
    estimate = np.abs(_STEP[:, None] - first[None, :]).argmin(axis=0)
    options = [np.zeros_like(estimate), previous]
    for shift in (-2, 2):
        options.append(np.clip(estimate + shift, 0, 88))
    options.append(estimate)
    return np.stack(options)


def _encode_channel(blocks: np.ndarray) -> bytes:
    """One channel of (blocks, FRAMES) samples to (blocks * SUBBLOCK) ADPCM bytes."""
    count = blocks.shape[0]
    candidates = _candidates(blocks, previous=np.zeros(count, np.int32))
    runs = [_run(blocks, start) for start in candidates]
    squared = np.stack([run[2] for run in runs])
    # a tie keeps the earlier candidate, so the choice does not depend on the order
    # in which numpy happens to compare equal values
    winner = squared.argmin(axis=0)
    start = candidates[winner, np.arange(count)]
    out = np.zeros((count, SUBBLOCK), np.uint8)
    # nibbles[:, 0] is the header sample, which is coded in the sub-block header:
    # the 63 packed nibbles are samples 1..63 and the 64th slot is Wwise's padding.
    coded = np.stack([runs[r][0] for r in range(len(runs))])[winner, np.arange(count)][:, 1:]
    nibbles = np.concatenate([coded, np.zeros((count, 1), np.int32)], axis=1)
    out[:, 0] = blocks[:, 0] & 0xFF
    out[:, 1] = (blocks[:, 0] >> 8) & 0xFF
    out[:, 2] = start.astype(np.uint8)
    out[:, 3] = 0
    packed = nibbles[:, 0::2] | (nibbles[:, 1::2] << 4)
    out[:, 4:] = packed.astype(np.uint8)
    return out.tobytes()


def read(blob: bytes) -> tuple[int, int, bytes]:
    """(channels, sample rate, ADPCM data) of a ``.stream`` file."""
    if len(blob) < 64 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise FormatError("not a RIFF/WAVE file")
    at = 12
    fmt = None
    while at + 8 <= len(blob):
        kind, size = blob[at:at + 4], struct.unpack("<I", blob[at + 4:at + 8])[0]
        payload = blob[at + 8:at + 8 + size]
        if len(payload) < size:
            raise FormatError(f"{kind!r} chunk runs past the end of the file")
        if kind == b"fmt ":
            fmt = payload
        elif kind == b"data":
            if fmt is None:
                raise FormatError("data before fmt")
            break
        at += 8 + size + (size & 1)
    else:
        raise FormatError("no data chunk")
    if fmt is None or len(fmt) < 18:
        raise FormatError("no usable fmt chunk")
    tag, channels, rate, _byte_rate, align, _bits, _extra = struct.unpack("<HHIIHHH", fmt[:18])
    if tag != 2:
        raise FormatError(f"not IMA ADPCM (fmt tag {tag})")
    if channels not in (1, 2) or align != block_align(channels):
        raise FormatError(f"unexpected channels/block align: {channels}/{align}")
    if size % align:
        raise FormatError(f"data size {size} is not a whole number of {align}-byte blocks")
    return channels, rate, payload


def decode(data: bytes, channels: int) -> np.ndarray:
    """int16 (frames, channels) from raw ADPCM block data."""
    align = block_align(channels)
    if len(data) % align:
        raise FormatError(f"{len(data)} bytes is not a whole number of blocks")
    blocks = np.frombuffer(data, np.uint8).reshape(-1, channels, SUBBLOCK)
    out = np.zeros((blocks.shape[0], FRAMES, channels), np.int16)
    for c in range(channels):
        rows = blocks[:, c, :]
        predictor = rows[:, 0].astype(np.int32) | (rows[:, 1].astype(np.int32) << 8)
        predictor = np.where(predictor >= 0x8000, predictor - 0x10000, predictor)
        index = rows[:, 2].astype(np.int32)
        step = _STEP[index]
        out[:, 0, c] = predictor
        for t in range(1, FRAMES):
            byte = rows[:, 4 + (t - 1) // 2]
            nibble = (byte >> (4 * ((t - 1) % 2))) & 0xF
            delta = ((2 * (nibble & 7) + 1) * step) >> 3
            predictor = np.where(nibble & 8, predictor - delta, predictor + delta)
            predictor = np.clip(predictor, -32768, 32767)
            index = np.clip(index + _INDEX_STEP[nibble & 7], 0, 88)
            step = _STEP[index]
            out[:, t, c] = predictor
    return out.reshape(-1, channels)


def decode_file(blob: bytes) -> tuple[int, np.ndarray]:
    """(sample rate, int16 (frames, channels)) of a ``.stream`` file."""
    channels, rate, data = read(blob)
    return rate, decode(data, channels)


def main(argv=None) -> int:
    """`python tools/pd2-las/wwise_ima.py FILE.stream [--wav out.wav]` — what is in this file."""
    import argparse
    import wave
    from pathlib import Path

    p = argparse.ArgumentParser(description="Inspect a Wwise IMA ADPCM .stream file.")
    p.add_argument("file", type=Path, nargs="+")
    p.add_argument("--wav", type=Path, help="write the decoded audio here (one file in, one file out)")
    args = p.parse_args(argv)
    if args.wav and len(args.file) != 1:
        p.error("--wav takes exactly one input file")
    for path in args.file:
        blob = path.read_bytes()
        try:
            rate, audio = decode_file(blob)
        except FormatError as error:
            print(f"{path.name}: {error} ({len(blob)} bytes)")
            continue
        frames = audio.shape[0]
        peak = int(abs(audio).max()) if frames else 0
        print(f"{path.name}: {audio.shape[1]} ch, {rate} Hz, {frames} frames "
              f"({frames / rate:.3f} s), {len(blob)} bytes, peak {peak}")
        if args.wav:
            args.wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(args.wav), "wb") as out:
                out.setnchannels(audio.shape[1])
                out.setsampwidth(2)
                out.setframerate(rate)
                out.writeframes(audio.astype("<i2").tobytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
