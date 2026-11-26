"""The keying contract of the two character `.stream` packs (2026-11-25).

`Geralt_VO_over_Rust_Stream` and `Arivus_VO_over_Hoxton_Stream` follow the Hila
pack's route: one Wwise ADPCM file per shared `regular_vox` voice-line id, named
after the id. Slots with no take in the pack's source set are left vanilla, as are
the 27 Wwise Vorbis ids. These tests read the tracked CSVs and, when `dist/` is
present, the built zips - no ffmpeg and no archives needed.
"""
from __future__ import annotations

import csv
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_character_stream_mod as charpack  # noqa: E402
import wwise_ima  # noqa: E402
from dist_paths import dist_path  # noqa: E402

CUTS = ROOT / "voice_lines_vox" / "miranda_lawson" / "hila_intent_cuts.csv"
VORBIS = ROOT / "voice_lines_vox" / "miranda_lawson" / "hila_vorbis_ids.csv"
NAME_ADDRESS = re.compile(r"shepard|commander|commando", re.IGNORECASE)

PACKS = {
    "geralt-rust": dist_path(ROOT, "Geralt_VO_over_Rust_Stream.zip"),
    "arivus-old-hoxton": dist_path(ROOT, "Arivus_VO_over_Hoxton_Stream.zip"),
}


def _first_slot_per_id() -> dict[str, str]:
    chosen: dict[str, str] = {}
    with CUTS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            chosen.setdefault(r["hila_id"].strip(), r["slot"])
    return chosen


def _vorbis_ids() -> set[str]:
    with VORBIS.open(newline="", encoding="utf-8") as f:
        return {r["hila_id"].strip() for r in csv.DictReader(f)}


def _picks(pack_id: str) -> dict[str, dict]:
    cfg = charpack.PACKS[pack_id]
    return charpack.load_picks_csv(cfg["picks"])


def _expected(pack_id: str):
    ids = _first_slot_per_id()
    covered = set(_picks(pack_id))
    vorbis = _vorbis_ids()
    covered_ids = {hila_id for hila_id, slot in ids.items() if slot in covered}
    return covered_ids, vorbis, ids


@pytest.mark.parametrize("pack_id", sorted(PACKS))
def test_picks_name_real_slots_no_rank_no_blank(pack_id):
    picks = _picks(pack_id)
    table = set(_first_slot_per_id().values())
    assert picks, "a pack must pick at least one slot"
    for slot, row in picks.items():
        assert slot in table, f"{slot} is not a slot in hila_intent_cuts.csv"
        assert not NAME_ADDRESS.search(row.get("clip_text", "")), (slot, "clip_text")
        for col in ("t_start", "t_end", "source_ogg"):
            assert row.get(col), (slot, col)
        start, end = float(row["t_start"]), float(row["t_end"])
        assert 0.0 <= start < end


@pytest.mark.parametrize("pack_id", sorted(PACKS))
def test_pick_sources_exist_in_the_configured_archives(pack_id):
    cfg = charpack.PACKS[pack_id]
    picks = _picks(pack_id)
    by_base = {}
    for path, enc in cfg["archives"]:
        for name in charpack.list_zip_files(path, enc):
            by_base.setdefault(name.split("/")[-1], name)
    for slot, row in picks.items():
        assert row["source_ogg"] in by_base, f"{slot}: {row['source_ogg']} not in any configured archive"


@pytest.mark.parametrize("pack_id", sorted(PACKS))
def test_the_expected_stream_counts(pack_id):
    covered_ids, vorbis, ids = _expected(pack_id)
    expected = len(covered_ids) - len(covered_ids & vorbis)
    assert expected > 0
    if PACKS[pack_id].is_file():
        with zipfile.ZipFile(PACKS[pack_id]) as z:
            streams = [n for n in z.namelist() if n.endswith(".stream")]
        assert len(streams) == expected
    cfg = charpack.PACKS[pack_id]
    assert cfg["install"].endswith("Stream") and "/" not in cfg["install"]


@pytest.mark.parametrize("pack_id", sorted(PACKS))
def test_the_packs_are_alternatives_not_companions(pack_id):
    """Both packs write the shared regular_vox ids; the docs must say install only one."""
    cfg = charpack.PACKS[pack_id]
    text = charpack.readme(pack_id, cfg, 1, 885, 27, 1.0, 1, 1)
    assert "INSTALL ONLY ONE" in text


@pytest.mark.skipif(not PACKS["geralt-rust"].is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_the_geralt_pack_holds_one_stream_per_covered_id():
    covered_ids, vorbis, _ids = _expected("geralt-rust")
    with zipfile.ZipFile(PACKS["geralt-rust"]) as z:
        streams = {Path(n).stem for n in z.namelist() if n.endswith(".stream")}
    assert streams == covered_ids - vorbis


@pytest.mark.skipif(not PACKS["arivus-old-hoxton"].is_file(), reason="dist/ is absent from this sandbox snapshot")
def test_the_arivus_pack_holds_one_stream_per_covered_id_and_borrows_the_hoxton_callout():
    covered_ids, vorbis, _ids = _expected("arivus-old-hoxton")
    picks = _picks("arivus-old-hoxton")
    assert picks["call_teammate.hey_you"]["source_ogg"] == "Геральт-Hoxton.mp3"
    with zipfile.ZipFile(PACKS["arivus-old-hoxton"]) as z:
        streams = {Path(n).stem for n in z.namelist() if n.endswith(".stream")}
    assert streams == covered_ids - vorbis


@pytest.mark.parametrize("pack_id", sorted(PACKS))
@pytest.mark.skipif(not PACKS["geralt-rust"].is_file() or not PACKS["arivus-old-hoxton"].is_file(),
                    reason="dist/ is absent from this sandbox snapshot")
def test_the_manifests_agree_with_what_is_in_the_zips(pack_id):
    pack = charpack.PACKS[pack_id]
    with zipfile.ZipFile(PACKS[pack_id]) as z:
        install = z.namelist()[0].split("/")[0]
        rows = list(csv.DictReader(z.read(install + "/" + pack["manifest"]).decode().splitlines()))
        streams = {Path(n).stem: len(z.read(n)) for n in z.namelist() if n.endswith(".stream")}
    import build_hila_stream_mod as hila_base
    assert [r["hila_id"] for r in rows] == [hila_id for hila_id, _s, _a in hila_base.load_ids()]
    for row in rows:
        written = row["hila_id"] in streams
        assert written == (not row["skipped"]), row
        if written:
            assert streams[row["hila_id"]] == int(row["stream_bytes"]), row
        elif row["skipped"].startswith("no take in"):
            assert row["stream_bytes"] == "0" and row["frames"] == "0", row
        else:
            # the vorbis rows carry the would-be clip bytes, like the Hila pack does
            assert row["skipped"] == "vorbis id left vanilla", row


@pytest.mark.parametrize("pack_id", sorted(PACKS))
@pytest.mark.skipif(not PACKS["geralt-rust"].is_file() or not PACKS["arivus-old-hoxton"].is_file(),
                    reason="dist/ is absent from this sandbox snapshot")
def test_every_stream_is_mono_ima_adpcm_at_44100_in_whole_blocks(pack_id):
    with zipfile.ZipFile(PACKS[pack_id]) as z:
        for name in [n for n in z.namelist() if n.endswith(".stream")]:
            blob = z.read(name)
            channels, rate, data = wwise_ima.read(blob)
            assert (channels, rate) == (1, wwise_ima.SAMPLE_RATE), name
            assert blob[:64] == wwise_ima.header(1, len(data)), f"{name} has a foreign header"
            assert len(data) % wwise_ima.SUBBLOCK == 0


def test_the_geralt_pack_ships_the_sub8_takes_it_actually_has():
    """kill.taser/mark.taser scored <8 for the Hila pick, but the Geralt set
    purpose-authors them, so they ship - the Hila removal is per-archive."""
    picks = _picks("geralt-rust")
    assert {"kill.taser", "mark.taser"} <= set(picks)
    assert "call_teammate.hey_you" not in picks  # no Geralt name take for Rust; vanilla


def test_the_arivus_pack_ships_its_own_takes_plus_the_borrowed_callout():
    picks = _picks("arivus-old-hoxton")
    own = {s for s in picks if s != "call_teammate.hey_you"}
    assert own == {"ammo.low", "civ.down", "civ.killthreat", "civ.nophone", "drop.ammo",
                   "kill.cloaker", "kill.dozer", "kill.shield", "kill.sniper", "kill.taser",
                   "mark.cloaker", "mark.dozer", "mark.shield", "mark.sniper", "mark.taser",
                   "nade.grenade", "nade.smoke", "nade.tear"}
    assert picks["call_teammate.hey_you"]["source_ogg"] == "Геральт-Hoxton.mp3"


# ---------------------------------------------------------------- the char_rust route (D74)

def test_the_char_rust_route_refuses_until_an_id_is_named(tmp_path, monkeypatch):
    """`--bank char_rust` ships nothing on a guess: a dedicated bank's ids cannot be derived.

    The measured table says which files exist in Rust's own bank; nothing in it (or in the
    reference Marine pack, which only names the medic-kill *event*) says which line each id is.
    So the builder has to stop, and it has to stop *before* encoding: a take written to a guessed
    id plays the wrong line in game.
    """
    cfg = charpack.PACKS["geralt-rust"]
    monkeypatch.setattr(charpack, "load_named_ids", lambda _path: {})
    with pytest.raises(SystemExit) as stop:
        charpack.build_dedicated("geralt-rust", cfg, "char_rust", ff="/nonexistent", args=None)
    message = str(stop.value)
    assert "no named voice-line id" in message
    assert "char_rust_ids.csv" in message
    assert "kill.taser" in message                      # the slots it lists are the picks
    assert not list(tmp_path.iterdir())


def test_the_named_id_template_is_tracked_and_empty():
    """The file the build reads is tracked, carries the instructions, and holds no rows yet."""
    path = charpack.CHAR_RUST_IDS
    assert path.is_file(), "the build names this file; it has to exist as a template"
    assert charpack.load_named_ids(path) == {}, "a row would need a source that named that id"
    text = path.read_text()
    assert "slot,id,named_by" in text and "refuses" in text


def test_the_dedicated_route_writes_the_measured_bank_and_nothing_shared():
    """The route's bank is the measured one, and the two banks never share an id."""
    tables = ROOT / "voice_lines_vox" / "targets"
    measured = [r["id"] for r in csv.DictReader((tables / "rust_dedicated_char_rust.csv").open())]
    picks = list(_picks("geralt-rust"))[:3]
    named = dict(zip(picks, measured[:3]))
    folder = charpack.bank_folder("char_rust")
    assert folder == "soundbanks/streamed/char_rust"
    for slot, hila_id in named.items():
        assert hila_id in measured, "an id has to come from the measured bank"
        assert hila_id not in {r["id"] for r in csv.DictReader((tables / "rust_shared_regular_vox.csv").open())}
    # the two banks are disjoint, which is the property the write path relies on
    shared = {r["id"] for r in csv.DictReader((tables / "rust_shared_regular_vox.csv").open())}
    assert not set(named.values()) & shared
