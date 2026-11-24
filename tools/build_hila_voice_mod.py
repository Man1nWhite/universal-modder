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
import os
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
CUTS = ROOT / "voice_lines_vox/miranda_lawson/hila_intent_cuts.csv"
MAP = ROOT / "voice_lines_vox/miranda_lawson/hila_to_miranda_mapping.csv"
ARCHIVE = ROOT / "references/Голос Лоусон.7z"
SPLITS = ROOT / "voice_lines_vox/miranda_lawson/ogg_phrase_splits.csv"
PIECES = ROOT / "voice_lines_vox/miranda_lawson/hila_slot_pieces.csv"
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


def _need_py7zr():
    try:
        import py7zr  # noqa: F401
    except ImportError:
        sys.stderr.write("need py7zr: python3 -m venv /tmp/voxvenv && /tmp/voxvenv/bin/pip install py7zr\n")
        raise


def load_cuts():
    with CUTS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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
    dur = max(0.2, end - start)
    subprocess.run(
        [ff, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
         "-c:a", "libvorbis", "-q:a", "5", str(dest)],
        check=True, capture_output=True,
    )


def extract_selected(paths: set[str]) -> dict[str, bytes]:
    import py7zr
    data = {}
    with py7zr.SevenZipFile(ARCHIVE) as z:
        targets = [p for p in z.getnames() if p in paths]
        bio = io.BytesIO()
        # extract to memory via temp
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            z.extract(targets=targets, path=td)
            for p in targets:
                fp = Path(td) / p
                data[p] = fp.read_bytes()
    return data


def build_xml(rows, slot_file: dict[str, str]) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<table name="{escape(INSTALL)}">',
        f'  <Sounds directory="sounds" prefix="{PREFIX}" load_on_play="true">',
    ]
    for r in rows:
        hid = r["hila_id"]
        slot = r["slot"]
        fname = Path(slot_file[slot]).name
        lines.append(
            f'    <sound id="{escape(hid)}" path="{escape(fname)}" stop_id="{escape(hid)}_stop"/>'
        )
    lines += [
        "  </Sounds>",
        "</table>",
        "",
    ]
    return "\n".join(lines)


def readme(n_ids: int, n_clips: int) -> str:
    return f"""{INSTALL}

Requires SuperBLT + BeardLib. Extract the '{INSTALL}' folder into
PAYDAY 2/mods/  (or assets/mod_overrides/ if BeardLib loads overrides).

Replaces Hila's heister barks (voice prefix {PREFIX}) with {n_clips} short
Miranda Lawson clips from Mass Effect, mapped by intent onto {n_ids} PD2 sound IDs.

Source archive: references/Голос Лоусон.7z
Mapping: voice_lines_vox/miranda_lawson/hila_intent_cuts.csv

Does not replace music, radio, or other heisters. Remove the folder to uninstall.
"""


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
    out.with_suffix(out.suffix + ".sha256").write_text(sha + "  " + out.name + "\n", encoding="utf-8")
    return len(data), sha


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--no-cut", action="store_true", help="use whole oggs, no phrase splits")
    p.add_argument("--source-dir", type=Path, default=Path("/tmp/lawson_all"),
                   help="extracted Голос Лоусон folder for ffmpeg cuts")
    args = p.parse_args(argv)
    _need_py7zr()
    if not ARCHIVE.is_file():
        raise SystemExit(f"missing {ARCHIVE}")
    rows = load_cuts()
    hints = load_hints()
    oggs = list_archive_oggs()
    splits = {} if args.no_cut else load_splits()
    slot_hint = {}
    slot_ids = defaultdict(list)
    for r in rows:
        slot_ids[r["slot"]].append(r["hila_id"])
        if r["slot"] not in slot_hint:
            slot_hint[r["slot"]] = hints.get(r["hila_id"], "")
    used = set()
    slot_file = {}
    slot_piece = {}
    ff = None if args.no_cut else ffmpeg_bin()
    for slot, hint in sorted(slot_hint.items()):
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
        install + "README.txt": readme(len(rows), len(slot_file)).encode("utf-8"),
    }
    map_buf = io.StringIO()
    w = csv.writer(map_buf)
    w.writerow(["slot", "cut_line", "archive_file", "piece_index", "t_start", "t_end",
                "duration_s", "score", "uses", "example_ids"])
    piece_csv = io.StringIO()
    pw = csv.writer(piece_csv)
    pw.writerow(["slot", "cut_line", "source_ogg", "piece", "t_start", "t_end", "duration_s"])

    need_paths = {slot_piece[s][0] for s in slot_piece}
    extracted = extract_selected(need_paths)
    src_root = args.source_dir
    out_sounds = {}
    for slot in sorted(slot_file):
        path, idx, a, b, sc = slot_piece[slot]
        ids = slot_ids[slot]
        cut = next(r["cut_line"] for r in rows if r["slot"] == slot)
        base = Path(path).name
        if b is None or ff is None:
            fname = base
            audio = extracted[path]
            t0, t1, dur = 0.0, 0.0, 0.0
        else:
            fname = f"{Path(base).stem}_p{idx}_{a:.2f}-{b:.2f}.ogg"
            src = src_root / path
            if not src.is_file():
                # 7z layout: folder/file
                hits = list(src_root.rglob(base))
                src = hits[0] if hits else None
            if src is None or not src.is_file():
                fname = base
                audio = extracted[path]
                t0, t1, dur = a, b, b - a
            else:
                dest = Path("/tmp/hila_pieces") / fname
                cut_ogg(src, a, b, dest, ff)
                audio = dest.read_bytes()
                t0, t1, dur = a, b, b - a
        out_sounds[fname] = audio
        slot_file[slot] = fname
        w.writerow([slot, cut, base, idx, f"{t0:.3f}", f"{t1:.3f}", f"{dur:.3f}",
                    f"{sc:.3f}" if isinstance(sc, float) else "", len(ids), "|".join(ids[:4])])
        pw.writerow([slot, cut, base, idx, f"{t0:.3f}", f"{t1:.3f}", f"{dur:.3f}"])
        files[install + "sounds/" + fname] = audio
    files[install + "main.xml"] = build_xml(rows, slot_file).encode("utf-8")
    files[install + "slot_to_ogg.csv"] = map_buf.getvalue().encode("utf-8")
    PIECES.parent.mkdir(parents=True, exist_ok=True)
    PIECES.write_text(piece_csv.getvalue(), encoding="utf-8")
    files[install + "hila_slot_pieces.csv"] = piece_csv.getvalue().encode("utf-8")
    size, sha = write_zip(args.out, files)
    print(f"wrote {args.out} ({size} bytes) sha256={sha[:12]}… clips={len(slot_file)} ids={len(rows)}")


if __name__ == "__main__":
    main()
