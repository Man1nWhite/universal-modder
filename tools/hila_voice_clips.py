#!/usr/bin/env python3
"""The clip half of the Miranda-over-Hila voice packs: pick, cut, level-match.

Miranda Lawson's barks live in `references/Голос Лоусон.7z` as ~870 oggs of whole
scenes. `voice_lines_vox/miranda_lawson/hila_intent_cuts.csv` says which Hila slot
answers which intent; `slot_picks.csv` is the hand-picked (source ogg, window, phrase
splits) per slot, and the file-hint column plus the stem heuristic below are only a
fallback for a slot nobody has picked. This module turns that into cut, level-matched
clips at `-1.5 dBFS` and nothing else - no packaging.

The pack that ships is `tools/build_hila_stream_mod.py`, one Wwise IMA ADPCM `.stream`
per Hila voice-line id. It imports this module for the archive, cut and level helpers.
The BeardLib `SoundsModule` pack that used to ship beside it was dropped on
2026-11-25 (D61); its builder was the other half of this file, and `main()` here now
only refreshes the tracked `hila_slot_pieces.csv` build manifest.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
import determinism  # noqa: E402  (the pinned numeric code path every builder enters)
CUTS = ROOT / "voice_lines_vox/miranda_lawson/hila_intent_cuts.csv"
MAP = ROOT / "voice_lines_vox/miranda_lawson/hila_to_miranda_mapping.csv"
ARCHIVE = ROOT / "references/Голос Лоусон.7z"
#: purpose-authored Mira takes for individual slots (TTS); slot-keyed by file name
MIRA_ARCHIVE = ROOT / "references/LAWSON VOICE (PAYDAY 2).7z"
#: slots deliberately left vanilla: semantic fit < 8 and no take in either archive
REMOVED = ROOT / "voice_lines_vox/miranda_lawson/removed_slots.csv"
SPLITS = ROOT / "voice_lines_vox/miranda_lawson/ogg_phrase_splits.csv"
PIECES = ROOT / "voice_lines_vox/miranda_lawson/hila_slot_pieces.csv"
PICKS = ROOT / "voice_lines_vox/miranda_lawson/slot_picks.csv"
EVENTS = ROOT / "voice_lines_vox/miranda_lawson/slot_event_ids.csv"
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


def list_mira_files():
    """The purpose-authored Mira takes, MP3s from the LAWSON VOICE (PAYDAY 2) archive."""
    import py7zr
    with py7zr.SevenZipFile(MIRA_ARCHIVE) as z:
        out = []
        for info in z.list():
            if info.filename.lower().endswith(".mp3"):
                out.append((info.uncompressed, info.filename.split("/")[-1], info.filename))
    out.sort()
    return out


def load_removed():
    """slots the pack does not answer: semantic fit < 8, no take in either archive.

    Kept in `removed_slots.csv` (with the clip they replaced); the builders refuse
    to write those ids and leave them for the vanilla Hila line.
    """
    out = {}
    if not REMOVED.is_file():
        return out
    with REMOVED.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("slot"):
                out[r["slot"]] = r
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
    """Unpack the sources this build touches; returns archive member -> extracted file."""
    py7zr = import_py7zr()
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for archive in (ARCHIVE, MIRA_ARCHIVE):
        if not archive.is_file():
            continue
        with py7zr.SevenZipFile(archive) as z:
            targets = [p for p in z.getnames() if p in paths]
            if targets:
                z.extract(targets=targets, path=dest)
            out.update({p: dest / p for p in targets})
    return out


def manifest_rows(rows, picks, oggs, splits) -> list[list[str]]:
    """The `hila_slot_pieces.csv` body: one row per slot, the pick it resolves to.

    Columns match what `fit_hila_intents.py` writes, because that script can also
    regenerate this file: slot, cut line, source ogg, piece index, window, duration
    and the phrase splits. A slot without a curated pick falls back to the same
    heuristic the builders use.
    """
    slot_piece = {}
    slot_file = {}
    used: set[str] = set()
    removed = load_removed()
    picks = {s: p for s, p in picks.items() if s not in removed}
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
            slot_piece[slot] = (path, 0, ranges[0][0], ranges[-1][1])
        else:
            slot_piece[slot] = (path, 0, float(pk["t_start"]), float(pk["t_end"]))
        slot_file[slot] = path
        used.add(path)
    for row in rows:
        slot = row["slot"]
        if slot in removed or slot in slot_file:
            continue
        piece = pick_piece_for_slot(slot, "", oggs, splits, used)
        path, idx, a, b, _score = piece
        slot_piece[slot] = (path, idx, a, b)
        slot_file[slot] = path
    # one row per slot: the cut table is per voice-line id, and several ids answer
    # the same slot; the first row's cut line is the one the slot's clip is cut for
    cut_line: dict[str, str] = {}
    for row in rows:
        cut_line.setdefault(row["slot"], row["cut_line"])
    out = [["slot", "cut_line", "source_ogg", "piece", "t_start", "t_end", "duration_s", "splits"]]
    for slot in sorted(slot_piece):
        path, idx, a, b = slot_piece[slot]
        cut = cut_line.get(slot, "")
        pk = picks.get(slot)
        if pk and pk.get("cut_line"):
            cut = pk["cut_line"]
        # a spliced pick is as long as its pieces, not as long as the span it covers
        ranges = parse_splits(pk.get("splits", "")) if pk else []
        heard = sum(e - s_ for s_, e in ranges) if ranges else b - a
        out.append([slot, cut, Path(path).name, idx, f"{a:.3f}", f"{b:.3f}",
                    f"{heard:.3f}", pk.get("splits", "") if pk else ""])
    return out


def main(argv=None) -> int:
    """Refresh `voice_lines_vox/miranda_lawson/hila_slot_pieces.csv` (nothing is packaged).

    No ffmpeg and no cutting: this is the plan the builders cut from, and the file
    `fit_hila_intents.py` can also write.
    """
    p = argparse.ArgumentParser(description=main.__doc__)
    p.add_argument("--out", type=Path, default=PIECES)
    args = p.parse_args(argv)
    determinism.enter(__file__)
    if not ARCHIVE.is_file():
        raise SystemExit(f"missing {ARCHIVE}")
    oggs = list_archive_oggs() + list_mira_files()
    rows = manifest_rows(load_cuts(), load_picks(), oggs, load_splits())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(buf.getvalue(), encoding="utf-8")
    print(f"wrote {args.out} ({len(rows) - 1} slots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
