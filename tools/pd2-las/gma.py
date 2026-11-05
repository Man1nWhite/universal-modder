"""Garry's Mod addon (`.gma`) reader, for subscribed workshop content.

Why this exists: a subscribed GMod addon is a folder of Source assets, and the
interesting part for this repo is that it is *the cheap end of the Source
pipeline* — `source_model.py` reads a `.mdl`/`.vvd`/`.vtx` triple directly, so a
`.gma` is a disposable wrapper around something already readable. Reading one
means the question "what is actually inside that addon?" is answered by its file
list and its bones, not by a description and a thumbnail.

Layout (Facepunch `gmad/include/AddonReader.h` + `src/create_gmad.cpp`):
``GMAD`` | version (u8) | steamid (u64) | timestamp (u64) |
[version > 1] required-content c-strings, terminated by an empty one |
name | description | author (c-strings) | addon version (u32) |
repeated { file number (u32, non-zero) | name | size (i64) | crc32 (u32) },
closed by a zero u32 | file bodies concatenated in the same order |
archive crc32 (u32) of everything before it.

`create_gmad.cpp` ends every addon it writes with that last u32. The per-file
CRCs only cover files this reader happens to open, and only once it opens them;
the archive CRC covers the header, the index and every body in one check, so it
is what detects an addon damaged after packing (a partly written download, a
zeroed tail, a hex-edited file). Hand-built addons often omit it, so its absence
is not an error — but when it *is* there and does not match, the report says so.

Three things the format does that matter here:

* **the payload may be LZMA-wrapped.** Steam hands out some older workshop
  items as a bare `.lzma` stream whose contents are the `.gma`
  (``cat addon.gma | lzma -d > real.gma``); `gma`-reading tools sniff the magic
  byte and decompress before parsing. We do the same.
* **the description is JSON, not prose.** `gmad` stores the title separately and
  puts `{"description": ..., "type": ..., "tags": [...]}` in the description
  field, so the field has to be unpacked with a JSON parse *and* left readable
  when that parse fails (hand-built addons put raw text there).
* **required content is a list, and GMod acts on it.** A v2+ addon can name the
  games it needs mounted ("half-life 2", "left 4 dead 2"); an addon whose
  required content is not mounted renders broken in game even though every file
  is present here, so the list is kept rather than skipped.

Read-only, no extraction to disk: `GmaArchive.entries` + `read(path)` is enough
to list an addon and pull the model triple out of memory. Per-file CRCs are
verified on read, the trailing archive CRC is checked when present, and paths
are validated the same way `vpk.py` validates its own (no absolute paths, no
`..`) so a hostile archive cannot walk out of memory.
"""
from __future__ import annotations

import json
import lzma
import struct
import zlib
from dataclasses import dataclass

GMA_MAGIC = b"GMAD"
SUPPORTED_VERSIONS = (1, 2, 3)
XZ_MAGIC = b"\xfd7zXZ\x00"
#: `foo.dx90.vtx` is what GMod ships for DX9; older addons carry a DX8 file or
#: the unified `foo.vtx`. Both are readable, so a model is not missing just
#: because its VTX is not the DX9 one.
VTX_SUFFIXES = (".dx90.vtx", ".vtx", ".dx80.vtx", ".sw.vtx")


class GmaError(ValueError):
    pass


@dataclass(frozen=True)
class GmaEntry:
    """One file inside a `.gma`: name, size, crc32 and offset into the body."""

    path: str
    size: int
    crc32: int
    offset: int


def _safe_rel_path(path: str) -> str:
    path = path.replace("\\", "/")
    if path.startswith("/") or ":" in path.split("/", 1)[0]:
        raise GmaError(f"unsafe entry path: {path!r}")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise GmaError(f"unsafe entry path: {path!r}")
    return "/".join(parts)


def unwrap_lzma(data: bytes) -> bytes:
    """Return `data`, decompressed first if it is a bare LZMA/LZMA-alone stream.

    Steam wraps some workshop downloads in LZMA with no container header of its
    own, so the only reliable test is "does it start with `GMAD`?". Anything
    else is fed to `lzma` in both the `.xz` and the legacy alone formats, and a
    clean `GmaError` is raised if neither works — a wrong guess must not look
    like a malformed addon.
    """
    if data[:4] == GMA_MAGIC:
        return data
    for fmt in (lzma.FORMAT_XZ, lzma.FORMAT_ALONE, lzma.FORMAT_AUTO):
        try:
            out = lzma.decompress(data, format=fmt)
        except lzma.LZMAError:
            continue
        if out[:4] == GMA_MAGIC:
            return out
        raise GmaError("LZMA stream did not decompress to a GMAD archive")
    raise GmaError(f"not a GMAD archive: magic {data[:4]!r}")


class GmaArchive:
    """In-memory Garry's Mod addon."""

    def __init__(self, data: bytes, name: str = "addon.gma") -> None:
        self.name = name
        self._data = unwrap_lzma(data)
        self.version = 0
        self.steamid = 0
        self.timestamp = 0
        self.title = ""
        self.description = ""
        self.author = ""
        self.addon_type = ""
        self.tags: tuple[str, ...] = ()
        self.required_content: tuple[str, ...] = ()
        #: Trailing whole-archive CRC32, or None when the addon does not carry
        #: one (hand-built archives); `archive_crc_ok` is None in that case.
        self.archive_crc: int | None = None
        self.archive_crc_ok: bool | None = None
        self.entries: list[GmaEntry] = []
        self._body = 0
        self._parse()

    # ------------------------------------------------------------ parsing
    def _parse(self) -> None:
        data = self._data
        pos = 0

        def take(fmt: str):
            nonlocal pos
            size = struct.calcsize(fmt)
            if pos + size > len(data):
                raise GmaError(f"{self.name}: truncated header at {pos}")
            out = struct.unpack_from(fmt, data, pos)
            pos += size
            return out if len(out) > 1 else out[0]

        def cstr() -> str:
            nonlocal pos
            end = data.find(b"\x00", pos)
            if end < 0:
                raise GmaError(f"{self.name}: unterminated string at {pos}")
            out = data[pos:end].decode("utf-8", "replace")
            pos = end + 1
            return out

        if take("4s") != GMA_MAGIC:
            raise GmaError(f"{self.name}: bad GMAD magic")
        self.version = take("<B")
        if self.version not in SUPPORTED_VERSIONS:
            raise GmaError(f"{self.name}: unsupported GMAD version {self.version}")
        self.steamid = take("<Q")
        self.timestamp = take("<Q")
        if self.version > 1:
            required = []
            while True:
                item = cstr()
                if not item:
                    break
                required.append(item)
            self.required_content = tuple(required)
        self.title = cstr()
        raw_desc = cstr()
        self.author = cstr()
        take("<I")  # addon version, unused

        self.description, self.addon_type, self.tags = _unpack_description(raw_desc)

        offset = 0
        while True:
            number = take("<I")
            if number == 0:
                break
            path = _safe_rel_path(cstr())
            size = take("<q")
            crc = take("<I")
            if size < 0:
                raise GmaError(f"{self.name}: negative size for {path!r}")
            self.entries.append(GmaEntry(path, size, crc, offset))
            offset += size

        self._body = pos
        total = sum(e.size for e in self.entries)
        if self._body + total > len(data):
            raise GmaError(
                f"{self.name}: file bodies need {total} bytes, "
                f"{len(data) - self._body} present"
            )
        # Everything after the bodies is the archive CRC32 `gmad` appends. A
        # stale one means the file was truncated or edited after packing, which
        # the per-file sizes cannot reveal on their own.
        tail = len(data) - (self._body + total)
        if tail == 4:
            end = self._body + total
            self.archive_crc = struct.unpack_from("<I", data, end)[0]
            actual = zlib.crc32(data[:end]) & 0xFFFFFFFF
            self.archive_crc_ok = actual == self.archive_crc

    # ------------------------------------------------------------- reading
    def _entry(self, path: str) -> GmaEntry:
        want = _safe_rel_path(path).lower()  # the addon filesystem is lowercase
        for entry in self.entries:
            if entry.path.lower() == want:
                return entry
        raise GmaError(f"{self.name}: no such entry: {path!r}")

    def has(self, path: str) -> bool:
        try:
            self._entry(path)
        except GmaError:
            return False
        return True

    def read(self, path: str) -> bytes:
        entry = self._entry(path)
        start = self._body + entry.offset
        body = self._data[start : start + entry.size]
        if len(body) != entry.size:
            raise GmaError(f"{self.name}: truncated entry {path!r}")
        actual = zlib.crc32(body) & 0xFFFFFFFF
        if entry.crc32 and actual != entry.crc32:
            raise GmaError(
                f"{self.name}: CRC mismatch for {path!r}: "
                f"{actual:08x} != {entry.crc32:08x}"
            )
        return body

    def paths(self, *suffixes: str) -> list[str]:
        """Entry names ending in any of `suffixes` (case-insensitive)."""
        want = tuple(s.lower() for s in suffixes)
        return [e.path for e in self.entries if e.path.lower().endswith(want)]

    def model_paths(self) -> list[tuple[str, str, str]]:
        """Every `.mdl` in the addon as an `(mdl, vvd, vtx)` path triple.

        The MDL does not name its VTX: the engine derives it from the model
        path and the DirectX level, so an addon may carry `foo.dx90.vtx`, a
        legacy `foo.vtx`, or a DX8-era `foo.dx80.vtx`. All three are readable
        here, and `VTX_SUFFIXES` is the preference order (DX9 first, because
        that is the variant this repo's other Source reads go through).
        """
        out = []
        for mdl in self.paths(".mdl"):
            stem = mdl[:-4]
            vvd = stem + ".vvd"
            if not self.has(vvd):
                continue
            vtx = next((stem + s for s in VTX_SUFFIXES if self.has(stem + s)), None)
            if vtx:
                out.append((mdl, self._entry(vvd).path, self._entry(vtx).path))
        return out

    def summary(self) -> str:
        """One readable paragraph about the addon, for a log or a note."""
        kinds: dict[str, int] = {}
        for entry in self.entries:
            ext = entry.path.rsplit(".", 1)[-1].lower() if "." in entry.path else "-"
            kinds[ext] = kinds.get(ext, 0) + 1
        biggest = sorted(self.entries, key=lambda e: e.size, reverse=True)[:5]
        kind_text = ", ".join(f"{ext} x{count}" for ext, count in sorted(kinds.items()))
        big_text = "; ".join(f"{e.path} ({e.size:,} B)" for e in biggest)
        required = ", ".join(self.required_content) or "none"
        if self.archive_crc_ok is None:
            crc_text = "absent"
        else:
            crc_text = "ok" if self.archive_crc_ok else "MISMATCH"
        return (
            f"{self.title!r} by {self.author!r} (GMAD v{self.version}, "
            f"type {self.addon_type or 'unset'}, tags {list(self.tags) or 'none'}, "
            f"{len(self.entries)} files, {sum(e.size for e in self.entries):,} B)\n"
            f"  description: {self.description}\n"
            f"  requires: {required}  archive crc: {crc_text}\n"
            f"  contents: {kind_text}\n"
            f"  largest: {big_text}"
        )


def _unpack_description(raw: str) -> tuple[str, str, tuple[str, ...]]:
    """`gmad` stores metadata as JSON in the description field; unpack it.

    A hand-built addon may put plain text there — that is a description, not an
    error, so it is kept as-is with no type and no tags.
    """
    raw = raw.strip()
    if not raw.startswith("{"):
        return raw, "", ()
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError:
        return raw, "", ()
    if not isinstance(blob, dict):
        return raw, "", ()
    tags = blob.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return (
        str(blob.get("description", "")),
        str(blob.get("type", "")).lower(),
        tuple(str(t) for t in tags if t),
    )
