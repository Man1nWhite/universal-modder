"""Snapshot folders before touching them (saves, profiles, config, the game's data folder).

    um backup create "C:\\Users\\me\\Documents\\My Games\\Terraria" --name terraria-saves
    um backup list [name]
    um backup diff terraria-saves "C:\\Users\\me\\Documents\\My Games\\Terraria"
    um backup restore terraria-saves [--to DIR] [--snapshot FILE] [--yes]

Snapshots are zip files + a manifest (size + sha1 per file) in ~/.universal-modder/backups/<name>/.
Snapshots created in the same second get numbered suffixes so earlier backups are never overwritten.
Restore validates and stages every file, snapshots the current state for undo, and removes files that
weren't in the snapshot only with --clean. Symlinks and junctions are not supported in backup trees.
Older snapshots are supported except ambiguous ones with duplicate manifest entries. For an older
snapshot with a relative source path, supply an explicit destination with --to.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PureWindowsPath

from um.common import data_dir, die, to_posix

MANIFEST = "_um_manifest.json"
MAX_SIZE = 20 << 30


def _root(name: str) -> Path:
    d = data_dir() / "backups" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _link(path: Path) -> bool:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _scan(src: Path) -> dict:
    if _link(src):
        die(f"backup folder is a symlink or junction: {src}")
    files = {}
    for p in sorted(src.rglob("*")):
        if _link(p):
            die(f"symlinks and junctions are not supported in backup folders: {p}")
        if p.is_file():
            rel = p.relative_to(src).as_posix()
            _validate_rel(rel)
            h = hashlib.sha1()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            files[rel] = dict(size=p.stat().st_size, sha1=h.hexdigest())
    return files


def _validate_rel(rel: str) -> None:
    if (not isinstance(rel, str) or not rel or "\\" in rel or "\x00" in rel
            or PureWindowsPath(rel).drive or rel.startswith("/")
            or any(part in ("", ".", "..") or ":" in part for part in rel.split("/"))):
        die(f"unsafe backup path: {rel!r}")


def create(src: str, name: str | None = None, note: str = "") -> Path:
    s = Path(to_posix(src)).expanduser()
    if _link(s):
        die(f"backup folder is a symlink or junction: {s}")
    if not s.is_dir():
        die(f"not a folder: {s}")
    s = s.resolve()
    name = name or s.name.replace(" ", "-").lower()
    files = _scan(s)
    total = sum(f["size"] for f in files.values())
    if total > MAX_SIZE:
        die(f"{total / 2**30:.1f} GB - too big to snapshot casually; back up the specific subfolder you'll change")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = _root(name)
    sequences = (p.stem[len(stamp) + 1:] for p in root.glob(f"{stamp}_*.zip"))
    sequence = max((int(n) + 1 for n in sequences if n.isdecimal()), default=0)
    while True:
        suffix = f"_{sequence:06d}" if sequence else ""
        out = root / f"{stamp}{suffix}.zip"
        try:
            z = zipfile.ZipFile(out, "x", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False)
            break
        except FileExistsError:
            sequence += 1
    try:
        with z:
            for rel in files:
                z.write(s / rel, "files/" + rel)
            z.writestr(MANIFEST, json.dumps(dict(version=2, source=str(s), created=stamp, note=note, files=files), indent=1))
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    print(f"{out}  ({len(files)} files, {total / 2**20:.1f} MB)")
    return out


def snapshots(name: str) -> list[Path]:
    return sorted(_root(name).glob("*.zip"))


def _manifest(zp: Path) -> dict:
    with zipfile.ZipFile(zp) as z:
        names = [i.filename for i in z.infolist()]
        unique = set(names)
        if len(names) != len(unique) or MANIFEST not in unique:
            die(f"invalid snapshot {zp}: duplicate or missing manifest/archive entries")
        m = json.loads(z.read(MANIFEST))
        if not isinstance(m, dict) or m.get("version", 1) not in (1, 2) or not isinstance(m.get("files"), dict):
            die(f"invalid snapshot manifest: {zp}")
        if not isinstance(m.get("source"), str) or not m["source"]:
            die(f"invalid snapshot source: {zp}")
        files = m["files"]
        for rel, info in files.items():
            _validate_rel(rel)
            if (not isinstance(info, dict) or type(info.get("size")) is not int or info["size"] < 0
                    or not isinstance(info.get("sha1"), str) or not re.fullmatch(r"[0-9a-f]{40}", info["sha1"])):
                die(f"invalid snapshot file metadata: {rel}")
            if any("/".join(rel.split("/")[:i]) in files for i in range(1, len(rel.split("/")))):
                die(f"snapshot file conflicts with a directory: {rel}")
            member = ("files/" if m.get("version", 1) == 2 else "") + rel
            if member == MANIFEST or member not in unique:
                die(f"missing or ambiguous snapshot member: {rel}")
            entry = z.getinfo(member)
            if entry.is_dir() or stat.S_ISLNK(entry.external_attr >> 16) or entry.file_size != info["size"]:
                die(f"invalid snapshot member: {rel}")
        if sum(info["size"] for info in files.values()) > MAX_SIZE:
            die("snapshot exceeds the 20 GiB restore limit")
        return m


def _target(m: dict, target: str | None) -> Path:
    path = Path(to_posix(target or m["source"])).expanduser()
    if target is None and not path.is_absolute():
        die("snapshot has a relative source path; supply an explicit target or --to")
    return path


def diff(name: str, target: str | None = None, snapshot: str | None = None) -> dict:
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _manifest(zp)
    t = _target(m, target)
    if _link(t):
        die(f"restore target is a symlink or junction: {t}")
    now = _scan(t) if t.is_dir() else {}
    old = m["files"]
    return dict(snapshot=str(zp), target=str(t),
                added=sorted(set(now) - set(old)), removed=sorted(set(old) - set(now)),
                changed=sorted(k for k in set(now) & set(old) if now[k]["sha1"] != old[k]["sha1"]))


def _parent_fd(root_fd: int, parts: list[str], create_dirs: bool) -> int:
    """Open a destination parent without following links (POSIX dir_fd path)."""
    fd = os.dup(root_fd)
    try:
        for part in parts:
            if create_dirs:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def _windows_parent(root: Path, rel: str, create_dirs: bool):
    """Hold directory handles without delete sharing to prevent reparse-point swaps on Windows."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    handles = []

    def lock(directory: Path):
        # OPEN_REPARSE_POINT observes the link itself, not its target. With no
        # FILE_SHARE_DELETE, an opened ancestor cannot be renamed or swapped.
        handle = kernel.CreateFileW(str(directory), 0x80, 0x1 | 0x2, None, 3, 0x02000000 | 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(handle)
        info = AttributeTagInfo()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
            die(f"restore path contains a symlink or junction: {directory}")

    try:
        # Lock all ancestors, not only the destination root: replacement uses a
        # Windows path rather than POSIX dir_fd-relative operations.
        for directory in reversed((root, *root.parents)):
            lock(directory)
        parent = root
        for part in rel.split("/")[:-1]:
            parent = parent / part
            if create_dirs:
                parent.mkdir(exist_ok=True)
            lock(parent)
        yield parent
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


@contextlib.contextmanager
def _stage_dir(root: Path, root_fd: int | None):
    """Create a private staging directory anchored to the destination filesystem."""
    if root_fd is None:
        with tempfile.TemporaryDirectory(prefix=".um-restore-", dir=root) as tmp:
            yield Path(tmp), None
        return
    name = ".um-restore-" + secrets.token_hex(16)
    os.mkdir(name, 0o700, dir_fd=root_fd)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            yield root / name, fd
        finally:
            for entry in os.listdir(fd):
                os.unlink(entry, dir_fd=fd)
            os.close(fd)
    finally:
        os.rmdir(name, dir_fd=root_fd)


def restore(name: str, to: str | None = None, snapshot: str | None = None, clean: bool = False, yes: bool = False):
    zp = Path(snapshot) if snapshot else (snapshots(name) or [None])[-1]
    if not zp:
        die(f"no snapshots for {name}")
    m = _manifest(zp)
    t = _target(m, to).absolute()
    d = diff(name, str(t), str(zp))
    print(f"restore {zp.name} -> {t}: {len(d['changed'])} changed, {len(d['removed'])} missing, {len(d['added'])} new since"
          + (" (new files will be deleted: --clean)" if clean else " (new files kept)"))
    if not yes:
        die("re-run with --yes to do it")
    if t.is_dir():
        create(str(t), name + "-pre-restore", note=f"automatic, before restoring {zp.name}")
    t.mkdir(parents=True, exist_ok=True)
    if _link(t):
        die(f"restore target is a symlink or junction: {t}")
    secure = (os.name == "posix" and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
              and os.open in os.supports_dir_fd and os.rename in os.supports_dir_fd)
    if not secure and os.name != "nt":
        die("safe backup restore is not supported on this platform")
    with contextlib.ExitStack() as stack:
        if secure:
            root_fd = os.open(t, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, root_fd)
        else:
            root_fd = None
            # Keep all root ancestors locked through staging and replacement.
            stack.enter_context(_windows_parent(t, "sentinel", False))
        tmp, stage_fd = stack.enter_context(_stage_dir(t, root_fd))
        z = stack.enter_context(zipfile.ZipFile(zp))
        staged = []
        for i, (rel, info) in enumerate(m["files"].items()):
            member = ("files/" if m.get("version", 1) == 2 else "") + rel
            path = tmp / str(i)
            h, size = hashlib.sha1(), 0
            if secure:
                fd = os.open(str(i), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=stage_fd)
                dst = os.fdopen(fd, "wb")
            else:
                dst = path.open("xb")
            with dst, z.open(member) as src:
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    size += len(chunk)
                    if size > info["size"]:
                        die(f"snapshot size mismatch: {rel}")
                    h.update(chunk)
                    dst.write(chunk)
            if size != info["size"] or h.hexdigest() != info["sha1"]:
                die(f"snapshot checksum mismatch: {rel}")
            staged.append((rel, path))
        for rel, path in staged:
            parts = rel.split("/")
            if secure:
                fd = _parent_fd(root_fd, parts[:-1], True)
                try:
                    try:
                        mode = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False).st_mode
                        if stat.S_ISLNK(mode):
                            die(f"restore path is a symlink: {rel}")
                    except FileNotFoundError:
                        pass
                    os.replace(path.name, parts[-1], src_dir_fd=stage_fd, dst_dir_fd=fd)
                finally:
                    os.close(fd)
            else:
                with _windows_parent(t, rel, True) as parent:
                    dest = parent / parts[-1]
                    if _link(dest):
                        die(f"restore path is a symlink or junction: {dest}")
                    os.replace(path, dest)
        if clean:
            for rel in d["added"]:
                parts = rel.split("/")
                if secure:
                    fd = _parent_fd(root_fd, parts[:-1], False)
                    try:
                        if stat.S_ISLNK(os.stat(parts[-1], dir_fd=fd, follow_symlinks=False).st_mode):
                            die(f"restore path is a symlink: {rel}")
                        os.unlink(parts[-1], dir_fd=fd)
                    finally:
                        os.close(fd)
                else:
                    with _windows_parent(t, rel, False) as parent:
                        dest = parent / parts[-1]
                        if _link(dest):
                            die(f"restore path is a symlink or junction: {dest}")
                        dest.unlink(missing_ok=True)
    print("restored", len(m["files"]), "files")


def main(a):
    if a.cmd == "create":
        create(a.src, a.name, a.note or "")
    elif a.cmd == "list":
        root = data_dir() / "backups"
        names = [a.name] if a.name else sorted(p.name for p in root.glob("*") if p.is_dir()) if root.exists() else []
        for n in names:
            for zp in snapshots(n):
                m = _manifest(zp)
                print(f"{n:28} {zp.name}  {len(m['files']):5} files  {m['source']}  {m.get('note', '')}")
    elif a.cmd == "diff":
        print(json.dumps(diff(a.name, a.target, a.snapshot), indent=1))
    elif a.cmd == "restore":
        restore(a.name, a.to, a.snapshot, a.clean, a.yes)


def register(sub):
    import argparse
    p = sub.add_parser("backup", help="snapshot / diff / restore save folders before you touch them",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")
    q = cs.add_parser("create", help="snapshot a folder")
    q.add_argument("src")
    q.add_argument("--name")
    q.add_argument("--note")
    q.set_defaults(func=main)
    q = cs.add_parser("list", help="list snapshots")
    q.add_argument("name", nargs="?")
    q.set_defaults(func=main)
    q = cs.add_parser("diff", help="what changed since the latest snapshot")
    q.add_argument("name")
    q.add_argument("target", nargs="?")
    q.add_argument("--snapshot")
    q.set_defaults(func=main)
    q = cs.add_parser("restore", help="restore the latest (or --snapshot) snapshot")
    q.add_argument("name")
    q.add_argument("--to")
    q.add_argument("--snapshot")
    q.add_argument("--clean", action="store_true", help="also delete files created after the snapshot")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=main)
