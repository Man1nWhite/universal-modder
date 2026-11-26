"""Read and write sha256sum sidecars for distribution and scratch packs.

Run from the repository root to verify every pair under dist/:
    python tools/pd2-las/pack_checksum.py
"""
from __future__ import annotations
import hashlib
import re
import sys
from collections.abc import Iterable
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sidecar_path(pack: Path) -> Path:
    return pack.with_name(pack.name + ".sha256")


def read_checksum(pack: Path, root: Path, *, portable: bool = False) -> str:
    """Read a sidecar naming this ZIP from root (or beside the ZIP if portable).

    Handles CRLF line endings, trims surrounding whitespace, and validates
    that the sidecar names exactly the expected file. Portable sidecars (for
    scratch/custom builds) may name only the basename.
    """
    sidecar = sidecar_path(pack)
    try:
        content = sidecar.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"{sidecar}: cannot read sidecar: {e}") from e
    # Handle CRLF and strip trailing whitespace/newlines; reject multi-line sidecars
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"{sidecar}: expected one '<sha256>  <path>' entry, got {len(lines)} lines")
    # Split on exactly two spaces as per sha256sum format, but also tolerate any whitespace
    if "  " in lines[0]:
        fields = lines[0].split("  ", 1)
    else:
        # Fallback: split on whitespace for non-standard sidecars (still require 64-hex digest)
        parts = lines[0].split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            fields = parts
        else:
            fields = []
    if len(fields) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
        raise ValueError(f"{sidecar}: expected one '<sha256>  <path>' entry")
    digest, name = fields[0].strip(), fields[1].strip()
    paths = {pack.name} if portable else set()
    try:
        if pack.resolve().is_relative_to(root.resolve()):
            paths.add(pack.resolve().relative_to(root.resolve()).as_posix())
    except (OSError, ValueError):
        pass
    if name not in paths:
        raise ValueError(f"{sidecar}: does not name {pack} from the expected directory: {name!r} (expected one of {sorted(paths)!r})")
    return digest.lower()


def write_checksum(pack: Path, *, root: Path | None = None) -> str:
    """Write a repo-relative sidecar or a portable adjacent one for custom output."""
    digest = sha256_file(pack)
    name = pack.resolve().relative_to(root.resolve()).as_posix() if root else pack.name
    sidecar_path(pack).write_text(f"{digest}  {name}\n", encoding="utf-8", newline="\n")
    return digest


def verify_checksum(pack: Path, root: Path, *, portable: bool = False) -> str:
    """Require both files, the correct target path, and the correct digest."""
    wanted = read_checksum(pack, root, portable=portable)
    actual = sha256_file(pack)
    if actual != wanted:
        raise ValueError(f"{pack}: ZIP does not match its checksum (actual {actual}, expected {wanted})")
    return actual


def write_pack_checksum(pack: Path, repo: Path) -> str:
    """Keep distributed checksums repo-relative and scratch checksums portable."""
    return write_checksum(pack, root=repo if pack.resolve().is_relative_to(repo.resolve() / "dist") else None)


def distribution_zips(root: Path, recorded: Iterable[str] = ()) -> list[str]:
    """Inventory both halves, optionally including paths already recorded by git.

    Returns sorted, deduplicated ZIP paths. Validates that every ZIP has a
    matching .sha256 sidecar and vice versa, with distinct error messages
    for missing vs orphan sidecars to aid debugging.
    """
    paths = set(recorded)
    if (root / "dist").is_dir():
        paths.update(p.relative_to(root).as_posix() for p in (root / "dist").rglob("*") if p.is_file())
    zips = sorted({rel for rel in paths if rel.endswith(".zip")})
    # Deduplicate sidecar check: normalize recorded paths to avoid double counting
    missing = [rel for rel in zips if not (root / rel).is_file() or not sidecar_path(root / rel).is_file()]
    orphan = sorted(rel for rel in paths if rel.endswith(".zip.sha256") and rel.removesuffix(".sha256") not in paths and rel.removesuffix(".sha256") not in zips)
    if missing or orphan:
        details = []
        if missing:
            details.append(f"missing sidecar or ZIP: {', '.join(missing)}")
        if orphan:
            details.append(f"orphan sidecar without ZIP: {', '.join(orphan)}")
        raise ValueError("incomplete ZIP/checksum inventory: " + "; ".join(details))
    if not zips:
        raise ValueError("no distribution ZIPs found")
    return zips


def main() -> int:
    root = Path.cwd()
    try:
        zips = distribution_zips(root)
        for rel in zips:
            verify_checksum(root / rel, root)
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"{len(zips)} distribution ZIPs match their checksums")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
