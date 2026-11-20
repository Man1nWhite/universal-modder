"""Validate extracted build inputs by archive and payload, not by sentinel files."""
from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

from pack_checksum import sha256_file

STAMP = ".archive-cache.json"


def _files(tree: Path) -> dict[str, str]:
    return {path.relative_to(tree).as_posix(): sha256_file(path)
            for path in sorted(tree.rglob("*")) if path.is_file() and path != tree / STAMP}


def current(archive: Path, tree: Path) -> bool:
    """An altered archive, missing file, or edited payload invalidates the cache."""
    try:
        saved = json.loads((tree / STAMP).read_text(encoding="utf-8"))
        return (isinstance(saved, dict) and saved.get("archive_sha256") == sha256_file(archive)
                and bool(saved.get("files")) and saved["files"] == _files(tree))
    except (OSError, ValueError):
        return False


def refresh(archive: Path, tree: Path, unpack: Callable[[Path], None],
            required: Iterable[Path | str]) -> None:
    """Extract into an empty staging tree; keep the old tree if unpacking fails."""
    digest = sha256_file(archive)
    tree.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{tree.name}-", dir=tree.parent) as scratch:
        output = Path(scratch) / "payload"
        output.mkdir()
        unpack(output)
        missing = [str(name) for name in required if not (output / name).is_file()]
        if missing:
            raise ValueError(f"{archive} did not contain: {', '.join(missing)}")
        if sha256_file(archive) != digest:
            raise ValueError(f"{archive} changed during extraction")
        stamp = {"archive_sha256": digest, "files": _files(output)}
        (output / STAMP).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
        if tree.is_symlink() or tree.is_file():
            tree.unlink()
        elif tree.exists():
            shutil.rmtree(tree)
        output.rename(tree)
