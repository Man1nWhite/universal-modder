#!/usr/bin/env python3
"""Build the Geralt-over-Rust BeardLib <Sounds> voice pack for PAYDAY 2.

Produces `dist/Geralt/Geralt_VO_over_Rust.zip`:
  Geralt VO over Rust/
    main.xml                      BeardLib <Sounds> + <redirect prefix="rb16"> + lifecycle fix hook
    mod.txt                       SuperBLT metadata (for mods/ installs; ignored in mod_overrides/)
    README.txt                    Install, scope, and verification guide
    geralt_rust_vo_map.csv        Build manifest: all 36 takes -> OGG + bark event IDs
    hooks/beardlib_sound_fix.lua  Fixes BeardLib 5.2.0 SoundManager / XAudio lifecycle bugs
    voicelines/*.ogg              36 trimmed, -1.0 dBFS mono 44.1 kHz Ogg Vorbis clips

Architecture mirrors `Marine VO for Rust`'s `<Sounds directory="voicelines">` / `<random>` /
`<redirect ... prefix="rb16"/>` layout while shipping all 36 takes from
`references/voice/GERALT VOICE (PAYDAY 2).zip`:
  - 29 intent slots (with <random> pools for civ.down x4, inspire.faster x2, mask.go x2),
  - 2 character-specific summon callouts (`f21ab_sin` when Rust calls Hila, `f21d_sin` when
    Rust calls Old Hoxton),
  - Uncovered Rust voice lines remain vanilla (no silent `.stream` stubs),
  - Companion Lua hook fixes BeardLib 5.2.0's `blt.xaudio.setup()` skip, `Closed` boot state,
    and `Setup:unload_packages` -> `Close()` buffer wipe so `<Sounds>` plays in heists.
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import subprocess
import sys
import tempfile
import xml.sax.saxutils as saxutils
import zipfile
from collections import OrderedDict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]
import determinism  # noqa: E402
from pack_checksum import write_pack_checksum  # noqa: E402

GERALT_ZIP = ROOT / "references/voice/GERALT VOICE (PAYDAY 2).zip"
TAKES_CSV = ROOT / "voice_lines_vox/geralt/rust_beardlib_takes.csv"
PICKS_CSV = ROOT / "voice_lines_vox/geralt/slot_picks.csv"
EVENTS_CSV = ROOT / "voice_lines_vox/miranda_lawson/slot_event_ids.csv"
DEFAULT_OUT = ROOT / "dist/Geralt/Geralt_VO_over_Rust.zip"

MOD_FOLDER = "Geralt VO over Rust"
MOD_NAME = "Geralt VO over Rust"
RUST_PREFIX = "rb16"
SAMPLE_RATE = 44100
TARGET_PEAK_DBFS = -1.0
MAX_GAIN_DB = 12.0
MIN_GAIN_DB = -9.0
FADE_SECONDS = 0.005
ZIP_EPOCH = (2020, 1, 1, 0, 0, 0)


def ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            return str(exe)
    except Exception as exc:  # pragma: no cover - pinned build dep
        raise SystemExit(f"need imageio-ffmpeg: {exc}") from exc
    raise SystemExit("need imageio-ffmpeg binary")


def load_takes(path: Path = TAKES_CSV) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    with path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("intent_id")]
    if not rows:
        raise SystemExit(f"{path} has no rows")
    return rows


def render_sound_fix_lua() -> str:
    """Return `hooks/beardlib_sound_fix.lua` fixing BeardLib 5.2.0's <Sounds> lifecycle."""
    return """-- Geralt VO over Rust: BeardLib 5.2.0 <Sounds> lifecycle fix.
--
-- Fixes three bugs that leave BeardLib <Sounds> silent in PAYDAY 2 heists:
--   1. Modern SuperBLT (mods/base/base.lua) defines _G.XAudio = {} before
--      blt.xaudio.setup() runs, so SoundsModule:init()'s `if not XAudio` check
--      skips OpenAL initialization and blt.xaudio.issetup() remains false.
--   2. On older SuperBLT builds where _G.XAudio is nil until setup(), BeardLib's
--      Core.lua constructs BeardLibSoundManager with self.Closed = true and
--      skips MixedSoundSource.lua (`if not XAudio then return end`) before
--      SoundsModule runs.
--   3. Hooks/GeneralHooks.lua hooks Setup:unload_packages -> Sound:Close(),
--      wiping self.buffers = {} and setting self.Closed = true across state
--      transitions, while Sound:Open() returns early when self.Closed is true.

local function ensure_xaudio()
\tif blt and blt.xaudio and blt.xaudio.setup then
\t\tif not blt.xaudio.issetup or not blt.xaudio.issetup() then
\t\t\tblt.xaudio.setup()
\t\tend
\tend
\treturn XAudio ~= nil
end

local function ensure_mixed_sound_source()
\tif not XAudio then
\t\treturn false
\tend
\tif not MixedSoundSource and BeardLib and BeardLib.ModPath then
\t\tlocal base = BeardLib.ModPath
\t\tlocal mss_path = (Path and Path.Combine and Path:Combine(base, "Classes/MixedSoundSource.lua"))
\t\t\tor (base .. "Classes/MixedSoundSource.lua")
\t\tlocal exists = (FileIO and FileIO.Exists and FileIO:Exists(mss_path))
\t\t\tor (SystemFS and SystemFS.exists and SystemFS:exists(mss_path))
\t\tif exists then
\t\t\tdofile(mss_path)
\t\tend
\tend
\tif MixedSoundSource and not MixedSoundSource._um_stop_patched then
\t\tMixedSoundSource._um_stop_patched = true
\t\tlocal orig_init = MixedSoundSource.init
\t\tfunction MixedSoundSource:init(sound_id, queue, engine_source, clbk, cookie)
\t\t\torig_init(self, sound_id, queue, engine_source, clbk, cookie)
\t\t\tif engine_source then
\t\t\t\tif engine_source.is_relative and engine_source:is_relative() then
\t\t\t\t\tself:set_relative(true)
\t\t\t\telseif engine_source.get_position then
\t\t\t\t\tlocal pos = engine_source:get_position()
\t\t\t\t\tif pos then
\t\t\t\t\t\tself:set_position(pos)
\t\t\t\t\tend
\t\t\t\tend
\t\t\tend
\t\tend
\t\tfunction MixedSoundSource:stop()
\t\t\tself._queue = {}
\t\t\tif not self:is_closed() then
\t\t\t\tMixedSoundSource.super.stop(self)
\t\t\t\tself:close()
\t\t\tend
\t\tend
\tend
\treturn MixedSoundSource ~= nil
end

local function spec_key(data)
\treturn table.concat({
\t\ttostring(data.id or ""),
\t\ttostring(data.prefix or ""),
\t\ttostring(data.prefixes_strict and "1" or "0"),
\t\ttostring(data.full_path or ""),
\t}, "\\0")
end

local function apply_beardlib_sound_fix()
\tif not BeardLib or not BeardLib.Managers or not BeardLib.Managers.Sound then
\t\treturn
\tend
\tlocal sm = BeardLib.Managers.Sound
\tlocal has_xaudio = ensure_xaudio()
\tensure_mixed_sound_source()
\tif has_xaudio then
\t\tsm.Closed = false
\tend

\tif sm._um_sound_fix_v1 then
\t\treturn
\tend
\tsm._um_sound_fix_v1 = true
\tsm._um_persistent_map = sm._um_persistent_map or {}
\tsm._um_persistent_list = sm._um_persistent_list or {}

\tlocal orig_add_buffer = sm.AddBuffer
\tfunction sm:AddBuffer(data, force)
\t\tif ensure_xaudio() then
\t\t\tensure_mixed_sound_source()
\t\t\tself.Closed = false
\t\tend
\t\tif type(data) == "table" and data.full_path and not data.unload then
\t\t\tlocal k = spec_key(data)
\t\t\tif data.close_previous then
\t\t\t\tfor i = #self._um_persistent_list, 1, -1 do
\t\t\t\t\tlocal prev = self._um_persistent_list[i]
\t\t\t\t\tif prev.id == data.id and self:ComparePrefixes(prev, data.id, data.prefixes) then
\t\t\t\t\t\tself._um_persistent_map[spec_key(prev)] = nil
\t\t\t\t\t\ttable.remove(self._um_persistent_list, i)
\t\t\t\t\tend
\t\t\t\tend
\t\t\tend
\t\t\tif not self._um_persistent_map[k] then
\t\t\t\tself._um_persistent_map[k] = data
\t\t\t\ttable.insert(self._um_persistent_list, data)
\t\t\telse
\t\t\t\tself._um_persistent_map[k] = data
\t\t\tend
\t\tend
\t\treturn orig_add_buffer(self, data, force)
\tend

\tlocal orig_open = sm.Open
\tfunction sm:Open()
\t\tif ensure_xaudio() then
\t\t\tensure_mixed_sound_source()
\t\t\tself.Closed = false
\t\t\tfor _, spec in ipairs(self._um_persistent_list) do
\t\t\t\tif not self:GetLoadedBuffer(spec.id, spec.prefixes, true) then
\t\t\t\t\tif not spec.load_on_play then
\t\t\t\t\t\tlocal buffer = XAudio.Buffer:new(spec.full_path)
\t\t\t\t\t\tbuffer.data = spec
\t\t\t\t\t\ttable.insert(self.buffers, buffer)
\t\t\t\t\telse
\t\t\t\t\t\ttable.insert(self.buffers, spec)
\t\t\t\t\tend
\t\t\t\t\tif not self:GetSound(spec.id, spec.prefixes) then
\t\t\t\t\t\tself:AddSoundID(spec)
\t\t\t\t\tend
\t\t\t\tend
\t\t\tend
\t\t\tif SoundDevice then
\t\t\t\tfor _, redirect in ipairs(self.redirects) do
\t\t\t\t\tif redirect.id then
\t\t\t\t\t\tself:StoreFloat(redirect.id)
\t\t\t\t\tend
\t\t\t\tend
\t\t\tend
\t\tend
\t\treturn orig_open(self)
\tend
end

apply_beardlib_sound_fix()
"""


def render_main_xml(takes: list[dict[str, str]]) -> str:
    """Render BeardLib `main.xml` mirroring `Marine VO for Rust`'s `<Sounds>` structure."""
    groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in takes:
        groups.setdefault(row["group_id"], []).append(row)

    lines = [
        f'<mod name={saxutils.quoteattr(MOD_NAME)} min_lib_ver="3.38" core_class="hooks/beardlib_sound_fix.lua">',
        '\t<Hooks directory="hooks">',
        '\t\t<hook source_file="lib/setups/setup" file="beardlib_sound_fix.lua"/>',
        "\t</Hooks>",
        '\t<Sounds directory="voicelines">',
    ]
    seen_redirects: set[tuple[str, str]] = set()
    for group_id, group_rows in groups.items():
        for row in group_rows:
            sid = saxutils.quoteattr(row["sound_id"])
            opath = saxutils.quoteattr(row["ogg_name"])
            lines.append(f"\t\t<sound id={sid} path={opath}/>")
        if len(group_rows) > 1:
            lines.append(f"\t\t<random id={saxutils.quoteattr(group_id)}>")
            for row in group_rows:
                lines.append(f"\t\t\t<sound id={saxutils.quoteattr(row['sound_id'])}/>")
            lines.append("\t\t</random>")
        prefix = group_rows[0]["prefix"]
        events = [e for e in group_rows[0]["event_ids"].split("|") if e]
        for ev in events:
            key = (ev, prefix)
            if key in seen_redirects:
                raise ValueError(f"duplicate redirect event {ev!r} for prefix {prefix!r}")
            seen_redirects.add(key)
            lines.append(
                f"\t\t<redirect id={saxutils.quoteattr(ev)} "
                f"to={saxutils.quoteattr(group_id)} "
                f"prefix={saxutils.quoteattr(prefix)}/>"
            )
    lines.append("\t</Sounds>")
    lines.append("</mod>")
    return "\n".join(lines) + "\n"


def render_mod_txt(num_clips: int, num_intents: int, num_events: int) -> str:
    return (
        "{\n"
        f'  "name": "{MOD_NAME}",\n'
        '  "description": "Geralt of Rivia voice pack over Rust (rb16): '
        f'{num_clips} Ogg Vorbis takes across {num_intents} intents ({num_events} bark events), '
        'with BeardLib 5.2.0 XAudio lifecycle fix. Uncovered lines stay vanilla.",\n'
        '  "author": "universal-modder",\n'
        '  "version": "1.0.0",\n'
        '  "blt_version": 2\n'
        "}\n"
    )


def render_readme(num_clips: int, num_slots: int, num_events: int) -> str:
    return f"""{MOD_NAME} — PAYDAY 2 Voice Pack
=================================

Replaces Rust's (`rb16`) combat barks and squad summon callouts with Geralt of Rivia's
voice while leaving uncovered Rust lines as vanilla Rust audio.

Prerequisites
-------------
  - SuperBLT (provides the `blt.xaudio` OpenAL API)
  - BeardLib 5.x (provides `<Sounds>` event redirection on `prefix="rb16"`)

Install (pick ONE folder — do not install in both at once)
----------------------------------------------------------
  1. Recommended (matches `Geralt over Rust` and `Marine VO for Rust`):
       Extract `{MOD_FOLDER}` into `PAYDAY 2/assets/mod_overrides/` so that
       `PAYDAY 2/assets/mod_overrides/{MOD_FOLDER}/main.xml` exists.
     (Alternative: extract `{MOD_FOLDER}` into `PAYDAY 2/mods/` so that
      `PAYDAY 2/mods/{MOD_FOLDER}/main.xml` exists.)
  2. Start PAYDAY 2 and play a heist as Rust (or with Rust as an AI / co-op teammate).

What is covered ({num_clips} clips across {num_slots} bark slots + 2 teammate callouts = {num_events} events)
-------------------------------------------------------------------------------------------------------------
  - 29 combat/stealth bark slots mapped to Rust (`prefix="rb16"`), including `<random>`
    multi-take rotation on:
      * `civ.down` (4 takes)
      * `inspire.faster` (2 takes)
      * `mask.go` (2 takes)
  - 2 character-specific teammate summon shouts (`PlayerStandard` `come` shout):
      * `f21ab_sin` — Geralt calls Hila ("Hila.")
      * `f21d_sin`  — Geralt calls Old Hoxton ("Hoxton.")
  - Uncovered Rust lines (heist-specific mission chatter, pagers, etc.) remain vanilla Rust.
  - Other heisters (Hila `rb21`, Old Hoxton `rb5`, Dallas `rb4`, etc.) are untouched even
    when posting the same bark event names.

Why `hooks/beardlib_sound_fix.lua` is included
----------------------------------------------
BeardLib 5.2.0's `<Sounds>` module has three lifecycle bugs with modern SuperBLT:
  1. SuperBLT pre-defines `_G.XAudio = {{}}` before `blt.xaudio.setup()` runs, causing
     `SoundsModule:init()` (`if not XAudio`) to skip OpenAL initialization.
  2. If `XAudio` was nil when `Core.lua` ran, `BeardLibSoundManager.Closed` starts `true`
     and `MixedSoundSource` is skipped.
  3. `Setup:unload_packages` calls `BeardLib.Managers.Sound:Close()`, wiping `self.buffers`
     and leaving `self.Closed = true` when entering a heist.
`hooks/beardlib_sound_fix.lua` fixes all three idempotently without modifying BeardLib on disk.

Uninstall
---------
Delete `{MOD_FOLDER}` from `assets/mod_overrides/` (or `mods/`).
"""


def _decode_trim_normalize_pcm(src_mp3: Path, start_s: float, end_s: float, ff: str) -> tuple[bytes, float, float]:
    """Decode `[start_s, end_s]` to mono 44.1 kHz int16 PCM, level-matched to TARGET_PEAK_DBFS."""
    dur_s = max(0.10, end_s - start_s)
    raw = subprocess.run(
        [
            ff,
            "-v",
            "error",
            "-threads",
            "1",
            "-ss",
            f"{start_s:.3f}",
            "-t",
            f"{dur_s:.3f}",
            "-i",
            str(src_mp3),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if samples.size == 0:
        raise ValueError(f"decoded 0 samples from {src_mp3.name} ({start_s}..{end_s})")

    peak_abs = float(np.max(np.abs(samples))) / 32768.0
    peak_db = 20.0 * math.log10(max(peak_abs, 1e-7))
    gain_db = max(MIN_GAIN_DB, min(MAX_GAIN_DB, TARGET_PEAK_DBFS - peak_db))
    if abs(gain_db) >= 0.2:
        samples = samples * (10.0 ** (gain_db / 20.0))
    else:
        gain_db = 0.0

    fade_len = min(int(SAMPLE_RATE * FADE_SECONDS), samples.size // 4)
    if fade_len > 1:
        ramp = np.linspace(0.0, 1.0, fade_len, dtype=np.float64)
        samples[:fade_len] *= ramp
        samples[-fade_len:] *= ramp[::-1]

    pcm_i16 = np.clip(np.rint(samples), -32768, 32767).astype("<i2")
    actual_dur = float(pcm_i16.size) / float(SAMPLE_RATE)
    return pcm_i16.tobytes(), actual_dur, gain_db


def _encode_vorbis_deterministic(pcm_bytes: bytes, dest_ogg: Path, ff: str) -> bytes:
    """Encode mono 44.1 kHz int16 PCM to deterministic Ogg Vorbis (`libvorbis -q:a 5`)."""
    subprocess.run(
        [
            ff,
            "-y",
            "-v",
            "error",
            "-threads",
            "1",
            "-f",
            "s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-c:a",
            "libvorbis",
            "-q:a",
            "5",
            str(dest_ogg),
        ],
        input=pcm_bytes,
        check=True,
        capture_output=True,
    )
    return dest_ogg.read_bytes()


def build_pack(out_zip: Path = DEFAULT_OUT, takes_csv: Path = TAKES_CSV, source_zip: Path = GERALT_ZIP) -> dict[str, int]:
    """Build `Geralt_VO_over_Rust.zip` deterministically and write its `.sha256` sidecar."""
    determinism.enter(__file__)
    if not source_zip.is_file():
        raise SystemExit(f"missing source archive {source_zip}")
    ff = ffmpeg_bin()
    takes = load_takes(takes_csv)

    files_to_pack: dict[str, bytes] = {}
    manifest_rows: list[list[str]] = [
        [
            "intent_id",
            "kind",
            "take_index",
            "sound_id",
            "group_id",
            "ogg_path",
            "source_mp3",
            "t_start",
            "t_end",
            "duration_s",
            "gain_db",
            "cut_line",
            "event_ids",
            "prefix",
        ]
    ]

    with zipfile.ZipFile(source_zip, "r", metadata_encoding="cp866") as zsrc, tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        available = set(zsrc.namelist())
        for idx, row in enumerate(takes):
            mp3_name = row["source_mp3"]
            if mp3_name not in available:
                raise SystemExit(f"source MP3 {mp3_name!r} missing from {source_zip}")
            mp3_path = tmp / f"src_{idx:02d}.mp3"
            mp3_path.write_bytes(zsrc.read(mp3_name))

            t_start = float(row["t_start"])
            t_end = float(row["t_end"])
            pcm_bytes, dur_s, gain_db = _decode_trim_normalize_pcm(mp3_path, t_start, t_end, ff)

            ogg_path = tmp / row["ogg_name"]
            ogg_bytes = _encode_vorbis_deterministic(pcm_bytes, ogg_path, ff)
            rel_ogg = f"voicelines/{row['ogg_name']}"
            files_to_pack[f"{MOD_FOLDER}/{rel_ogg}"] = ogg_bytes

            manifest_rows.append(
                [
                    row["intent_id"],
                    row["kind"],
                    row["take_index"],
                    row["sound_id"],
                    row["group_id"],
                    rel_ogg,
                    mp3_name,
                    f"{t_start:.3f}",
                    f"{t_end:.3f}",
                    f"{dur_s:.3f}",
                    f"{gain_db:+.2f}",
                    row["cut_line"],
                    row["event_ids"],
                    row["prefix"],
                ]
            )

    main_xml = render_main_xml(takes)
    num_clips = len(takes)
    num_slots = len({r["intent_id"] for r in takes if r["kind"] == "slot"})
    num_intents = len({r["intent_id"] for r in takes})
    num_events = len({ev for r in takes for ev in r["event_ids"].split("|") if ev})

    csv_buf = io.StringIO()
    csv.writer(csv_buf, lineterminator="\n").writerows(manifest_rows)

    files_to_pack[f"{MOD_FOLDER}/main.xml"] = main_xml.encode("utf-8")
    files_to_pack[f"{MOD_FOLDER}/mod.txt"] = render_mod_txt(num_clips, num_intents, num_events).encode("utf-8")
    files_to_pack[f"{MOD_FOLDER}/README.txt"] = render_readme(num_clips, num_slots, num_events).encode("utf-8")
    files_to_pack[f"{MOD_FOLDER}/geralt_rust_vo_map.csv"] = csv_buf.getvalue().encode("utf-8")
    files_to_pack[f"{MOD_FOLDER}/hooks/beardlib_sound_fix.lua"] = render_sound_fix_lua().encode("utf-8")

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname in sorted(files_to_pack):
            info = zipfile.ZipInfo(arcname, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, files_to_pack[arcname])

    write_pack_checksum(out_zip, ROOT)
    return {
        "clips": num_clips,
        "slots": num_slots,
        "intents": num_intents,
        "events": num_events,
        "bytes": out_zip.stat().st_size,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output zip path")
    ap.add_argument("--takes", type=Path, default=TAKES_CSV, help="input 36-take CSV manifest")
    args = ap.parse_args(argv)
    stats = build_pack(out_zip=args.out, takes_csv=args.takes)
    print(
        f"wrote {args.out} ({stats['bytes']:,} bytes: {stats['clips']} OGG clips, "
        f"{stats['slots']} slots + {stats['intents'] - stats['slots']} callouts, "
        f"{stats['events']} redirected events on {RUST_PREFIX})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
