#!/usr/bin/env python3
"""Pack Miranda Lawson oggs from references/Голос Лоусон.7z over Hila (rb21).

Reads voice_lines_vox/miranda_lawson/hila_intent_cuts.csv and the original
file-hint column, picks the shortest matching .ogg per intent slot, and writes
a BeardLib SoundsModule zip (OGG, prefix rb21, sound id = PD2 ID).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
import determinism  # noqa: E402  (the pinned numeric code path every builder enters)
CUTS = ROOT / "voice_lines_vox/miranda_lawson/hila_intent_cuts.csv"
MAP = ROOT / "voice_lines_vox/miranda_lawson/hila_to_miranda_mapping.csv"
ARCHIVE = ROOT / "references/Голос Лоусон.7z"
SPLITS = ROOT / "voice_lines_vox/miranda_lawson/ogg_phrase_splits.csv"
PIECES = ROOT / "voice_lines_vox/miranda_lawson/hila_slot_pieces.csv"
PICKS = ROOT / "voice_lines_vox/miranda_lawson/slot_picks.csv"
EVENTS = ROOT / "voice_lines_vox/miranda_lawson/slot_event_ids.csv"
DEFAULT_OUT = ROOT / "dist/Hila/Miranda_Lawson_VO_over_Hila.zip"
INSTALL = "Miranda Lawson VO over Hila"
PREFIX = "rb21"
BARK_MIN = 0.28
BARK_MAX = 1.35
HEAD_CUT = 0.95

# Filename stems that actually sound like the slot (ME2/3 scene), not spreadsheet hints.
# Shorter combat/tutorial/warning barks beat romance/debrief speeches.
INTENT_STEMS: dict[str, tuple[str, ...]] = {
    "ammo.low": ("endgm2_warnings", "endgm2_leaderbarks", "horcr1_spaceport", "cspcr2_escape"),
    "assault.incoming": ("endgm2_warnings", "endgm2_leaderbarks", "horcr1_collector", "cspcr2_platform"),
    "assault.ready": ("endgm2_warnings", "endgm2_leaderbarks", "procer_cover_tutorial"),
    "assault.retreat": ("horcr1_collector_retreat", "endgm2_warnings", "cspcr2_escape"),
    "call_teammate.hey_you": ("norvx_starter", "pronor_illusive", "procer_cover_tutorial"),
    "caution.wait": ("procer_cover_tutorial", "endgm2_warnings", "norvx_starter"),
    "caution.watch": ("endgm2_warnings", "procer_cover_tutorial", "horcr1_ash"),
    "civ.dontmove": ("procer_vixen_briefing", "procer_vixen_intro", "bchlml_fatherfinal"),
    "civ.down": ("procer_vixen_briefing", "procer_vixen_intro"),
    "civ.killthreat": ("procer_vixen_briefing", "bchlml_fatherfinal", "endgm2_boss"),
    "civ.nophone": ("procer_vixen_briefing", "procer_vixen_intro"),
    "civ.talk": ("procer_vixen_briefing", "prscva", "bchlml_fatherfinal"),
    "civ.ties": ("procer_vixen_briefing", "procer_cover_tutorial"),
    "cop.cuffs": ("procer_vixen_intro", "procer_vixen_briefing", "bchlml_fatherfinal"),
    "cop.drop": ("procer_vixen_intro", "procer_vixen_briefing", "endgm2_boss"),
    "cop.hands": ("procer_vixen_intro", "procer_vixen_briefing"),
    "cop.kneel": ("procer_vixen_intro", "procer_vixen_briefing"),
    "cuffed.pick": ("twrvxl_aboutaboy", "bchlml_village", "horcr1"),
    "curse.shit": ("endgm2_warnings", "horcr1_spaceport", "endgm1_warship", "cspcr2_escape"),
    "curse.slow": ("endgm2_warnings", "procer_cover_tutorial", "endgm2_leaderbarks"),
    "downed.need_help": ("horcr1_collector", "horcr1_spaceport", "endgm2_warnings", "bchlml_village"),
    "downed.want_fight": ("horcr1_boss", "endgm2_boss", "endgm2_warnings"),
    "drop.ammo": ("endgm2_warnings", "endgm2_leaderbarks", "cspcr2_escape"),
    "drop.body": ("cspcr2_bodies", "cspcr2_coffin", "endgm2_warnings"),
    "drop.fak": ("norvx_relationship", "endgm2_team", "horcr1_professor"),
    "drop.medic": ("norvx_relationship", "endgm2_team", "horcr1_spaceport"),
    "hurt.hit": ("horcr1_spaceport", "endgm2_warnings", "horcr1_professor"),
    "hurt.medic": ("horcr1_spaceport", "endgm2_warnings", "norvx_relationship"),
    "inspire.faster": ("procer_cover_tutorial", "endgm2_leaderbarks", "norvx_starter"),
    "inspire.get_up": ("endgm2_team", "norvx_relationship", "endgm2_warnings"),
    "inspire.move": ("procer_cover_tutorial", "norvx_starter", "endgm2_leaderbarks"),
    "inspire.run": ("procer_cover_tutorial", "endgm2_warnings", "cspcr2_escape"),
    "kill.cloaker": ("endgm2_boss", "endgm2_leaderbarks", "jnkkga", "horcr1_collector"),
    "kill.dozer": ("endgm2_boss", "endgm2_leaderbarks", "horcr1_collector"),
    "kill.medic": ("endgm2_boss", "endgm2_leaderbarks", "endgm2_warnings"),
    "kill.shield": ("endgm2_boss", "cspcr2_escape", "endgm2_leaderbarks"),
    "kill.sniper": ("endgm2_boss", "endgm2_leaderbarks", "horcr1_collector"),
    "kill.taser": ("profre_mech", "endgm2_boss", "endgm2_leaderbarks"),
    "loot.secured": ("endgm2_teamc_success", "n7_hench", "cspcr2_escape"),
    "mark.camera": ("endgm2_warnings", "procer_cover_tutorial", "cithub_avina"),
    "mark.captain": ("endgm2_leaderbarks", "endgm1_warship", "endgm2_boss"),
    "mark.cloaker": ("endgm2_warnings", "endgm2_leaderbarks", "jnkkga"),
    "mark.dozer": ("endgm2_warnings", "endgm2_leaderbarks", "endgm2_boss"),
    "mark.generic": ("endgm2_warnings", "procer_cover_tutorial", "endgm2_leaderbarks"),
    "mark.guard": ("endgm2_warnings", "procer_cover_tutorial", "horcr1_ash"),
    "mark.medic": ("endgm2_warnings", "endgm2_leaderbarks"),
    "mark.shield": ("endgm2_warnings", "cspcr2_platform", "endgm2_leaderbarks"),
    "mark.sniper": ("endgm2_warnings", "endgm2_leaderbarks", "horcr1_collector"),
    "mark.taser": ("profre_mech", "endgm2_warnings", "endgm2_leaderbarks"),
    "mark.turret": ("endgm2_warnings", "norcvc_conflict", "profre_spaceport"),
    "mask.go": ("pronor_illusive", "norvx_starter", "n7_hench"),
    "move.follow": ("norvx_starter", "procer_cover_tutorial", "pronor"),
    "move.generic": ("norvx_starter", "procer_cover_tutorial"),
    "move.go": ("procer_cover_tutorial", "cspcr2_escape", "norvx_starter"),
    "move.hold": ("procer_cover_tutorial", "endgm2_warnings", "norvx_starter"),
    "move.in": ("norvx_starter", "procer_cover_tutorial"),
    "move.left": ("procer_cover_tutorial",),
    "move.right": ("procer_cover_tutorial",),
    "move.on_me": ("norvx_starter", "procer_cover_tutorial"),
    "move.this_way": ("norvx_starter", "procer_cover_tutorial"),
    "move.up": ("procer_cover_tutorial",),
    "nade.generic": ("endgm2_warnings", "endgm2_boss", "endgm2_leaderbarks"),
    "nade.grenade": ("endgm2_boss", "endgm2_warnings"),
    "nade.smoke": ("endgm2_warnings", "omghub", "horcr1_husks"),
    "nade.tear": ("endgm2_warnings", "horcr1_husks", "horcr1_ash"),
    "pager.clear": ("twrvxl_main_contact", "cithub_avina", "norvx_starter"),
    "pager.cover": ("twrvxl_main_contact", "norvx_relationship", "cithub"),
    "revive.critical": ("norvx_relationship", "endgm2_team"),
    "revive.hold": ("norvx_relationship", "endgm2_team"),
    "revived.thanks": ("norvx_loyalty", "norvx_relationship", "endgm2_team"),
    "spot.generic": ("norvx_starter", "procer_cover_tutorial", "cithub"),
    "spot.place": ("cithub", "norvx_starter", "pronor"),
    "tech.comp": ("gthgtl", "cithub_avina", "twrvxl_main_contact"),
    "tech.drill_jam": ("twrvxl_main_contact", "gthgtl", "horcr1_professor"),
    "tech.drilling": ("twrvxl_main_contact", "procer_cover_tutorial", "gthgtl"),
    "tech.fix": ("twrvxl_oldfriend", "twrvxl_main_contact", "gthgtl"),
    "tech.generic": ("twrvxl_main_contact", "gthgtl", "cithub_avina"),
    "win.generic": ("endgm2_teamc_success", "n7_hench", "endgm2_longwalk"),
}


def import_py7zr():
    """py7zr, with the one-line fix in the message if it is missing."""
    try:
        import py7zr
    except ImportError:
        sys.stderr.write("need py7zr: python3 -m venv .venv && .venv/bin/pip install py7zr\n")
        raise
    return py7zr


def load_cuts():
    with CUTS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_events() -> dict[str, list[str]]:
    """slot -> the PD2 bark event names that slot's clip answers (see the CSV's notes).

    The ids are what PD2 actually posts (`PlayerSound:say(name)`), not the numeric
    voice-line ids of hila_intent_cuts.csv: `<Sounds>` matches on the posted id, and
    the heister is chosen by the `robber` switch (rb21 = Hila), i.e. our prefix.
    """
    with EVENTS.open(newline="", encoding="utf-8") as f:
        return {r["slot"]: [e for e in r["event_ids"].split("|") if e]
                for r in csv.DictReader(f)}


def load_hints():
    hints = {}
    with MAP.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hints[row["hila_id"]] = row.get("miranda_file_hint") or ""
    return hints


def list_archive_oggs():
    import py7zr
    with py7zr.SevenZipFile(ARCHIVE) as z:
        out = []
        for info in z.list():
            if info.filename.endswith(".ogg"):
                out.append((info.uncompressed, info.filename.split("/")[-1], info.filename))
    out.sort()
    return out


def tokens_from_hint(hint: str):
    parts = []
    for chunk in hint.replace(",", " ").replace("/", " ").split():
        t = chunk.strip().strip(".*")
        if len(t) >= 4:
            parts.append(t.lower())
    return parts


def pick_file_for_slot(slot: str, hint: str, oggs, used: set[str]) -> str:
    """Return archive path of a short ogg matching hint tokens, else next unused short file."""
    toks = tokens_from_hint(hint)
    candidates = []
    for size, base, path in oggs:
        b = base.lower()
        if toks and any(t in b for t in toks):
            candidates.append((size, path))
    if not candidates:
        candidates = [(size, path) for size, _b, path in oggs]
    # prefer unused, then smaller
    unused = [c for c in candidates if c[1] not in used]
    pool = unused or candidates
    pool.sort()
    return pool[0][1]


def load_picks() -> dict[str, dict]:
    """Curated slot -> clip overrides (slot_picks.csv); these beat the stem heuristic."""
    out: dict[str, dict] = {}
    if not PICKS.is_file():
        return out
    with PICKS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("slot"):
                out[r["slot"]] = r
    return out


def load_splits():
    """file -> list of (start, end) phrases. Missing files treated as one piece."""
    out = {}
    if not SPLITS.is_file():
        return out
    with SPLITS.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            phrases = []
            for bit in (row.get("phrases") or "").split("|"):
                if "-" not in bit:
                    continue
                a, b = bit.split("-", 1)
                phrases.append((float(a), float(b)))
            out[row["file"]] = phrases or [(0.0, float(row["duration_s"] or 0))]
    return out


def ffmpeg_bin() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def bark_score(start: float, end: float, phrase_index: int) -> float:
    d = end - start
    if d < BARK_MIN:
        return 9.0
    if d > BARK_MAX:
        # still usable if we will head-cut; worse than a natural bark
        return 2.0 + d + phrase_index * 0.05
    # prefer ~0.7s command, first phrase of a longer line
    return abs(d - 0.7) + phrase_index * 0.08


def expand_pieces(archive_path: str, splits: dict):
    """Only first phrase, or a head-cut of a long first phrase. No mid-speech tails."""
    base = Path(archive_path).name
    phrases = splits.get(base)
    if not phrases:
        return [(archive_path, 0, 0.0, None)]
    a, b = phrases[0]
    d = b - a
    if d > BARK_MAX:
        return [(archive_path, 0, a, a + min(HEAD_CUT, d))]
    return [(archive_path, 0, a, b)]


def stem_rank(slot: str, filename: str) -> int:
    stems = INTENT_STEMS.get(slot) or ()
    fn = filename.lower()
    for i, stem in enumerate(stems):
        if stem in fn:
            return i
    return 99


def pick_piece_for_slot(slot, hint, oggs, splits, used_keys):
    """Prefer short first-phrases from the intent's ME scene, not spreadsheet lore hints."""
    pool = []
    for size, base, path in oggs:
        rank = stem_rank(slot, base)
        if rank == 99:
            continue
        for piece in expand_pieces(path, splits):
            _p, idx, a, b = piece
            key = (_p, idx, round(a, 3), round(b, 3) if b is not None else None)
            if key in used_keys:
                continue
            dur = 0.7 if b is None else (b - a)
            # short is good; wrong scene is not
            sc = rank * 3.0 + abs(dur - 0.55) + (0.4 if dur > 1.0 else 0)
            pool.append((sc, dur, key, piece))
    if not pool:
        # reuse a same-scene bark rather than a random other conversation
        for size, base, path in oggs:
            if stem_rank(slot, base) == 99:
                continue
            for piece in expand_pieces(path, splits):
                a, b = piece[2], piece[3]
                dur = 0.7 if b is None else (b - a)
                key = (piece[0], piece[1], round(a, 3), round(b, 3) if b is not None else None)
                pool.append((30 + abs(dur - 0.55), dur, key, piece))
    if not pool:
        # fallback: original hint tokens, first phrase only
        toks = tokens_from_hint(hint)
        for size, base, path in oggs:
            if toks and not any(t in base.lower() for t in toks):
                continue
            for piece in expand_pieces(path, splits):
                key = (piece[0], piece[1], piece[2], piece[3])
                if key in used_keys:
                    continue
                a, b = piece[2], piece[3]
                dur = 0.7 if b is None else (b - a)
                pool.append((10 + abs(dur - 0.55), dur, key, piece))
    if not pool:
        for size, base, path in oggs:
            piece = expand_pieces(path, splits)[0]
            key = (piece[0], piece[1], piece[2], piece[3])
            if key in used_keys:
                continue
            pool.append((20, 0.7, key, piece))
            break
    pool.sort()
    sc, _d, key, piece = pool[0]
    used_keys.add(key)
    return piece, sc


def cut_ogg(src: Path, start: float, end: float, dest: Path, ff: str):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.10, end - start)
    subprocess.run(
        [ff, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
         "-fflags", "+bitexact", "-c:a", "libvorbis", "-q:a", "5", str(dest)],
        check=True, capture_output=True,
    )


TARGET_PEAK = -1.5   # dBFS every bark is matched to
MAX_GAIN = 12.0      # never boost more than this (noise floor)


def peak_db(path: Path, ff: str) -> float | None:
    out = subprocess.run(
        [ff, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    m = re.search(r"max_volume: ([\-\d.]+) dB", out)
    return float(m.group(1)) if m else None


def match_level(path: Path, ff: str) -> float:
    """Bark-to-bark level match: bring the clip's peak to TARGET_PEAK (bounded)."""
    peak = peak_db(path, ff)
    if peak is None:
        return 0.0
    gain = max(-9.0, min(MAX_GAIN, TARGET_PEAK - peak))
    if abs(gain) < 0.5:
        return 0.0
    tmp = path.with_suffix(".norm.ogg")
    subprocess.run(
        [ff, "-y", "-i", str(path), "-af", f"volume={gain:.2f}dB",
         "-fflags", "+bitexact", "-c:a", "libvorbis", "-q:a", "5", str(tmp)],
        check=True, capture_output=True,
    )
    tmp.replace(path)
    return gain


def cut_ogg_ranges(src: Path, ranges: list[tuple[float, float]], dest: Path, ff: str):
    """Concatenate several sub-ranges of one ogg (used to drop a single word)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts, labels = [], []
    for i, (a, b) in enumerate(ranges):
        parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=N/SR/TB[p{i}]")
        labels.append(f"[p{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(ranges)}:v=0:a=1[out]"
    subprocess.run(
        [ff, "-y", "-i", str(src), "-filter_complex", graph, "-map", "[out]",
         "-fflags", "+bitexact", "-c:a", "libvorbis", "-q:a", "5", str(dest)],
        check=True, capture_output=True,
    )


def parse_splits(spec: str) -> list[tuple[float, float]]:
    out = []
    for bit in (spec or "").split("|"):
        if "-" in bit:
            a, b = bit.split("-", 1)
            out.append((float(a), float(b)))
    return out


def extract_selected(paths: set[str], dest: Path) -> dict[str, Path]:
    """Unpack the oggs this build touches; returns archive path -> extracted file."""
    py7zr = import_py7zr()
    dest.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(ARCHIVE) as z:
        targets = [p for p in z.getnames() if p in paths]
        z.extract(targets=targets, path=dest)
    return {p: dest / p for p in targets}


def build_xml(slot_file: dict[str, str], events: dict[str, list[str]]) -> str:
    """One <sound> per PD2 event name; several events may share one clip."""
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<table name="{escape(INSTALL)}">',
        f'  <Sounds directory="sounds" prefix="{PREFIX}" load_on_play="true">',
    ]
    owner: dict[str, str] = {}
    for slot in sorted(slot_file):
        ids = events.get(slot) or []
        if not ids:
            raise SystemExit(f"slot without a PD2 event id: {slot} (voice_lines_vox/miranda_lawson/slot_event_ids.csv)")
        fname = Path(slot_file[slot]).name
        for ev in ids:
            if ev in owner:
                raise SystemExit(f"event id {ev} claimed by both {owner[ev]} and {slot}: one clip must win")
            owner[ev] = slot
            lines.append(f'    <sound id="{escape(ev)}" path="{escape(fname)}" stop_id="{escape(ev)}_stop"/>')
    lines += [
        "  </Sounds>",
        "</table>",
        "",
    ]
    return "\n".join(lines)


def readme(n_events: int, n_clips: int) -> str:
    return f"""{INSTALL}

WHAT IT IS
Replaces Hila's heister barks (voice switch "{PREFIX}") with {n_clips} short Miranda Lawson
clips from Mass Effect, mapped by intent onto {n_events} PD2 bark events.
The <Sounds> node is prefixed rb21 - Hila's voice switch - so only her own barks
change and every other heister keeps their lines.

REQUIRES (both are hard requirements, the pack is silent without them)
  * SuperBLT with the built-in XAudio API  - https://modworkshop.net/mod/58342
  * BeardLib 5.x                           - https://modworkshop.net/mod/14924
BeardLib's Sounds module aborts with "Sounds module requires the XAudio API!"
on plain BLT/BLT4, so SuperBLT really is needed.

INSTALL
  1. Close PAYDAY 2.
  2. Copy the whole folder "{INSTALL}" into
       ...\\Steam\\steamapps\\common\\PAYDAY 2\\mods\\
     Final check: PAYDAY 2\\mods\\{INSTALL}\\main.xml must exist.
     Do not nest it twice (mods\\{INSTALL}\\{INSTALL}\\main.xml is wrong).
  3. Start the game. Main menu -> Mods: this pack and BeardLib are both listed.
     Nothing needs to be toggled - BeardLib picks the pack up from main.xml.
  4. Play a heist with Hila (as your heister, or as an AI teammate).

UNINSTALL
Delete this folder, or untick the pack in the main-menu Mods list.
Only one Hila voice pack should be installed at a time - two packs claiming the
same (id, prefix) pair means the one that loads later wins.

IF YOU HEAR NO CHANGE
Enable BeardLib's "Log Sounds" option (Mods -> BeardLib options), play once, then
open the newest payday2_win32_release_*.log and read the
"Incoming sound check: ID ... Prefixes ..." lines. This build is keyed on PD2's bark
event names (g18, f11e_plu, f30x_any, ...); if the log shows an id that should have
been replaced but was not, add it to slot_event_ids.csv in the source repository -
see docs/pd2-voice-mod-install.md.

CONTENTS
  main.xml                             BeardLib Sounds module config (prefix {PREFIX})
  sounds/                              {n_clips} ogg clips, peak-matched to -1.5 dBFS
  slot_to_ogg.csv, hila_slot_pieces.csv  build manifest (not read by the game)

Source archive: references/\u0413\u043e\u043b\u043e\u0441 \u041b\u043e\u0443\u0441\u043e\u043d.7z
Mapping: voice_lines_vox/miranda_lawson/hila_intent_cuts.csv
Nothing outside this folder is touched: music, radio, other heisters and all
vanilla files stay as they are.
"""


def mod_txt() -> str:
    """BLT metadata: makes the pack show up (and toggle) in the main-menu mod list.

    BeardLib does not need this file - main.xml is what makes it load the folder -
    but BLT's own manager only lists mods that carry a mod.txt.
    """
    return (
        "{\n"
        f"\t\"name\" : \"{INSTALL}\",\n"
        "\t\"description\" : \"Replaces Hila's (rb21) heister barks with short "
        "Miranda Lawson clips from Mass Effect.\",\n"
        "\t\"author\" : \"universal-modder\",\n"
        "\t\"version\" : \"1.0\",\n"
        "\t\"priority\" : 0\n"
        "}\n"
    )


def write_zip(out: Path, files: dict[str, bytes]):
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 11, 23, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    data = buf.getvalue()
    out.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    # The sidecar must name the zip relative to the repo root (tools/pd2-las/status.py
    # validates that path), and fall back to the bare file name outside the repo.
    try:
        name = out.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = out.name
    out.with_suffix(out.suffix + ".sha256").write_text(sha + "  " + name + "\n", encoding="utf-8")
    return len(data), sha


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--no-cut", action="store_true", help="use whole oggs, no phrase splits")
    p.add_argument("--no-normalize", action="store_true",
                   help="skip per-clip level matching to -1.5 dBFS peak")
    p.add_argument("--source-dir", type=Path, default=None,
                   help="optional already-extracted Голос Лоусон folder; "
                        "without it the archive is unpacked into a temporary directory")
    args = p.parse_args(argv)
    determinism.enter(__file__)
    import_py7zr()
    if not ARCHIVE.is_file():
        raise SystemExit(f"missing {ARCHIVE}")
    rows = load_cuts()
    events = load_events()
    hints = load_hints()
    oggs = list_archive_oggs()
    splits = {} if args.no_cut else load_splits()
    slot_hint = {}
    for r in rows:
        if r["slot"] not in slot_hint:
            slot_hint[r["slot"]] = hints.get(r["hila_id"], "")
    used = set()
    slot_file = {}
    slot_piece = {}
    picks = load_picks()
    by_base = {base: path for _size, base, path in oggs}
    for slot in sorted(picks):
        pk = picks[slot]
        base = pk["source_ogg"]
        path = by_base.get(base)
        if path is None:
            print(f"WARN pick source not in archive: {slot} -> {base}")
            continue
        ranges = parse_splits(pk.get("splits", ""))
        if ranges:
            slot_piece[slot] = (path, 0, ranges[0][0], ranges[-1][1], None)
        else:
            slot_piece[slot] = (path, 0, float(pk["t_start"]), float(pk["t_end"]), None)
        slot_file[slot] = path
        used.add(path)
    ff = None if args.no_cut else ffmpeg_bin()
    for slot, hint in sorted(slot_hint.items()):
        if slot in picks:
            continue
        if args.no_cut or not splits:
            path = pick_file_for_slot(slot, hint, oggs, used)
            used.add(path)
            slot_file[slot] = path
            slot_piece[slot] = (path, 0, 0.0, None, 0.0)
        else:
            piece, sc = pick_piece_for_slot(slot, hint, oggs, splits, used)
            path, idx, a, b = piece
            slot_piece[slot] = (path, idx, a, b, sc)
            slot_file[slot] = path
    install = INSTALL + "/"
    files = {
        install + "README.txt": readme(len({e for ids in events.values() for e in ids}),
                                       len(slot_file)).encode("utf-8"),
        install + "mod.txt": mod_txt().encode("utf-8"),
    }
    map_buf = io.StringIO()
    w = csv.writer(map_buf)
    w.writerow(["slot", "cut_line", "archive_file", "piece_index", "t_start", "t_end",
                "duration_s", "score", "event_ids", "gain_db"])
    piece_csv = io.StringIO()
    pw = csv.writer(piece_csv)
    pw.writerow(["slot", "cut_line", "source_ogg", "piece", "t_start", "t_end", "duration_s", "splits"])

    need_paths = {slot_piece[s][0] for s in slot_piece}
    work = tempfile.TemporaryDirectory(prefix="hila_vo_")
    src_root = args.source_dir or Path(work.name)
    extracted = extract_selected(need_paths, Path(work.name))
    pieces_dir = Path(work.name) / "pieces"
    out_sounds = {}

    def locate(path: str, base: str) -> Path | None:
        src = src_root / path
        if src.is_file():
            return src
        hits = list(src_root.rglob(base))  # 7z layout: folder/file
        return hits[0] if hits else None

    for slot in sorted(slot_file):
        path, idx, a, b, sc = slot_piece[slot]
        evs = events.get(slot, [])
        cut = next(r["cut_line"] for r in rows if r["slot"] == slot)
        pk = picks.get(slot)
        ranges = parse_splits(pk.get("splits", "")) if pk else []
        if pk and pk.get("cut_line"):
            cut = pk["cut_line"]
        base = Path(path).name
        src = locate(path, base)
        gain = 0.0
        if ranges and ff is not None and src is not None:
            fname = f"{Path(base).stem}_cut{len(ranges)}.ogg"
            dest = pieces_dir / fname
            cut_ogg_ranges(src, ranges, dest, ff)
            if not args.no_normalize:
                gain = match_level(dest, ff)
            audio = dest.read_bytes()
            t0, t1 = ranges[0][0], ranges[-1][1]
            dur = sum(e - s_ for s_, e in ranges)
        elif b is None or ff is None:
            fname = base
            audio = extracted[path].read_bytes()
            t0, t1, dur = 0.0, 0.0, 0.0
        else:
            fname = f"{Path(base).stem}_p{idx}_{a:.2f}-{b:.2f}.ogg"
            if src is None or not src.is_file():
                fname = base
                audio = extracted[path].read_bytes()
                t0, t1, dur = a, b, b - a
            else:
                dest = pieces_dir / fname
                cut_ogg(src, a, b, dest, ff)
                if not args.no_normalize:
                    gain = match_level(dest, ff)
                audio = dest.read_bytes()
                t0, t1, dur = a, b, b - a
        out_sounds[fname] = audio
        slot_file[slot] = fname
        w.writerow([slot, cut, base, idx, f"{t0:.3f}", f"{t1:.3f}", f"{dur:.3f}",
                    f"{sc:.3f}" if isinstance(sc, float) else "", "|".join(evs),
                    f"{gain:+.1f}"])
        pw.writerow([slot, cut, base, idx, f"{t0:.3f}", f"{t1:.3f}", f"{dur:.3f}",
                     pk.get("splits", "") if pk else ""])
        files[install + "sounds/" + fname] = audio
    files[install + "main.xml"] = build_xml(slot_file, events).encode("utf-8")
    files[install + "slot_to_ogg.csv"] = map_buf.getvalue().encode("utf-8")
    PIECES.parent.mkdir(parents=True, exist_ok=True)
    PIECES.write_text(piece_csv.getvalue(), encoding="utf-8")
    files[install + "hila_slot_pieces.csv"] = piece_csv.getvalue().encode("utf-8")
    size, sha = write_zip(args.out, files)
    print(f"wrote {args.out} ({size} bytes) sha256={sha[:12]}… clips={len(slot_file)} "
          f"events={len({e for ids in events.values() for e in ids})}")


if __name__ == "__main__":
    main()
