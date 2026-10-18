#!/usr/bin/env python3
"""Validate/fix the specific Lawson SkinBones mapping defect (Python 3.10+).
Check: python repair_skin_palettes.py lawson_clover.zip
Trial copy: python repair_skin_palettes.py lawson_clover.zip --output lawson_clover_skinfix.zip
Never modifies the input archive. Only known-bad mapping words in .model files
are changed; all other existing ZIP entry contents are preserved. Passing this
check is NOT proof of in-game compatibility.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
from zipfile import ZIP_DEFLATED, ZipFile
SKINBONES = 0x65CC1825
def identity_skin_mappings(bone_count: int, atom_count: int) -> bytes:
    """One full mapping plus one per atom; values index the skin's object list.
    Skeleton object section IDs belong later in SkinBones.object_ids, NOT here.
    This writer uses the same local palette for every atom of a drawable.
    """
    if not 1 <= bone_count <= 32 or atom_count < 1:
        raise ValueError("Expected 1..32 palette bones and at least one atom")
    mapping = struct.pack(f"<{bone_count + 1}I", bone_count, *range(bone_count))
    return struct.pack("<I", atom_count + 1) + mapping * (atom_count + 1)
def _skin_tables(data: bytes):
    """Bounds-checked reader for the DODB v1 containers used by these packs."""
    if len(data) < 16:
        raise ValueError("Truncated model header")
    magic, version, size, count = struct.unpack_from("<4I", data)
    if magic != 0x42444F44 or version != 1:
        raise ValueError("Expected a DODB v1 model")
    if size != len(data):
        raise ValueError("Model file size does not match its header")
    if count > (len(data) - 16) // 12:
        raise ValueError("Invalid section count")
    sections = []
    seen = set()
    pos = 16
    for _ in range(count):
        if pos + 12 > len(data):
            raise ValueError("Truncated section header")
        tag, sid, length = struct.unpack_from("<3I", data, pos)
        start, end = pos + 12, pos + 12 + length
        if end > len(data) or sid in seen:
            raise ValueError("Truncated section or duplicate section ID")
        seen.add(sid)
        sections.append((tag, sid, start, end))
        pos = end
    if pos != len(data):
        raise ValueError("Unexpected trailing model data")
    tables = []
    for tag, sid, pos, end in sections:
        if tag != SKINBONES:
            continue
        def words(n):
            nonlocal pos
            if n < 0 or n > (end - pos) // 4:
                raise ValueError(f"SkinBones {sid}: truncated array")
            values = struct.unpack_from(f"<{n}I", data, pos)
            pos += 4 * n
            return values
        mapping_count, = words(1)
        if mapping_count > (end - pos) // 4:
            raise ValueError(f"SkinBones {sid}: invalid mapping count")
        mappings = []
        for _ in range(mapping_count):
            length, = words(1)
            offset = pos
            mappings.append((offset, words(length)))
        root, bone_count = words(2)
        objects = words(bone_count)
        # One inverse-bind matrix per bone plus the global skin matrix.
        if end - pos != 64 * (bone_count + 1):
            raise ValueError(f"SkinBones {sid}: incorrect matrix payload size")
        tables.append((sid, mappings, objects))
    return tables
def validate_skin_palettes(data: bytes) -> int:
    """Reject out-of-range mapping indices; return number of SkinBones sections."""
    tables = _skin_tables(data)
    for sid, mappings, objects in tables:
        for _, values in mappings:
            if any(v >= len(objects) for v in values):
                raise ValueError(
                    f"SkinBones {sid}: mapping index {max(values)} outside "
                    f"0..{len(objects) - 1} ({len(objects)} bones)"
                )
    return len(tables)
def repair_model(data: bytes) -> tuple[bytes, int]:
    """Repair only the exact writer bug: every mapping duplicates object_ids.
    Valid mappings, including nonidentity mappings, are left alone. Unknown
    invalid mappings are rejected, never guessed, clamped or silently discarded.
    Lengths, offsets, section IDs, object IDs, matrices and geometry stay intact.
    """
    result = bytearray(data)
    changed = 0
    for sid, mappings, objects in _skin_tables(data):
        if not any(v >= len(objects) for _, values in mappings for v in values):
            continue
        if not objects or len(set(objects)) != len(objects) or any(values != objects for _, values in mappings):
            raise ValueError(f"SkinBones {sid}: unknown invalid mapping; refusing repair")
        for offset, values in mappings:
            struct.pack_into(f"<{len(values)}I", result, offset, *range(len(objects)))
        changed += 1
    patched = bytes(result)
    validate_skin_palettes(patched)
    return patched, changed
REPAIR_NOTE = b"""Lawson skin-palette trial repair - 2026-10-18
The prior packs have a reported startup access violation while loading menu
packages. Their rebuilt SkinBones mappings used skeleton object IDs instead of
local bone-array indices. This trial corrects ONLY that confirmed binary defect
in both .model files. It does not establish that the crash is fully resolved.
The original README describes the earlier metadata-only repair; this additional
repair DOES change model mapping bytes. Textures, materials, geometry, weights,
object IDs, matrices and the BeardLib manifest are unchanged.
Close PAYDAY 2. Move ALL older Lawson packs outside the game as backups. Extract
just this trial into PAYDAY 2/assets/mod_overrides/. The original lawson_<character>
folder name inside the ZIP is intentional. Do not nest it another level or leave
duplicate packs installed. SuperBLT and BeardLib are still required.
First confirm that the main menu opens. Then select this character with the
default outfit and inspect the unmasked preview. Test offline only; back up saves
before a heist test. If it crashes again, disable this pack and send the fresh
crash report and newest mods/logs/ log; do not keep retrying all three packs.
IN-GAME RETEST PENDING. Do not treat a successful static check as a working port.
"""
def repair_archive(source: Path, output: Path) -> dict[str, int]:
    """Write a new trial archive, refusing to overwrite any existing file."""
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Output must be a new file; keep the original as a backup")
    changes = {}
    with ZipFile(source) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries")
        roots = {n.split("/")[0] for n in names}
        if len(roots) != 1 or next(iter(roots)) not in {"lawson_clover", "lawson_bonnie", "lawson_sydney"}:
            raise ValueError("Expected a single Lawson pack root")
        root = next(iter(roots))
        models = [n for n in names if n.endswith(".model")]
        if len(models) != 2:
            raise ValueError("Expected menu and third-person models")
        patched = {}
        for name in models:
            patched[name], changes[name] = repair_model(archive.read(name))
        # Finish validation before creating anything. Exclusive create prevents
        # even an accidental overwrite of the user's existing trial or backup.
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as file:
            try:
                with ZipFile(file, "w", compression=ZIP_DEFLATED) as dest:
                    dest.comment = archive.comment
                    for info in archive.infolist():
                        if info.filename != root + "/SKIN_PALETTE_REPAIR.txt":
                            dest.writestr(info, patched[info.filename] if info.filename in patched else archive.read(info))
                    dest.writestr(root + "/SKIN_PALETTE_REPAIR.txt", REPAIR_NOTE)
            except Exception:
                file.close()
                output.unlink()
                raise
    return changes
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, help="Write a trial ZIP, leaving the input unchanged")
    args = parser.parse_args()
    try:
        if args.output:
            for name, count in repair_archive(args.archive, args.output).items():
                print(f"{name}: repaired {count} SkinBones sections")
            print(f"Trial written to {args.output}. In-game retest still required.")
        else:
            with ZipFile(args.archive) as archive:
                models = [n for n in archive.namelist() if n.endswith(".model")]
                if not models:
                    raise ValueError("No models found")
                for name in models:
                    count = validate_skin_palettes(archive.read(name))
                    print(f"{name}: {count} SkinBones sections pass range checks")
    except (ValueError, OSError) as error:
        parser.exit(1, f"ERROR: {error}\n")
if __name__ == "__main__":
    main()
