"""The keying contract of the `.stream` Hila voice pack: voice-line id -> game file name.

This pack replaces lines by the numeric id the game streams, so its whole contract is
"one file per id, named after the id, in Hila's bank" plus the ids it must *not* write
(the ones the vanilla bank streams as Wwise Vorbis). These tests read the tracked CSVs
and, when `dist/` is present, the built zip - no ffmpeg and no py7zr.
"""
from __future__ import annotations

import csv
import json
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_hila_stream_mod as pack  # noqa: E402
import wwise_ima  # noqa: E402
from dist_paths import dist_path  # noqa: E402

DIR = ROOT / "voice_lines_vox" / "miranda_lawson"
PACK = dist_path(ROOT, "Miranda_Lawson_VO_over_Hila_Stream.zip")
FOLDER = pack.INSTALL + "/"
BANK = pack.BANK + "/"


def test_generated_readme_describes_the_single_shipped_route():
    """The install notes inside the zip must not advertise the removed BeardLib pack."""
    readme = pack.readme(858, 885, 27, 665)
    assert "This stream pack leaves those lines vanilla" in readme
    assert "unless the BeardLib pack" not in readme
    assert "the other zip" not in readme


def test_every_voice_line_id_is_numeric_and_answers_exactly_one_slot():
    ids = pack.load_ids()
    assert len(ids) == 885
    assert all(hila_id.isdigit() for hila_id, _slot, _also in ids)
    assert len({hila_id for hila_id, _s, _a in ids}) == len(ids), "an id appears twice"
    # Two ids answer two slots each; the file can only hold one line and the other
    # slot is recorded, not silently dropped.
    two_slots = [row for row in ids if row[2]]
    assert len(two_slots) == 2, two_slots
    assert all(not row[2].startswith("|") and "|" not in row[2] for row in two_slots)


def test_every_slot_the_ids_use_asks_for_a_curated_clip():
    picks = pack.vo.load_picks()
    slots = {slot for _id, slot, _also in pack.load_ids()}
    missing = sorted(slots - picks.keys())
    assert not missing, f"slots without a clip in slot_picks.csv: {missing}"


def test_the_ids_an_adpcm_file_cannot_replace_are_known_and_inside_the_table():
    vorbis = pack.load_vorbis_ids()
    ids = {hila_id for hila_id, _s, _a in pack.load_ids()}
    assert len(vorbis) == 27
    assert set(vorbis) <= ids, sorted(set(vorbis) - ids)
    assert all(note for note in vorbis.values()), "every skipped id says why"
    with (DIR / "hila_vorbis_ids.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["hila_id"] for r in rows] == sorted(vorbis, key=int), "the CSV is in id order"


@pytest.mark.skipif(not PACK.is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_the_pack_holds_one_stream_per_id_except_the_vorbis_ids():
    ids = {hila_id for hila_id, _s, _a in pack.load_ids()}
    skipped = set(pack.load_vorbis_ids())
    with zipfile.ZipFile(PACK) as z:
        names = z.namelist()
    streams = [n for n in names if n.startswith(FOLDER + BANK)]
    assert {Path(n).stem for n in streams} == ids - skipped
    assert all(n.endswith(".stream") for n in streams), "the bank holds nothing else"
    assert len(streams) == len(ids) - len(skipped) == 858


@pytest.mark.skipif(not PACK.is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_every_stream_is_mono_ima_adpcm_at_44100_in_whole_blocks():
    with zipfile.ZipFile(PACK) as z:
        for name in [n for n in z.namelist() if n.endswith(".stream")]:
            blob = z.read(name)
            channels, rate, data = wwise_ima.read(blob)
            assert (channels, rate) == (1, wwise_ima.SAMPLE_RATE), name
            assert blob[:64] == wwise_ima.header(1, len(data)), f"{name} has a foreign header"
            assert len(data) % wwise_ima.SUBBLOCK == 0


@pytest.mark.skipif(not PACK.is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_the_manifest_in_the_pack_agrees_with_what_is_in_it():
    with zipfile.ZipFile(PACK) as z:
        rows = list(csv.DictReader(z.read(FOLDER + "hila_stream_map.csv").decode("utf-8").splitlines()))
        streams = {Path(n).stem: len(z.read(n)) for n in z.namelist() if n.endswith(".stream")}
    assert [r["hila_id"] for r in rows] == [hila_id for hila_id, _s, _a in pack.load_ids()]
    for row in rows:
        written = row["hila_id"] in streams
        assert written == (not row["skipped"]), row
        if written:
            assert streams[row["hila_id"]] == int(row["stream_bytes"]), row
            assert int(row["frames"]) % wwise_ima.FRAMES == 0, row


@pytest.mark.skipif(not PACK.is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_the_pack_writes_no_vorbis_and_no_other_bank():
    with zipfile.ZipFile(PACK) as z:
        names = z.namelist()
        for name in [n for n in names if n.endswith(".stream")]:
            blob = z.read(name)
            assert struct.unpack("<H", blob[20:22])[0] == 2, f"{name} is not ADPCM"
            assert name.startswith(FOLDER + BANK), name
    assert not [n for n in names if n.startswith(FOLDER + "sounds/")], "this is not the BeardLib pack"


@pytest.mark.skipif(not PACK.is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_the_folder_says_what_it_is_to_the_loader_and_to_blt():
    with zipfile.ZipFile(PACK) as z:
        root = ET.fromstring(z.read(FOLDER + "main.xml"))
        assert root.tag == "mod" and root.get("name") == pack.INSTALL
        meta = json.loads(z.read(FOLDER + "mod.txt"))
        assert meta["name"] == pack.INSTALL
        readme = z.read(FOLDER + "README.txt").decode("utf-8")
    assert "soundbanks/streamed/regular_vox/" in readme
    assert "BeardLib" in readme, "the README has to say it needs no BeardLib"
    assert "This stream pack leaves those lines vanilla" in readme
    assert "unless the BeardLib pack" not in readme
