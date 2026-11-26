#!/usr/bin/env python3
"""Write the per-character ``.stream`` id tables for the VO mods: Rust and Old Hoxton first.

What this answers, and what it does not: the game plays a heister line by streaming
``soundbanks/streamed/<bank>/<id>.stream``, and Wwise keeps no name for the audio, only the
numeric id. So a **stream table** is ``intent slot -> bank folder -> the voice-line ids that
slot's file must be written under`` — one table per heister. The slot -> *bark event* table
(``slot_event_ids.csv``) is a different thing: it names what the game posts, not which file
the game reads, and keying a pack on it is the route that failed silently in game (D61).

Two banks exist for a heister, and they are not interchangeable:

* **shared** — ``regular_vox``. The original crew bark from it, so every pack that writes it
  replaces those lines for *everyone* on the bank. The repo's three VO packs are all this kind,
  and they write the same shared ids.
* **dedicated** — ``char_<heister>``. Newer heisters stream from their own folder, with their
  own numeric ids (measured on two reference packs: 0 ids shared with ``regular_vox``).

Whether Rust plays his *heister* barks from ``regular_vox`` or from ``char_rust`` is the open
question of D71, and this script does not guess it. The shared table is generated per target.
A dedicated table is only ever read out of a real reference pack, because a dedicated bank's
ids cannot be derived — Wwise strips every name, so the only honest source of "which id is
``kill.taser`` for this heister" is a mod that already replaced that exact file.

Nothing here builds audio or touches `dist/`: the output is two text tables derived from the
tracked CSVs, so it does not enter the numeric code path `determinism.enter` guards.

    python tools/build_stream_tables.py                          # both targets, shared bank
    python tools/build_stream_tables.py --target rust --bank dedicated \\
        --dedicated path/to/reference-mod.zip                     # an extracted folder, .zip or .7z

Output (tracked, so a table can be read without building anything):

    voice_lines_vox/targets/rust_shared_regular_vox.csv
    voice_lines_vox/targets/old_hoxton_shared_regular_vox.csv
    voice_lines_vox/targets/<target>_dedicated_char_<heister>.csv   (only with --bank dedicated)

A dedicated row carries the id and the bank it was measured in; its ``slot`` stays empty until
the reference pack's own accounting names it, and the row is useful as-is (that id is that
heister's, under that folder) which is what a later annotation starts from.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_hila_stream_mod as hila  # noqa: E402  (load_ids, load_vorbis_ids, the shared ids)

SHARED = "regular_vox"
OUT = ROOT / "voice_lines_vox" / "targets"

#: The heisters the fork ships a VO pack for. `voice` is the Wwise `robber` switch value (the
#: speaker switch, not a file name, docs/pd2-voice-mod-install.md §4c); `model` is the unit the
#: head packs already target; `bank` is the dedicated folder for the heisters that have one.
TARGETS = {
    "rust": {
        "heister": "Rust",
        "model": "npc_criminal_wild_1",
        "voice": "rb16",
        "bank": "char_rust",
        "pack": "Geralt_VO_over_Rust_Stream.zip",
        "picks": "voice_lines_vox/geralt/slot_picks.csv",
        "dedicated": "a reference Rust VO mod ships `char_rust` (1046 ids), but whether his heister "
                     "barks stream from it or from the shared bank is not documented anywhere",
    },
    "old-hoxton": {
        "heister": "Old Hoxton",
        "model": "npc_criminals_suit_1",
        "voice": "rb5",
        "bank": "char_hoxton",
        "pack": "Arivus_VO_over_Hoxton_Stream.zip",
        "picks": "voice_lines_vox/arivus/slot_picks.csv",
        "dedicated": "no dedicated bank is listed for Old Hoxton in the community Wwise bank dump, "
                     "and the shared bank is what his packs replace; the folder name is a "
                     "hypothesis for a measurement, not a known bank",
    },
}

HEADER = ["slot", "bank", "id", "vanilla_kind", "written", "target", "model",
          "dedicated_bank", "note"]


def load_picks(rel: str) -> set[str]:
    path = ROOT / rel
    if not path.is_file():
        raise SystemExit(f"missing {path} (the target's slot_picks.csv)")
    with path.open(newline="", encoding="utf-8") as f:
        return {r["slot"].strip() for r in csv.DictReader(f) if r.get("slot")}


def write_shared(target: str) -> Path:
    cfg = TARGETS[target]
    picks = load_picks(cfg["picks"])
    vorbis = hila.load_vorbis_ids()
    rows = []
    for hila_id, slot, also in hila.load_ids():
        if hila_id in vorbis:
            note = "the vanilla bank streams this id as Wwise Vorbis; an ADPCM pack cannot write it"
            written = "no"
        elif slot in picks:
            note = f"written by {cfg['pack']}"
            written = "yes"
        else:
            note = f"no take for this slot in the {cfg['heister']} set; left vanilla"
            written = "no"
        if also:
            note += f"; the id also answers {also}"
        rows.append({
            "slot": slot,
            "bank": SHARED,
            "id": hila_id,
            "vanilla_kind": "vorbis" if hila_id in vorbis else "adpcm",
            "written": written,
            "target": cfg["heister"],
            "model": cfg["model"],
            "dedicated_bank": cfg["bank"],
            "note": note,
        })
    path = OUT / f"{target.replace('-', '_')}_shared_{SHARED}.csv"
    _write(path, rows)
    return path


def write_dedicated(target: str, archive: Path) -> Path:
    """The dedicated bank's ids, read out of a reference mod that already writes them."""
    cfg = TARGETS[target]
    bank = cfg["bank"]
    names = [n.replace("\\", "/") for n in _member_names(archive)]
    ids = sorted({n.split("/")[-1].split(".")[0] for n in names
                  if f"/{bank}/" in n and n.lower().endswith(".stream")},
                 key=lambda s: (len(s), s))
    if not ids:
        raise SystemExit(f"{archive} has no soundbanks/streamed/{bank}/*.stream members")
    rows = [{
        "slot": "",
        "bank": bank,
        "id": i,
        "vanilla_kind": "",
        "written": "",
        "target": cfg["heister"],
        "model": cfg["model"],
        "dedicated_bank": bank,
        "note": f"dedicated-bank id measured in {archive.name}; the slot it answers is unknown, "
                f"so keep the file name as it is",
    } for i in ids]
    path = OUT / f"{target.replace('-', '_')}_dedicated_{bank}.csv"
    _write(path, rows)
    return path


def _member_names(archive: Path) -> list[str]:
    if archive.is_dir():
        return [p.relative_to(archive).as_posix() for p in archive.rglob("*") if p.is_file()]
    if re.search(r"\.7z(\.\d{3})?$", archive.name, re.IGNORECASE):
        import py7zr  # hila_voice_clips.import_py7zr prints the install line when this is missing
        volumes = _volumes(archive)
        if len(volumes) == 1:
            with py7zr.SevenZipFile(archive) as z:
                return z.getnames()
        with tempfile.TemporaryDirectory() as tmp:
            joined = Path(tmp) / "joined.7z"
            with joined.open("wb") as out:
                for volume in volumes:
                    out.write(volume.read_bytes())
            with py7zr.SevenZipFile(joined) as z:
                return z.getnames()
    try:
        with zipfile.ZipFile(archive) as z:
            return z.namelist()
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"{archive}: not a .zip/.7z archive or a folder ({exc})") from exc


def _volumes(archive: Path) -> list[Path]:
    """`x.7z.001` + `.002` … in order, or the archive itself when it is not a split volume."""
    if not re.search(r"\.7z\.\d{3}$", archive.name, re.IGNORECASE):
        return [archive]
    stem = archive.name[: -len(archive.suffix)]
    parts = sorted(archive.parent.glob(f"{stem}.*"))
    return parts or [archive]


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", choices=sorted(TARGETS), action="append",
                    help="repeatable; default: every target")
    ap.add_argument("--bank", choices=[SHARED, "dedicated"], default=SHARED,
                    help="regular_vox is generated; dedicated needs --dedicated")
    ap.add_argument("--dedicated", type=Path, action="append", default=[],
                    help="a reference mod (extracted folder, .zip or .7z) that already writes the "
                         "target's dedicated char_<heister> bank")
    args = ap.parse_args(argv)
    for target in args.target or sorted(TARGETS):
        if args.bank == SHARED:
            print(write_shared(target).relative_to(ROOT).as_posix())
            continue
        if not args.dedicated:
            raise SystemExit("--bank dedicated needs --dedicated <reference mod>")
        for archive in args.dedicated:
            print(write_dedicated(target, archive).relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
