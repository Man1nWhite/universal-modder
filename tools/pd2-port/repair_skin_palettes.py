#!/usr/bin/env python3
"""Inspect and repair PAYDAY 2 Diesel .model SkinBones bone-palette mappings.

In Diesel .model files, SkinBones (0x65CC1825) begins with a Bones mapping
table: one uint32 palette per render atom (+1 trailing set in vanilla models).
Each uint32 entry in a palette must be a 0-based local index into that same
SkinBones section's object_ids / rotations arrays (0 .. count - 1), NOT a
section ID of an Object3D bone in the model file.

Writing Object3D section IDs into SkinBones.bone_mappings causes PAYDAY 2's
native skinning renderer to index past the end of the SkinBones matrix array
and crash to desktop with an access violation (0xc0000005) as soon as the
character mesh is displayed in the menu or a heist.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import dmodel  # noqa: E402
import package_metadata  # noqa: E402

TAG_MODEL = dmodel.TAGS_INV["model_data"]
TAG_SKINBONES = dmodel.TAGS_INV["skinbones"]
TAG_GEOMETRY = dmodel.TAGS_INV["geometry"]
TAG_PASSTHROUGH = dmodel.TAGS_INV["passthroughGP"]


@dataclass(frozen=True)
class SkinPaletteIssue:
    section_id: int
    bone_count: int
    set_count: int
    out_of_range_indices: tuple[int, ...]
    matches_object_ids: bool


def parse_model_bytes(data: bytes) -> tuple[list[dmodel.Section], bool, int | None, int, dict[int, dmodel.Section]]:
    """Parse a Diesel .model binary buffer using dmodel's section readers."""
    sections, legacy, version, filesize = dmodel.read_container(data)
    hl = dmodel.Hashlist()
    by_id: dict[int, dmodel.Section] = {}
    for sec in sections:
        cls = dmodel.PARSERS.get(sec.tag)
        if cls:
            br = dmodel.BR(data)
            br.p = sec.start
            obj = cls()
            obj.parse(br, sec, hl)
            sec.obj = obj
        else:
            sec.obj = None
        by_id[sec.id] = sec
    return sections, legacy, version, filesize, by_id


def inspect_model_skin_palettes(data: bytes) -> list[SkinPaletteIssue]:
    """Return all SkinBones sections whose bone_mappings contain invalid indices."""
    sections, _, _, _, _ = parse_model_bytes(data)
    issues: list[SkinPaletteIssue] = []
    for sec in sections:
        if sec.type != TAG_SKINBONES:
            continue
        sb: dmodel.SkinBones = sec.obj
        bone_count = sb.count
        bad: list[int] = []
        for mapping in sb.bone_mappings:
            for idx in mapping:
                if idx < 0 or idx >= bone_count:
                    bad.append(idx)
        if bad:
            matches_obj_ids = all(
                list(mapping) == list(sb.object_ids) for mapping in sb.bone_mappings
            )
            issues.append(
                SkinPaletteIssue(
                    section_id=sec.id,
                    bone_count=bone_count,
                    set_count=len(sb.bone_mappings),
                    out_of_range_indices=tuple(bad),
                    matches_object_ids=matches_obj_ids,
                )
            )
    return issues


def validate_model_skinning(data: bytes) -> list[str]:
    """Validate container layout, SkinBones palettes, and skinned Geometry indices."""
    errors: list[str] = []
    sections, legacy, version, filesize, by_id = parse_model_bytes(data)
    if not legacy and version != 1:
        errors.append(f"Unexpected DODB version {version}")
    if filesize != len(data):
        errors.append(f"Header filesize {filesize} != actual {len(data)}")

    for sec in sections:
        if sec.start <= 0 or sec.end > len(data):
            errors.append(
                f"Section {sec.id} ({sec.tag}) bounds {sec.start}..{sec.end} exceed {len(data)}"
            )

    for sec in sections:
        if sec.type != TAG_SKINBONES:
            continue
        sb: dmodel.SkinBones = sec.obj
        bone_count = sb.count
        if bone_count <= 0 or len(sb.object_ids) != bone_count or len(sb.rotations) != bone_count:
            errors.append(
                f"SkinBones {sec.id}: invalid count ({bone_count}) / object_ids ({len(sb.object_ids)}) "
                f"/ rotations ({len(sb.rotations)})"
            )
        if sb.remaining:
            errors.append(f"SkinBones {sec.id}: unexpected trailing bytes ({len(sb.remaining)})")
        if not sb.bone_mappings:
            errors.append(f"SkinBones {sec.id}: empty bone_mappings")
        for set_idx, mapping in enumerate(sb.bone_mappings):
            if len(mapping) != bone_count:
                errors.append(
                    f"SkinBones {sec.id} set {set_idx}: mapping length {len(mapping)} != bone_count {bone_count}"
                )
            bad = [idx for idx in mapping if idx < 0 or idx >= bone_count]
            if bad:
                errors.append(
                    f"SkinBones {sec.id} set {set_idx}: {len(bad)} out-of-range indices "
                    f"(max={max(bad)}, bone_count={bone_count})"
                )

    for sec in sections:
        if sec.type != TAG_MODEL:
            continue
        md: dmodel.Model = sec.obj
        if md.version == 6 or getattr(md, "skinbones_id", 0) == 0:
            continue
        sb_sec = by_id.get(md.skinbones_id)
        if sb_sec is None or sb_sec.type != TAG_SKINBONES:
            errors.append(f"Model {sec.id}: missing SkinBones section {md.skinbones_id}")
            continue
        sb: dmodel.SkinBones = sb_sec.obj
        if len(sb.bone_mappings) < len(md.render_atoms):
            errors.append(
                f"Model {sec.id}: SkinBones {md.skinbones_id} has {len(sb.bone_mappings)} sets "
                f"for {len(md.render_atoms)} atoms"
            )
        pg_sec = by_id.get(md.passthrough_id)
        if pg_sec is None or pg_sec.type != TAG_PASSTHROUGH:
            errors.append(f"Model {sec.id}: missing PassthroughGP {md.passthrough_id}")
            continue
        pg: dmodel.PassthroughGP = pg_sec.obj
        geom_sec = by_id.get(pg.geometry_id)
        if geom_sec is None or geom_sec.type != TAG_GEOMETRY:
            errors.append(f"Model {sec.id}: missing Geometry {pg.geometry_id}")
            continue
        geom: dmodel.DieselGeometry = geom_sec.obj
        if len(geom.joints) != geom.vert_count:
            errors.append(
                f"Model {sec.id}: Geometry {pg.geometry_id} blend index count "
                f"{len(geom.joints)} != vert_count {geom.vert_count}"
            )
            continue
        for atom_idx, atom in enumerate(md.render_atoms):
            palette_len = len(sb.bone_mappings[atom_idx])
            v0 = atom["base_vertex"]
            v1 = v0 + atom["geo_len"]
            for vi in range(v0, v1):
                w4 = geom.weights4(vi)
                for slot_idx, bi in enumerate(geom.joints[vi]):
                    if slot_idx < len(w4) and w4[slot_idx] == 0.0 and bi == 0:
                        continue
                    if bi < 0 or bi >= palette_len:
                        errors.append(
                            f"Model {sec.id} atom {atom_idx} vert {vi}: blend index {bi} >= palette_len {palette_len}"
                        )
                        break
    return errors


def repair_model_skin_palettes(data: bytes) -> tuple[bytes, list[int]]:
    """Rewrite any out-of-range SkinBones.bone_mappings in place to 0..bone_count-1.

    Returns (repaired_bytes, repaired_section_ids).
    """
    sections, _, _, _, _ = parse_model_bytes(data)
    buf = bytearray(data)
    repaired_ids: list[int] = []

    for sec in sections:
        if sec.type != TAG_SKINBONES:
            continue
        sb: dmodel.SkinBones = sec.obj
        bone_count = sb.count
        has_bad = any(
            idx < 0 or idx >= bone_count
            for mapping in sb.bone_mappings
            for idx in mapping
        )
        if not has_bad:
            continue
        if any(len(mapping) != bone_count for mapping in sb.bone_mappings):
            raise ValueError(
                f"SkinBones section {sec.id} mapping lengths {[len(m) for m in sb.bone_mappings]} "
                f"do not match bone_count {bone_count}; cannot patch in place"
            )
        rebuilt_bones = bytearray()
        rebuilt_bones += struct.pack("<I", len(sb.bone_mappings))
        local_palette = struct.pack(f"<{bone_count}I", *range(bone_count))
        for _ in sb.bone_mappings:
            rebuilt_bones += struct.pack("<I", bone_count)
            rebuilt_bones += local_palette
        expected_bones_bytes = 4 + len(sb.bone_mappings) * (4 + 4 * bone_count)
        if len(rebuilt_bones) != expected_bones_bytes:
            raise ValueError(
                f"SkinBones section {sec.id} rebuilt header size {len(rebuilt_bones)} != {expected_bones_bytes}"
            )
        buf[sec.start : sec.start + expected_bones_bytes] = rebuilt_bones
        repaired_ids.append(sec.id)

    repaired = bytes(buf)
    errors = validate_model_skinning(repaired)
    if errors:
        raise ValueError("Repaired model failed validation: " + "; ".join(errors[:5]))
    return repaired, repaired_ids


def repair_archive_skin_palettes(archive: Path) -> dict[str, list[int]]:
    """Atomically repair all .model files in a Lawson ZIP and refresh metadata."""
    character = archive.stem.removeprefix("lawson_")
    prefix = f"lawson_{character}/"
    temporary = None
    repaired_by_entry: dict[str, list[int]] = {}
    try:
        with ZipFile(archive) as source:
            names = source.namelist()
            if not names or any(not n.startswith(prefix) for n in names):
                raise ValueError(f"Unexpected ZIP root in {archive}")
            if len(names) != len(set(names)):
                raise ValueError(f"Duplicate ZIP entries in {archive}")
            textures = [n[len(prefix) :] for n in names if n.endswith(".texture")]
            metadata = package_metadata.package_metadata(character, textures)
            with tempfile.NamedTemporaryFile(
                dir=archive.parent, suffix=".zip", delete=False
            ) as tmp:
                temporary = Path(tmp.name)
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as output:
                output.comment = source.comment
                for info in source.infolist():
                    if info.filename in {prefix + n for n in metadata}:
                        continue
                    payload = source.read(info)
                    if info.filename.endswith(".model"):
                        payload, fixed_ids = repair_model_skin_palettes(payload)
                        repaired_by_entry[info.filename] = fixed_ids
                    output.writestr(info, payload)
                for name, data in metadata.items():
                    output.writestr(prefix + name, data)
        temporary.replace(archive)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return repaired_by_entry


def inspect_target(path: Path) -> dict[str, list[str]]:
    """Validate a .model file or a .zip containing .model files."""
    if path.suffix == ".model":
        errs = validate_model_skinning(path.read_bytes())
        return {str(path): errs} if errs else {}
    if path.suffix == ".zip":
        problems: dict[str, list[str]] = {}
        with ZipFile(path) as zf:
            model_names = [n for n in zf.namelist() if n.endswith(".model")]
            if not model_names:
                problems[str(path)] = ["Archive contains no .model files"]
            for name in model_names:
                errs = validate_model_skinning(zf.read(name))
                if errs:
                    problems[f"{path}:{name}"] = errs
        return problems
    raise ValueError(f"Unsupported target {path}; expected .model or .zip")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path, nargs="+", help=".zip or .model files")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; exit non-zero if any SkinBones or skinning errors exist",
    )
    args = parser.parse_args()

    if args.check:
        had_errors = False
        for target in args.targets:
            problems = inspect_target(target)
            if problems:
                had_errors = True
                for key, errs in problems.items():
                    for err in errs:
                        print(f"FAIL {key}: {err}")
            else:
                print(f"OK   {target}")
        if had_errors:
            raise SystemExit(1)
        return

    for target in args.targets:
        if target.suffix == ".model":
            repaired, fixed_ids = repair_model_skin_palettes(target.read_bytes())
            target.write_bytes(repaired)
            print(f"Repaired {target}: SkinBones sections {fixed_ids}")
        elif target.suffix == ".zip":
            report = repair_archive_skin_palettes(target)
            print(f"Repaired {target}: {report}")
        else:
            raise ValueError(f"Unsupported target {target}; expected .model or .zip")


if __name__ == "__main__":
    main()
