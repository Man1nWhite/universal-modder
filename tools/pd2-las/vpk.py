"""Valve VPK archive reader (versions 1 and 2), single-file archives only.

Used to read the L4D2 addon `miranda_rochelle.vpk` inside
`l4d2_miranda_lawson_1.zip`. Entry bodies of a single-file VPK (archive index
0x7fff) live inline after the directory tree; `entry_offset` is relative to the
end of the tree, not to the start of the file. Multi-file `_NNN.vpk` split
archives are not supported and raise on read.

CRC32 of each entry's full content (preload + body) is checked on `read()`.
Paths are validated before extraction: absolute paths, drive letters and
`..` traversal are rejected.
"""
from __future__ import annotations

import struct
import zipfile
import zlib
from dataclasses import dataclass

VPK_SIGNATURE = 0x55AA1234
INLINE_ARCHIVE = 0x7FFF


@dataclass(frozen=True)
class VpkEntry:
    """One file inside a VPK."""

    path: str
    crc32: int
    preload: bytes
    archive_index: int
    entry_offset: int
    entry_length: int


class VpkError(ValueError):
    pass


def _safe_rel_path(path: str) -> str:
    path = path.replace("\\", "/")
    if path.startswith("/") or ":" in path.split("/", 1)[0]:
        raise VpkError(f"unsafe entry path: {path!r}")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise VpkError(f"unsafe entry path: {path!r}")
    return "/".join(parts)


class VpkArchive:
    """In-memory single-file VPK."""

    def __init__(self, data: bytes, name: str = "archive.vpk") -> None:
        self.name = name
        self._data = data
        if len(data) < 12:
            raise VpkError(f"{name}: truncated VPK header")
        sig, version, tree_size = struct.unpack_from("<III", data, 0)
        if sig != VPK_SIGNATURE:
            raise VpkError(f"{name}: bad VPK signature {sig:#x}")
        if version == 1:
            tree_start = 12
        elif version == 2:
            if len(data) < 28:
                raise VpkError(f"{name}: truncated VPK v2 header")
            tree_start = 28
        else:
            raise VpkError(f"{name}: unsupported VPK version {version}")
        self.version = version
        self._data_start = tree_start + tree_size
        if self._data_start > len(data):
            raise VpkError(f"{name}: truncated VPK tree")
        self._entries: dict[str, VpkEntry] = {}
        self._parse_tree(data, tree_start)

    @classmethod
    def from_file(cls, path) -> "VpkArchive":
        with open(path, "rb") as fh:
            return cls(fh.read(), name=str(path))

    @classmethod
    def from_zip(cls, zip_path, inner_path: str) -> "VpkArchive":
        """Read a VPK member out of a zip without extracting to disk."""
        with zipfile.ZipFile(zip_path) as zf:
            return cls(zf.read(inner_path), name=f"{zip_path}!{inner_path}")

    def _parse_tree(self, data: bytes, pos: int) -> None:
        def cstr() -> str:
            nonlocal pos
            end = data.index(b"\x00", pos)
            out = data[pos:end].decode("latin1")
            pos = end + 1
            return out

        while True:
            ext = cstr()
            if not ext:
                break
            while True:
                folder = cstr()
                if not folder:
                    break
                while True:
                    stem = cstr()
                    if not stem:
                        break
                    if pos + 18 > len(data):
                        raise VpkError(f"{self.name}: truncated tree entry")
                    crc, preload_len, archive_index, entry_offset, entry_length, terminator = (
                        struct.unpack_from("<IHHIIH", data, pos)
                    )
                    pos += 18
                    if terminator != 0xFFFF:
                        raise VpkError(f"{self.name}: bad tree terminator")
                    preload = data[pos : pos + preload_len]
                    pos += preload_len
                    if len(preload) != preload_len:
                        raise VpkError(f"{self.name}: truncated preload data")
                    rel = stem if folder == " " else f"{folder}/{stem}"
                    ext_part = f".{ext}" if ext else ""
                    path = _safe_rel_path(f"{rel}{ext_part}")
                    self._entries[path] = VpkEntry(
                        path=path,
                        crc32=crc,
                        preload=preload,
                        archive_index=archive_index,
                        entry_offset=entry_offset,
                        entry_length=entry_length,
                    )

    @property
    def entries(self) -> list[VpkEntry]:
        return sorted(self._entries.values(), key=lambda e: e.path)

    def __contains__(self, path: str) -> bool:
        return _safe_rel_path(path) in self._entries

    def read(self, path: str) -> bytes:
        key = _safe_rel_path(path)
        try:
            entry = self._entries[key]
        except KeyError:
            raise VpkError(f"{self.name}: no such entry: {path!r}") from None
        if entry.archive_index != INLINE_ARCHIVE:
            raise VpkError(
                f"{self.name}: entry {path!r} lives in split archive "
                f"{entry.archive_index:03d}; only single-file VPKs are supported"
            )
        start = self._data_start + entry.entry_offset
        body = self._data[start : start + entry.entry_length]
        if len(body) != entry.entry_length:
            raise VpkError(f"{self.name}: truncated entry {path!r}")
        content = entry.preload + body
        actual = zlib.crc32(content) & 0xFFFFFFFF
        if actual != entry.crc32:
            raise VpkError(
                f"{self.name}: CRC mismatch for {path!r}: "
                f"{actual:08x} != {entry.crc32:08x}"
            )
        return content

    def extract(self, dest) -> list[str]:
        """Write every entry under ``dest``; returns the safe relative paths."""
        import os
        from pathlib import Path

        root = Path(dest)
        written = []
        for entry in self.entries:
            rel = _safe_rel_path(entry.path)
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = self.read(entry.path)
            with open(target, "wb") as fh:
                fh.write(data)
            written.append(rel)
            os.utime(target, (0, 0))
        return written
