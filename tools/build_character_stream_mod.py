#!/usr/bin/env python3
"""Pack the character voice sets over two more heisters, one ``.stream`` per voice-line id.

Same route as ``tools/build_hila_stream_mod.py``: every heister line the game plays
is ``soundbanks/streamed/<bank>/<id>.stream`` with the id as the file name, so the
file *is* the replacement. Slots with no take in the source set are left alone, so
vanilla audio plays there.

Two banks, and the pack you get depends on which ids it is given:

* ``shared`` — the ids are the shared ``regular_vox`` ones from
  ``voice_lines_vox/miranda_lawson/hila_intent_cuts.csv`` (885 ids). The two packs that
  wrote this bank (``Geralt_VO_over_Rust_Stream``, ``Arivus_VO_over_Hoxton_Stream``)
  were retired and deleted from ``dist/`` on 2026-11-28 (D87) — never heard in game.
  Running ``--pack all`` here would stage them under ``build/character_stream/``
  (gitignored scratch); shipping one means re-adding it to ``tools/pd2-las/packs.py``
  and passing ``--out dist/<group>/<pack>.zip``.
* ``char_rust`` — Rust's own bank, whose 1,046 ids were measured out of the reference
  Rust pack (``voice_lines_vox/targets/rust_dedicated_char_rust.csv``, D73). Writing
  here changes Rust alone. The ids cannot be derived: Wwise keeps no name for a
  streamed file, so a slot take may only ship once a source *names* its id in
  ``voice_lines_vox/geralt/char_rust_ids.csv``. Until then ``--bank char_rust`` refuses.

See the ``packs`` tab of ``voice_lines_vox/vo_master.xlsx`` for the record of the retired packs and how they related to the Hila one.

    python tools/build_character_stream_mod.py --pack geralt-rust      # retired 2026-11-28 (D87); stages into build/character_stream/
    python tools/build_character_stream_mod.py --pack arivus-old-hoxton # retired 2026-11-28 (D87); stages into build/character_stream/
    python tools/build_character_stream_mod.py --pack all
    python tools/build_character_stream_mod.py --pack geralt-rust --bank char_rust   # needs the named id map
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]
import determinism  # noqa: E402  (the pinned numeric code path every builder enters)
import wwise_ima  # noqa: E402
import hila_voice_clips as vo  # noqa: E402  (cut, level and parse helpers)
import build_hila_stream_mod as base  # noqa: E402  (load_ids, load_vorbis_ids, cut_clip, pcm_mono, write_zip)

BANK = "soundbanks/streamed/regular_vox"
ZIP_DATE = (2026, 11, 25, 0, 0, 0)
#: The banks a pack may be keyed on. `shared` is `regular_vox`; a dedicated bank is a folder
#: under `soundbanks/streamed/` whose ids only a measuring source can name (D73, D76).
BANKS = {"shared": BANK, "char_rust": "soundbanks/streamed/char_rust"}
def bank_folder(bank: str) -> str:
    """The `soundbanks/streamed/...` folder a bank writes."""
    try:
        return BANKS[bank]
    except KeyError:
        raise SystemExit(f"unknown bank {bank!r}; known: {', '.join(sorted(BANKS))}") from None


def load_named_ids(path: Path) -> dict[str, str]:
    """slot -> id from a table a source wrote; empty when the table is not there.

    A dedicated bank's ids cannot be derived (Wwise strips every name), so this reads only what
    a person or a tool has written down, and `named_id_sources` raises instead of inventing one.
    """
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("slot") and r.get("id")]
    bad = [r for r in rows if not r["id"].strip().isdigit()]
    if bad:
        raise SystemExit(f"{path}: not numeric voice-line ids: " + ", ".join(r["id"] for r in bad))
    return {r["slot"].strip(): r["id"].strip() for r in rows}

VOX = ROOT / "voice_lines_vox"
#: slot -> voice-line id for Rust's own bank, filled in only from a source that names both.
#: Never generated: a dedicated bank's ids cannot be derived (Wwise strips every name, D73).
CHAR_RUST_IDS = VOX / "geralt" / "char_rust_ids.csv"

#: the two character packs. `archives` are scanned in order for the picks' sources
#: (first hit wins); a take is keyed by its file name, which is what slot_picks.csv
#: carries in `source_ogg`.
#: retired packs stage into the gitignored build/ scratch tree by default; shipping means
#: re-adding the pack to tools/pd2-las/packs.py and building with --out dist/<group>/<pack>.zip
PACKS = {
    "geralt-rust": {
        "install": "Geralt VO over Rust Stream",
        "out": ROOT / "build/character_stream/Geralt_VO_over_Rust_Stream.zip",
        "picks": VOX / "geralt/slot_picks.csv",
        "archives": [(ROOT / "references/voice/GERALT VOICE (PAYDAY 2).zip", "cp866")],
        "archive_note": "references/voice/GERALT VOICE (PAYDAY 2).zip",
        "manifest": "geralt_rust_stream_map.csv",
        "speaker": "Geralt of Rivia",
        "target": "Rust (npc_criminal_wild_1), the punk heister",
        "who_hears": (
            "Whether Rust plays his heister barks from the shared regular_vox bank is NOT "
            "verified: the original crew do; the install doc notes newer heisters are "
            "documented elsewhere as char_<heister>. If Rust still barks in his vanilla "
            "voice in game, that is why, and this pack cannot cover him without a "
            "dedicated-bank variant."
        ),
        "who_else": (
            "Everything else on the regular_vox bank (Dallas, Hoxton, Wolf, chained out, "
            "Hila, ...) is replaced too; the bank is shared."
        ),
        "version": "1.0",
        "bank_target": "rust",
        "voice": "rb16",
        "named_ids": CHAR_RUST_IDS,
    },
    "arivus-old-hoxton": {
        "install": "Arivus VO over Old Hoxton Stream",
        "out": ROOT / "build/character_stream/Arivus_VO_over_Hoxton_Stream.zip",
        "picks": VOX / "arivus/slot_picks.csv",
        "archives": [(ROOT / "references/voice/ARIVUS VOICE (PAYDAY 2).zip", None),
                     (ROOT / "references/voice/GERALT VOICE (PAYDAY 2).zip", "cp866")],
        "archive_note": "references/voice/ARIVUS VOICE (PAYDAY 2).zip",
        "manifest": "arivus_hoxton_stream_map.csv",
        "speaker": "Arivus",
        "target": "Old Hoxton (npc_criminals_suit_1, mtr_old_hoxton), the shared-suit heister",
        "who_hears": (
            "Old Hoxton's heister lines are the shared regular_vox ones, like every heister "
            "on that bank - installing this pack replaces those lines for Dallas, Hoxton, "
            "Hila and everyone else on the bank, not only for Old Hoxton."
        ),
        "who_else": "The one borrowed file (call_teammate.hey_you, 'Hoxton.') is a Geralt take.",
        "version": "1.0",
    },
}


def load_picks_csv(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return {r["slot"]: r for r in csv.DictReader(f) if r.get("slot")}


def list_zip_files(path: Path, encoding: str | None) -> list[str]:
    with zipfile.ZipFile(path, metadata_encoding=encoding) as z:
        return [n for n in z.namelist() if not n.endswith("/")]


def stage_sources(wanted: set[str], archives: list[tuple[Path, str | None]],
                  dest: Path) -> dict[str, Path]:
    """Copy the wanted members out of the archives into `dest`, flat, named by file name.

    Returns file name -> staged path. First archive that holds a name wins.
    """
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    remaining = set(wanted)
    for path, enc in archives:
        if not remaining:
            break
        if not path.is_file():
            raise SystemExit(f"missing source archive {path}")
        with zipfile.ZipFile(path, metadata_encoding=enc) as z:
            for name in z.namelist():
                base = name.split("/")[-1]
                if base in remaining and base not in out:
                    target = dest / base
                    with z.open(name) as src, target.open("wb") as dst:
                        dst.write(src.read())
                    out[base] = target
                    remaining.discard(base)
    if remaining:
        raise SystemExit("not in any source archive: " + ", ".join(sorted(remaining)))
    return out


def readme(pack_id: str, cfg: dict, n_files: int, n_ids: int, n_vorbis: int, seconds: float,
           n_uncovered: int, n_uncovered_ids: int) -> str:
    install = cfg["install"]
    return f"""{install}

WHAT IT IS
{cfg['target']}'s voice lines, replaced by short {cfg['speaker']} barks: this pack writes
{n_files} files into soundbanks/streamed/regular_vox/ under the shared voice-line ids. The game plays
a line by its id, so the clip answers that line whether it comes from a bark event, a heist script
or a teammate callout - no event table to keep up to date.

{cfg['who_hears']}

THIS IS ONE OF SEVERAL VOICE PACKS
Regular_vox voice-line ids are shared between heisters, and this pack writes the same ids as
Miranda_Lawson_VO_over_Hila_Stream.zip (and any other pack built from them). INSTALL ONLY ONE:
another pack writing the same ids wins or loses by load order, and with two installed you get a
blend, not two voices.

REQUIRES
A working copy of PAYDAY 2 with SuperBLT (or any BLT build). Nothing else:
this route is a file replacement, so BeardLib and the XAudio API are not used.

INSTALL
  1. Close PAYDAY 2.
  2. Copy the whole folder "{install}" into
       ...\\\\Steam\\\\steamapps\\\\common\\\\PAYDAY 2\\\\mods\\\\
     Final check: PAYDAY 2\\\\mods\\\\{install}\\\\main.xml must exist.
     Do not nest it twice (mods\\\\{install}\\\\{install}\\\\main.xml is wrong).
  3. Start the game and play a heist. The barks you recorded should be {cfg['speaker']}'s; the
     heist-scripted story lines he speaks as an NPC are not touched - those are not heister voice
     lines. The clips' wording has not been verified by ear.

UNINSTALL
Delete this folder, or untick it in the main-menu Mods list.

HOW IT REPLACES LINES
Every heister voice line is soundbanks/streamed/regular_vox/<id>.stream - RIFF IMA ADPCM, 44.1 kHz
mono, 64 samples per 36-byte block. Replacing the file under that id replaces the line, which is how
voice packs have always been made. The clips are cut from the source MP3s and encoded to ADPCM
(measured 30 dB SNR against the sources, i.e. transparent for speech at this bitrate).

WHAT IS NOT IN HERE
  * {n_vorbis} of the {n_ids} ids in the shared table are streamed by the vanilla game as Wwise Vorbis,
    and only the Wwise encoder can write that. Those ids are left out on purpose.
  * {n_uncovered} slots ({n_uncovered_ids} ids) have no take in {cfg['archive_note']}: vanilla audio plays
    there. {cfg['who_else']}
  * The `robbers_mission_gen` bank: those ids are heist-scripted NPC lines with their own text.

IF NOTHING CHANGES
Check that the folder is in mods/ and not nested, that you are playing a heister on the shared
regular_vox bank ({cfg['target']}), that no other pack writes the same ids (see above), and the
in-game log lines named in docs/pd2-las/in-game-checklist.md.

CONTENTS
  main.xml                              mod folder marker, nothing to configure
  mod.txt                               BLT mod-list metadata
  soundbanks/streamed/regular_vox/      {n_files} .stream files, {seconds:.0f}s of audio in all
  {cfg['manifest']}               id -> slot -> source take (build manifest)

Source archives: {cfg['archive_note']}
Mapping: voice_lines_vox/miranda_lawson/hila_intent_cuts.csv
Nothing outside this folder is touched: music, radio, other heisters and all vanilla files stay as
they are, except for the shared-bank caveat above.
"""


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def readme_dedicated(pack_id: str, cfg: dict, n_files: int, named: int, picked: int, slots: list[str],
                     seconds: float, unknown_ids: list[str]) -> str:
    named_rel = _rel(cfg["named_ids"])
    return f"""{cfg['install']} (Rust's own bank)

WHAT IT IS
{cfg['target']}'s voice lines, replaced by short {cfg['speaker']} barks: this pack writes
{n_files} files into soundbanks/streamed/char_rust/, Rust's own streamed bank, so it changes Rust
and no other heister. The game plays a line by its id, so the clip answers that line however it is
posted - no event table, no BeardLib, no XAudio.

WHY THIS BANK
Rust is on his own bank (char_rust, {cfg['voice']}); the shared regular_vox ids that the other
packs write are a different set of files. Measured on the reference Rust pack: 1,046 char_rust ids,
none of them shared with regular_vox (D73; the ``char_rust`` tab of voice_lines_vox/vo_master.xlsx). The Marine reference
pack (references/voice/Marine VO for Rust.7z.001) has no regular_vox folder at all on the 64-bit build.

WHAT A DEDICATED BANK COSTS
Id -> line cannot be derived: Wwise stores no name for a streamed file. Every id here was named by
a source (see {named_rel}) - a take is never written to a guessed id. Right now {named} of the
{picked} picked slots have a named id; the rest are vanilla and their takes are not in the zip:
{', '.join(slots) if slots else '(none)'}

REQUIRES
PAYDAY 2 with SuperBLT (or any BLT build). Nothing else: this is a file replacement.

INSTALL
  1. Close PAYDAY 2.
  2. Copy the whole folder "{cfg['install']}" into ...\\PAYDAY 2\\mods\\
     Final check: PAYDAY 2\\mods\\{cfg['install']}\\main.xml must exist. Never nest it twice.
  3. The mod folder marker is main.xml; nothing is configured inside it.

IF NOTHING CHANGES
Check the folder is in mods/ and not nested, that Rust is the heister you are playing, and that no
other pack writes char_rust. The in-game log lines are named in docs/pd2-las/in-game-checklist.md.

CONTENTS
  main.xml                               mod folder marker, nothing to configure
  mod.txt                                BLT mod-list metadata
  soundbanks/streamed/char_rust/         {n_files} .stream files, {seconds:.0f}s of audio in all
  {cfg['manifest']}                id -> slot -> source take (build manifest)

Source archive: {cfg['archive_note']}
Named ids: {named_rel}
Nothing outside this folder is touched.
{f"Unknown ids named by the source (not in the measured bank): {', '.join(unknown_ids)}" if unknown_ids else ""}
"""


def mod_txt(cfg: dict) -> str:
    return (
        "{\n"
        f"\t\"name\" : \"{cfg['install']}\",\n"
        f"\t\"description\" : \"Replaces heister voice lines with short {cfg['speaker']} barks, one streamed .stream file per voice-line id.\",\n"
        "\t\"author\" : \"universal-modder\",\n"
        f"\t\"version\" : \"{cfg['version']}\",\n"
        "\t\"priority\" : 0\n"
        "}\n"
    )


def main_xml(cfg: dict) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<mod name="{escape(cfg["install"])}" version="{cfg["version"]}">\n'
        "  <!-- The soundbanks/ directory is the whole mod: BLT serves the files, the\n"
        "       game reads them by voice-line id. No hooks, no scripts. -->\n"
        "</mod>\n"
    )


def build_one(pack_id: str, cfg: dict, ff: str, args) -> tuple[int, str, int]:
    ids = base.load_ids()
    vorbis = base.load_vorbis_ids()
    picks = load_picks_csv(cfg["picks"])
    slots_in_table = {slot for _id, slot, _a in ids}
    unknown = sorted(set(picks) - slots_in_table)
    if unknown:
        raise SystemExit(f"{pack_id}: picks name slots that are not in the cuts table: "
                         + ", ".join(unknown))

    work = tempfile.TemporaryDirectory(prefix=f"{pack_id}_stream_")
    stage = Path(work.name)
    # by_base: file name -> archive-internal name (first archive in the config wins)
    by_base: dict[str, str] = {}
    for path, enc in cfg["archives"]:
        for name in list_zip_files(path, enc):
            by_base.setdefault(name.split("/")[-1], name)
    missing = sorted({Path(p["source_ogg"]).name for p in picks.values()} - set(by_base))
    if missing:
        raise SystemExit(f"{pack_id}: pick sources not in the archives: " + ", ".join(missing))
    staged = stage_sources({Path(p["source_ogg"]).name for p in picks.values()},
                           cfg["archives"], stage / "src")

    by_name = {name: name for name in staged}
    clip = {}
    for slot in sorted(picks):
        dest, start, end = base.cut_clip(slot, picks[slot], by_name, staged, stage, ff,
                                         normalize=not args.no_normalize)
        pcm = base.pcm_mono(dest, ff)
        blob = wwise_ima.encode(pcm, 1)
        channels, rate, _data = wwise_ima.read(blob)
        assert channels == 1 and rate == wwise_ima.SAMPLE_RATE
        clip[slot] = (blob, start, end, pcm.shape[0] / wwise_ima.SAMPLE_RATE,
                      pcm.shape[0] // wwise_ima.FRAMES * wwise_ima.FRAMES)

    install = cfg["install"] + "/"
    files = {
        install + "main.xml": main_xml(cfg).encode("utf-8"),
        install + "mod.txt": mod_txt(cfg).encode("utf-8"),
    }
    manifest = io.StringIO()
    w = csv.writer(manifest, lineterminator="\n")
    w.writerow(["hila_id", "slot", "also_slots", "cut_line", "source_ogg", "t_start", "t_end",
                "clip_s", "frames", "stream_bytes", "skipped"])
    seconds = 0.0
    written = 0
    n_uncovered_ids = 0
    for hila_id, slot, also in ids:
        pick = picks.get(slot)
        if pick is None:
            skipped = f"no take in {cfg['archive_note']}; left vanilla"
            blob, start, end, clip_s, frames = b"", 0.0, 0.0, 0.0, 0
        elif hila_id in vorbis and not args.include_vorbis_ids:
            blob, start, end, clip_s, frames = clip[slot]
            skipped = "vorbis id left vanilla"
        else:
            blob, start, end, clip_s, frames = clip[slot]
            skipped = ""
        if pick is None:
            n_uncovered_ids += 1
        if not skipped:
            files[f"{install}{BANK}/{hila_id}.stream"] = blob
            seconds += clip_s
            written += 1
        src_pick = pick or {}
        w.writerow([hila_id, slot, also, src_pick.get("cut_line", ""), src_pick.get("source_ogg", ""),
                    f"{start:.3f}", f"{end:.3f}", f"{clip_s:.3f}", frames, len(blob), skipped])

    # slot-level uncovered count for the readme
    n_uncovered = len(slots_in_table - set(picks))
    files[install + cfg["manifest"]] = manifest.getvalue().encode("utf-8")
    uncovered_ids_note = n_uncovered_ids
    files[install + "README.txt"] = readme(pack_id, cfg, written, len(ids), len(vorbis), seconds,
                                           n_uncovered, uncovered_ids_note).encode("utf-8")

    out = Path(args.out) if args.out else cfg["out"]
    size, sha = base.write_zip(out, files)
    print(f"wrote {out} ({size} bytes) sha256={sha[:12]}… streams={written} "
          f"ids={len(ids)} slots={len(clip)} uncovered_slots={n_uncovered} "
          f"uncovered_ids={n_uncovered_ids} audio={seconds:.0f}s")
    return len(files), sha, written


def build_dedicated(pack_id: str, cfg: dict, bank: str, ff: str, args) -> tuple[int, str, int]:
    """One pack on a dedicated bank: the same picks, the ids a source named, nothing guessed."""
    folder = bank_folder(bank)
    measured_path = VOX / "targets" / f"{cfg['bank_target']}_dedicated_{bank}.csv"
    measured = {r["id"] for r in csv.DictReader(measured_path.open(newline="", encoding="utf-8"))} \
        if measured_path.is_file() else set()
    if not measured:
        raise SystemExit(f"{pack_id}: no measured table for {bank} at {measured_path}; run "
                         "tools/build_stream_tables.py --bank dedicated --dedicated <reference mod>")
    named = load_named_ids(cfg["named_ids"])
    picks = load_picks_csv(cfg["picks"])
    picked = {slot for slot in picks}
    missing = sorted(picked - set(named))
    if missing:
        raise SystemExit(
            f"{pack_id} --bank {bank}: {len(missing)} of {len(picked)} picked slots have no named "
            f"voice-line id. A dedicated bank's ids cannot be derived (Wwise strips every name), so "
            f"fill voice_lines_vox/geralt/char_rust_ids.csv from a source that names them - "
            f"appending whole takes to the measured ids would play the wrong line.\n"
            f"  unnamed slots: {', '.join(missing)}\n"
            f"  no published source names a char_rust id for a heister slot; the reference Marine "
            f"pack names only the medic-kill bark, and only by event (g36x_any), not by id")
    unknown = sorted(set(named.values()) - measured)
    if unknown:
        raise SystemExit(f"{pack_id}: ids not in the measured {bank} table: " + ", ".join(unknown))

    work = tempfile.TemporaryDirectory(prefix=f"{pack_id}_{bank}_")
    stage = Path(work.name)
    by_base = {}
    for path, enc in cfg["archives"]:
        for name in list_zip_files(path, enc):
            by_base.setdefault(name.split("/")[-1], name)
    staged = stage_sources({Path(p["source_ogg"]).name for p in picks.values()}, cfg["archives"],
                           stage / "src")
    by_name = {name: name for name in staged}
    install = cfg["install"] + "/"
    files = {install + "main.xml": main_xml(cfg).encode("utf-8"),
             install + "mod.txt": mod_txt(cfg).encode("utf-8")}
    manifest = io.StringIO()
    w = csv.writer(manifest, lineterminator="\n")
    w.writerow(["id", "bank", "slot", "cut_line", "source_ogg", "t_start", "t_end", "clip_s",
                "frames", "stream_bytes", "named_by"])
    seconds = 0.0
    for slot in sorted(named):
        if slot not in picks:
            continue
        dest, start, end = base.cut_clip(slot, picks[slot], by_name, staged, stage, ff,
                                         normalize=not args.no_normalize)
        pcm = base.pcm_mono(dest, ff)
        blob = wwise_ima.encode(pcm, 1)
        channels, rate, _data = wwise_ima.read(blob)
        assert channels == 1 and rate == wwise_ima.SAMPLE_RATE
        clip_s = pcm.shape[0] / wwise_ima.SAMPLE_RATE
        files[f"{install}{folder}/{named[slot]}.stream"] = blob
        seconds += clip_s
        w.writerow([named[slot], Path(folder).name, slot, picks[slot].get("cut_line", ""),
                    picks[slot].get("source_ogg", ""), f"{start:.3f}", f"{end:.3f}", f"{clip_s:.3f}",
                    pcm.shape[0] // wwise_ima.FRAMES * wwise_ima.FRAMES, len(blob),
                    _rel(cfg["named_ids"])])
    files[install + cfg["manifest"]] = manifest.getvalue().encode("utf-8")
    n_written = len([slot for slot in named if slot in picks])
    files[install + "README.txt"] = readme_dedicated(
        pack_id, cfg, n_written, len(picked & set(named)), len(picked),
        sorted(picked - set(named)), seconds, unknown).encode("utf-8")
    out = Path(args.out) if args.out else cfg["out"]
    size, sha = base.write_zip(out, files)
    written = sum(1 for name in files if name.endswith(".stream"))
    print(f"wrote {out} ({size} bytes) sha256={sha[:12]}… streams={written} bank={Path(folder).name} "
          f"slots={len(picked)} audio={seconds:.0f}s")
    return len(files), sha, written


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack", choices=list(PACKS) + ["all"], default="all")
    p.add_argument("--out", type=Path, default=None,
                   help="override the output path (valid only with a single --pack)")
    p.add_argument("--no-normalize", action="store_true")
    p.add_argument("--include-vorbis-ids", action="store_true")
    p.add_argument("--bank", choices=sorted(BANKS), default="shared",
                   help="shared: the regular_vox ids (what ships); char_rust: Rust's own bank, "
                        "which needs voice_lines_vox/geralt/char_rust_ids.csv to name every id")
    args = p.parse_args(argv)
    determinism.enter(__file__)
    if args.out and args.pack == "all":
        raise SystemExit("--out only makes sense with a single --pack")
    ff = vo.ffmpeg_bin()
    if ff is None:
        raise SystemExit("ffmpeg is missing (pip install imageio-ffmpeg)")
    if args.bank != "shared" and args.pack == "all":
        raise SystemExit("--bank only makes sense with a single --pack: the bank is per heister")
    for pack_id in (list(PACKS) if args.pack == "all" else [args.pack]):
        if args.bank == "shared":
            build_one(pack_id, PACKS[pack_id], ff, args)
        else:
            build_dedicated(pack_id, PACKS[pack_id], args.bank, ff, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
