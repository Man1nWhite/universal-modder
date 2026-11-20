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
    """Read a sidecar naming this ZIP from root (or beside the ZIP if portable)."""
    sidecar = sidecar_path(pack)
    lines = sidecar.read_text(encoding="utf-8").splitlines()
    fields = lines[0].split("  ", 1) if len(lines) == 1 else []
    if len(fields) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
        raise ValueError(f"{sidecar}: expected one '<sha256>  <path>' entry")
    digest, name = fields
    paths = {pack.name} if portable else set()
    if pack.resolve().is_relative_to(root.resolve()):
        paths.add(pack.resolve().relative_to(root.resolve()).as_posix())
    if name not in paths:
        raise ValueError(f"{sidecar}: does not name {pack} from the expected directory: {name!r}")
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
    """Inventory both halves, optionally including paths already recorded by git."""
    paths = set(recorded)
    paths.update(p.relative_to(root).as_posix() for p in (root / "dist").rglob("*") if p.is_file())
    zips = sorted(rel for rel in paths if rel.endswith(".zip"))
    missing = [rel for rel in zips if not (root / rel).is_file() or not sidecar_path(root / rel).is_file()]
    orphan = sorted(rel for rel in paths if rel.endswith(".zip.sha256") and rel.removesuffix(".sha256") not in paths)
    if missing or orphan:
        raise ValueError("incomplete ZIP/checksum inventory: " + ", ".join(missing + orphan))
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
