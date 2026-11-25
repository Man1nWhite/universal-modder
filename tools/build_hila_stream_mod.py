#!/usr/bin/env python3
"""Pack Miranda Lawson's barks over Hila as ``.stream`` files named by voice-line id.

This is the route the game itself uses: every heister line is a file
``soundbanks/streamed/regular_vox/<id>.stream`` and the game plays it by id, so
writing a file with our audio under Hila's id replaces that one line - no event
table, no BeardLib, no Lua. ``references/Tokoyami Hila.7z`` is the working pack
this is modelled on (``docs/tokoyami-hila-voice-mod-analysis.md``).

The clips are the same ones the BeardLib pack ships (``slot_picks.csv`` decides
each slot's ogg and the sub-ranges it keeps), re-encoded from the same cut oggs
as IMA ADPCM in Wwise's RIFF container by ``tools/pd2-las/wwise_ima.py``. One
file per id, so the 885 ids of ``hila_intent_cuts.csv`` become 885 files (858
after the 27 ids the vanilla bank keeps as Wwise Vorbis, which only a Wwise
encoder could write - see ``hila_vorbis_ids.csv``).

    python tools/build_hila_stream_mod.py            # dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip
    python tools/build_hila_stream_mod.py --out build/hila_stream.zip
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]
import determinism  # noqa: E402  (the pinned numeric code path every builder enters)
import wwise_ima  # noqa: E402
import build_hila_voice_mod as vo  # noqa: E402  (cut, level and archive helpers)

INSTALL = "Miranda Lawson VO over Hila Stream"
CUTS = ROOT / "voice_lines_vox/miranda_lawson/hila_intent_cuts.csv"
PICKS = ROOT / "voice_lines_vox/miranda_lawson/slot_picks.csv"
VORBIS = ROOT / "voice_lines_vox/miranda_lawson/hila_vorbis_ids.csv"
DEFAULT_OUT = ROOT / "dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip"
BANK = "soundbanks/streamed/regular_vox"
ZIP_DATE = (2026, 11, 25, 0, 0, 0)


def load_ids() -> list[tuple[str, str, str]]:
    """(id, slot, also_slots) per voice-line id, in id order.

    Two ids answer two slots in the table; a file can only hold one line, so the
    first row wins and the other slots are recorded in the manifest.
    """
    rows = vo.load_cuts()
    if not rows:
        raise SystemExit(f"no rows in {CUTS}")
    chosen: dict[str, tuple[str, list[str]]] = {}
    for r in rows:
        hila_id, slot = r["hila_id"].strip(), r["slot"].strip()
        if not hila_id.isdigit():
            raise SystemExit(f"not a numeric voice-line id: {hila_id!r}")
        if not slot:
            raise SystemExit(f"voice-line id {hila_id} names no slot")
        if hila_id in chosen:
            if slot not in chosen[hila_id][1]:
                chosen[hila_id][1].append(slot)
            continue
        chosen[hila_id] = (slot, [])
    return [(hila_id, slot, "|".join(also)) for hila_id, (slot, also) in sorted(chosen.items())]


def load_vorbis_ids() -> dict[str, str]:
    """The ids the vanilla bank streams as Wwise Vorbis: not ours to write in ADPCM."""
    if not VORBIS.is_file():
        raise SystemExit(f"missing {VORBIS} (the ids an ADPCM .stream cannot replace)")
    with VORBIS.open(newline="", encoding="utf-8") as f:
        return {r["hila_id"].strip(): (r.get("note") or "").strip() for r in csv.DictReader(f)}


def cut_clip(slot: str, pick: dict, by_base: dict[str, str], extracted: dict[str, Path],
             work: Path, ff: str, normalize: bool = True) -> tuple[Path, float, float]:
    """The slot's clip as an ogg, cut and level-matched exactly as the BeardLib pack does."""
    base = Path(pick["source_ogg"]).name
    path = by_base.get(base)
    src = extracted.get(path) if path else None
    if src is None:
        raise SystemExit(f"{slot}: {base} is not in the archive")
    ranges = vo.parse_splits(pick.get("splits", ""))
    if ranges:
        dest = work / f"{Path(base).stem}_cut{len(ranges)}.ogg"
        vo.cut_ogg_ranges(src, ranges, dest, ff)
        start, end = ranges[0][0], ranges[-1][1]
    else:
        start, end = float(pick["t_start"]), float(pick["t_end"])
        if end <= start:
            raise SystemExit(f"{slot}: slot_picks.csv has no usable range for {path}")
        dest = work / f"{Path(base).stem}_p{start:.2f}-{end:.2f}.ogg"
        vo.cut_ogg(src, start, end, dest, ff)
    if normalize:
        vo.match_level(dest, ff)
    return dest, start, end


def pcm_mono(path: Path, ff: str):
    import numpy as np
    raw = subprocess.run(
        [ff, "-v", "quiet", "-i", str(path), "-f", "s16le", "-ac", "1",
         "-ar", str(wwise_ima.SAMPLE_RATE), "pipe:1"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.int16)


def readme(n_files: int, n_ids: int, n_vorbis: int, seconds: float) -> str:
    return f"""{INSTALL}

WHAT IT IS
Hila's voice lines, replaced by short Miranda Lawson clips from Mass Effect, one
game file per line: this pack writes {n_files} files into
soundbanks/streamed/regular_vox/ under Hila's own voice-line ids. The game plays
a line by its id, so the clip answers that line whether it comes from a bark
event, a heist script or a teammate callout - no event table to keep up to date.

REQUIRES
A working copy of PAYDAY 2 with SuperBLT (or any BLT build). Nothing else:
this route is a file replacement, so BeardLib and the XAudio API are not used.

INSTALL
  1. Close PAYDAY 2.
  2. Copy the whole folder "{INSTALL}" into
       ...\\\\Steam\\\\steamapps\\\\common\\\\PAYDAY 2\\\\mods\\\\
     Final check: PAYDAY 2\\\\mods\\\\{INSTALL}\\\\main.xml must exist.
     Do not nest it twice (mods\\\\{INSTALL}\\\\{INSTALL}\\\\main.xml is wrong).
  3. Start the game and play a heist with Hila (as your heister, or as an AI
     teammate). Her barks are Miranda's now; the heist-scripted story lines she
     speaks as an NPC are not touched - those are not heister voice lines.

UNINSTALL
Delete this folder, or untick it in the main-menu Mods list.

HOW IT REPLACES LINES
Every heister voice line is soundbanks/streamed/regular_vox/<id>.stream - RIFF
IMA ADPCM, 44.1 kHz mono, 64 samples per 36-byte block. Replacing the file under
that id replaces the line, which is how voice packs have always been made.
The audio is the same set of cuts the BeardLib pack ships, re-encoded to ADPCM
(measured 30 dB SNR against the ogg source, i.e. transparent for speech at this
bitrate).

WHAT IS NOT IN HERE
  * {n_vorbis} of the {n_ids} ids in this pack's table are streamed by the vanilla game as Wwise
    Vorbis, and only the Wwise encoder can write that. Those ids are left out on
    purpose: an ADPCM file under a Vorbis id is not the audio the bank expects.
    Those lines stay vanilla unless the BeardLib pack (the other zip) is used.
  * The `robbers_mission_gen` bank: those ids are heist-scripted NPC lines with
    their own text, not heister barks.

IF NOTHING CHANGES
Check that the folder is in mods/ and not nested, that Hila is the heister you
hear (rb21), and that no other Hila voice pack is installed. A second pack
writing the same ids wins or loses by load order.

CONTENTS
  main.xml                              mod folder marker, nothing to configure
  mod.txt                               BLT mod-list metadata
  soundbanks/streamed/regular_vox/      {n_files} .stream files, {seconds:.0f}s of audio in all
  hila_stream_map.csv                   id -> slot -> source clip (build manifest)

Source archive: references/\\u0413\\u043e\\u043b\\u043e\\u0441 \\u041b\\u043e\\u0443\\u0441\\u043e\\u043d.7z
Mapping: voice_lines_vox/miranda_lawson/hila_intent_cuts.csv
Nothing outside this folder is touched: music, radio, other heisters and all
vanilla files stay as they are.
"""


def mod_txt() -> str:
    return (
        "{\n"
        f"\t\"name\" : \"{INSTALL}\",\n"
        "\t\"description\" : \"Replaces Hila's heister voice lines with short Miranda Lawson "
        "clips from Mass Effect, one streamed .stream file per voice-line id.\",\n"
        "\t\"author\" : \"universal-modder\",\n"
        "\t\"version\" : \"1.0\",\n"
        "\t\"priority\" : 0\n"
        "}\n"
    )


def main_xml() -> str:
    """A mod folder BLT loads. The soundbanks are overrides, so there is nothing to configure."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<mod name="{escape(INSTALL)}" version="1.0">\n'
        "  <!-- The soundbanks/ directory is the whole mod: BLT serves the files, the\n"
        "       game reads them by voice-line id. No hooks, no scripts. -->\n"
        "</mod>\n"
    )


def write_zip(out: Path, files: dict[str, bytes]) -> tuple[int, str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name)
            info.date_time = ZIP_DATE
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    data = buf.getvalue()
    out.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    try:
        name = out.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = out.name
    out.with_suffix(out.suffix + ".sha256").write_text(sha + "  " + name + "\n", encoding="utf-8")
    return len(data), sha


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--no-normalize", action="store_true",
                   help="skip per-clip level matching to -1.5 dBFS peak")
    p.add_argument("--include-vorbis-ids", action="store_true",
                   help="write ADPCM even under the ids the vanilla bank streams as Vorbis")
    p.add_argument("--source-dir", type=Path, default=None,
                   help="optional already-extracted Голос Лоусон folder; "
                        "without it the archive is unpacked into a temporary directory")
    args = p.parse_args(argv)
    determinism.enter(__file__)
    vo.import_py7zr()
    if not vo.ARCHIVE.is_file():
        raise SystemExit(f"missing {vo.ARCHIVE}")
    ff = vo.ffmpeg_bin()
    if ff is None:
        raise SystemExit("ffmpeg is missing (pip install imageio-ffmpeg)")

    ids = load_ids()
    vorbis = load_vorbis_ids()
    picks = vo.load_picks()
    slots = {slot for _id, slot, _also in ids}
    unpicked = sorted(slots - picks.keys())
    if unpicked:
        raise SystemExit("slots without a clip in slot_picks.csv: " + ", ".join(unpicked))
    unknown = sorted(vorbis.keys() - {hila_id for hila_id, _s, _a in ids})
    if unknown:
        raise SystemExit("hila_vorbis_ids.csv names ids that are not in the cuts table: "
                         + ", ".join(unknown))

    work = tempfile.TemporaryDirectory(prefix="hila_stream_")
    stage = Path(work.name)
    by_base = {base: path for _size, base, path in vo.list_archive_oggs()}
    wanted = {by_base[Path(p["source_ogg"]).name] for p in picks.values()
              if Path(p["source_ogg"]).name in by_base}
    extracted = vo.extract_selected(wanted, stage / "src")

    clip = {}
    for slot in sorted(slots):
        dest, start, end = cut_clip(slot, picks[slot], by_base, extracted, stage, ff,
                                    normalize=not args.no_normalize)
        pcm = pcm_mono(dest, ff)
        blob = wwise_ima.encode(pcm, 1)
        channels, rate, data = wwise_ima.read(blob)
        assert channels == 1 and rate == wwise_ima.SAMPLE_RATE
        clip[slot] = (blob, start, end, pcm.shape[0] / wwise_ima.SAMPLE_RATE,
                      pcm.shape[0] // wwise_ima.FRAMES * wwise_ima.FRAMES)

    install = INSTALL + "/"
    files = {
        install + "main.xml": main_xml().encode("utf-8"),
        install + "mod.txt": mod_txt().encode("utf-8"),
    }
    manifest = io.StringIO()
    w = csv.writer(manifest, lineterminator="\n")
    w.writerow(["hila_id", "slot", "also_slots", "cut_line", "source_ogg", "t_start", "t_end",
                "clip_s", "frames", "stream_bytes", "skipped"])
    seconds = 0.0
    for hila_id, slot, also in ids:
        blob, start, end, clip_s, frames = clip[slot]
        skipped = "vorbis id left vanilla" if hila_id in vorbis and not args.include_vorbis_ids else ""
        if not skipped:
            files[f"{install}{BANK}/{hila_id}.stream"] = blob
            seconds += clip_s
        w.writerow([hila_id, slot, also, picks[slot].get("cut_line", ""), picks[slot]["source_ogg"],
                    f"{start:.3f}", f"{end:.3f}", f"{clip_s:.3f}", frames, len(blob), skipped])
    files[install + "hila_stream_map.csv"] = manifest.getvalue().encode("utf-8")
    n_files = sum(1 for name in files if name.endswith(".stream"))
    files[install + "README.txt"] = readme(n_files, len(ids), len(vorbis), seconds).encode("utf-8")

    size, sha = write_zip(args.out, files)
    print(f"wrote {args.out} ({size} bytes) sha256={sha[:12]}… streams={n_files} "
          f"ids={len(ids)} slots={len(clip)} audio={seconds:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
