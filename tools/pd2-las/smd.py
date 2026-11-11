"""SMD (Studiomdl Data) read/write — the text hand-off format for Blender.

Every Source toolchain agrees on SMD: Crowbar, Blender Source Tools, SourceIO and
`studiomdl` itself all read it, it is plain text, and it carries exactly what the
port needs — per-vertex positions, normals, UVs and **weightmap links**. That
makes it the one format this repo can emit in pure Python and hand to a Windows
machine with Blender on it, without owning Blender here, without Crowbar, and
without shipping a copy of anyone's asset.

Format (Valve Developer Community, `SMD`), all blocks whitespace-separated,
`//` to end of line is a comment::

    version 1
    nodes                       // id "name" parent   (-1 = world)
    skeleton                    // time N, then id px py pz rx ry rz (radians, local)
    triangles                   // material, then per-vertex:
                                //   parent px py pz nx ny nz u v links ID W [ID W ...]

Three things this module is deliberately strict about, because they are where a
round-trip silently loses a rig:

* **weights.** SMD allows any number of links; `ModelData.SkinVertex` carries at
  most three (the VVD limit) and Diesel's palette is finer still. Links beyond
  the third are dropped and the surviving weights renormalised, and the drop is
  *counted* — `SmdMesh.clamped_links` is non-zero only when an import lost data,
  so a test can assert it instead of trusting it.
* **skeleton frames.** A reference mesh has one frame; an animation SMD has
  many. Parsing an animated SMD as a reference mesh would bake frame 0 as the
  bind pose, so that is reported rather than silently done.
* **space.** No flip, no scale: SMD and `ModelData` are both in Source units,
  `Z` up, bone-local rotations. (Blender's importer flips; that is its job.)

Read + write, and a `--from` CLI that turns any `.gma`/`.vpk`/`.zip` addon into
per-model `.smd` + stub `.qc` files on disk for the Blender side:

    python tools/pd2-las/smd.py path/to/addon.gma --out build/smd
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_model import (  # noqa: E402 - ModelData here, the rest via smd_to_model
    Bone,
    ModelData,
    SkinVertex,
    SubMesh,
)

#: Links kept per vertex. VVD stores three; anything past that is dropped and
#: renormalised, and the count is reported (`SmdMesh.clamped_links`).
MAX_LINKS = 3


class SmdError(ValueError):
    pass


@dataclass
class SmdVertex:
    parent: int
    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]
    links: tuple[tuple[int, float], ...] = ()


@dataclass
class SmdMesh:
    """One material's triangles, in the SMD's own vertex order."""

    material: str
    vertices: list[SmdVertex] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)
    clamped_links: int = 0  # vertices whose 4th+ link was dropped


@dataclass
class SmdModel:
    name: str = "model"
    nodes: list[tuple[str, int]] = field(default_factory=list)  # (name, parent)
    skeleton: list[tuple[int, tuple[float, float, float], tuple[float, float, float]]] = field(
        default_factory=list
    )  # (id, pos, rot radians)
    meshes: list[SmdMesh] = field(default_factory=list)
    frames: int = 1

    @property
    def triangle_count(self) -> int:
        return sum(len(m.triangles) for m in self.meshes)


# ------------------------------------------------------------------- parsing


def _strip_comments(line: str) -> str:
    cut = line.find("//")
    return line if cut < 0 else line[:cut]


def parse_smd(text: str, name: str = "model") -> SmdModel:
    """Parse an SMD reference mesh into bones, per-material vertices, triangles."""
    model = SmdModel(name=name)
    block = None
    pending_material: str | None = None
    pending_tri: list[SmdVertex] = []
    frame_times: list[int] = []

    def flush() -> None:
        nonlocal pending_material, pending_tri
        if pending_material is None:
            return
        if len(pending_tri) % 3:
            raise SmdError(
                f"material {pending_material!r}: {len(pending_tri)} vertices "
                "is not a multiple of 3"
            )
        mesh = SmdMesh(material=pending_material)
        mesh.vertices = list(pending_tri)
        mesh.triangles = [(i, i + 1, i + 2) for i in range(0, len(mesh.vertices), 3)]
        model.meshes.append(mesh)
        pending_material, pending_tri = None, []

    for raw in text.splitlines():
        line = _strip_comments(raw).strip()
        if not line:
            continue
        parts = line.split()
        head = parts[0].lower()
        if head in ("version", "nodes", "skeleton", "triangles", "vertexanimation", "end"):
            if head == "end":
                flush()
                block = None
            elif head in ("nodes", "skeleton", "triangles", "vertexanimation"):
                flush()
                block = head
                if head == "triangles":
                    pending_material = None
            continue
        if block == "nodes":
            if len(parts) != 3:
                raise SmdError(f"nodes line needs id name parent: {line!r}")
            model.nodes.append((parts[1].strip('"'), int(parts[2])))
        elif block == "skeleton":
            if head == "time":
                frame_times.append(int(parts[1]))
            else:
                if len(parts) != 7:
                    raise SmdError(f"skeleton line needs 7 fields: {line!r}")
                model.skeleton.append(
                    (
                        int(parts[0]),
                        (float(parts[1]), float(parts[2]), float(parts[3])),
                        (float(parts[4]), float(parts[5]), float(parts[6])),
                    )
                )
        elif block == "triangles":
            if len(parts) == 1:
                flush()
                pending_material = parts[0]
                continue
            if len(parts) < 9:
                raise SmdError(f"vertex needs at least 9 fields: {line!r}")
            parent = int(parts[0])
            pos = (float(parts[1]), float(parts[2]), float(parts[3]))
            normal = (float(parts[4]), float(parts[5]), float(parts[6]))
            uv = (float(parts[7]), float(parts[8]))
            links: list[tuple[int, float]] = []
            # A Source SMD writes "<links> id w [id w ...]" before the pairs, so
            # the count is skipped rather than trusted: a mismatch is caught by
            # the pair-parity check below instead of silently shifting fields.
            rest = parts[9:]
            if rest and rest[0].isdigit() and (len(rest) - 1) % 2 == 0:
                rest = rest[1:]
            if len(rest) % 2:
                raise SmdError(f"weight links come in id/weight pairs: {line!r}")
            for i in range(0, len(rest), 2):
                links.append((int(rest[i]), float(rest[i + 1])))
            pending_tri.append(SmdVertex(parent, pos, normal, uv, tuple(links)))
    flush()
    model.frames = max(1, len(frame_times))
    if model.frames > 1:
        # Frame 0 is the bind pose; parsing an animation silently as a reference
        # mesh is the failure this flag exists to prevent.
        raise SmdError(
            f"{name}: {model.frames} skeleton frames — this is an animation, "
            "not a reference mesh"
        )
    return model


def read_smd(path: Path | str) -> SmdModel:
    path = Path(path)
    return parse_smd(path.read_text(encoding="utf-8", errors="replace"), name=path.stem)


# ------------------------------------------------------------------- writing


def _f(value: float) -> str:
    text = f"{value:.6f}"
    return "0.000000" if text == "-0.000000" else text


def write_smd(model: SmdModel) -> str:
    """Serialise to SMD text. Round-trips through `parse_smd` to 6 decimals."""
    out = ["version 1", "nodes"]
    ids: dict[str, int] = {}
    for index, (name, parent) in enumerate(model.nodes):
        ids[name] = index
        out.append(f'{index} "{name}" {parent}')
    out.append("end")
    out.append("skeleton")
    out.append("time 0")
    for bone_id, pos, rot in model.skeleton:
        out.append(
            f"{bone_id} {_f(pos[0])} {_f(pos[1])} {_f(pos[2])} "
            f"{_f(rot[0])} {_f(rot[1])} {_f(rot[2])}"
        )
    out.append("end")
    out.append("triangles")
    for mesh in model.meshes:
        out.append(mesh.material)
        for vertex in mesh.vertices:
            links = "".join(f" {bid} {_f(w)}" for bid, w in vertex.links)
            out.append(
                f"{vertex.parent} {_f(vertex.pos[0])} {_f(vertex.pos[1])} "
                f"{_f(vertex.pos[2])} {_f(vertex.normal[0])} {_f(vertex.normal[1])} "
                f"{_f(vertex.normal[2])} {_f(vertex.uv[0])} {_f(vertex.uv[1])} "
                f"{len(vertex.links)}{links}"
            )
    out.append("end")
    return "\n".join(out) + "\n"


# ------------------------------------------------------- ModelData <-> SMD

#: SMD stores local Tait-Bryan angles in radians; `Bone` stores a quaternion
#: (x, y, z, w). The two conversions below are exact for any rotation, because a
#: ValveBiped bind pose is *not* identity (the L4D2 survivor's pelvis is a 90°
#: turn about X) — writing zeros there would silently destroy the rig.
def model_to_smd(model: ModelData, name: str | None = None) -> tuple[SmdModel, list[str]]:
    """`ModelData` → SMD. Returns the model and a list of fidelity warnings."""
    warnings: list[str] = []
    nodes = [(b.name, b.parent) for b in model.bones]
    skeleton = []
    for i, bone in enumerate(model.bones):
        try:
            rot = quat_to_euler(bone.quat)
        except ValueError as exc:  # pragma: no cover - only for non-unit quats
            warnings.append(f"bone {bone.name!r}: {exc}; rotation written as zero")
            rot = (0.0, 0.0, 0.0)
        skeleton.append((i, bone.pos, rot))

    smd = SmdModel(name=name or model.name, nodes=nodes, skeleton=skeleton)
    for sub in model.meshes:
        mesh = SmdMesh(material=sub.material)
        for tri_start in range(0, len(sub.triangle_indices), 3):
            for gi in sub.triangle_indices[tri_start : tri_start + 3]:
                vert = model.vertices[gi]
                links = tuple(vert.weights)
                if len(links) > MAX_LINKS:
                    mesh.clamped_links += 1
                    links = _clamp(links)
                elif links:
                    links = _renormalise(links)
                mesh.vertices.append(
                    SmdVertex(
                        parent=_dominant(links),
                        pos=vert.pos,
                        normal=vert.normal,
                        uv=vert.uv,
                        links=links,
                    )
                )
        # SMD carries no explicit index buffer: consecutive triples *are* the
        # triangles, which is why shared vertices are repeated above.
        mesh.triangles = [
            (i, i + 1, i + 2) for i in range(0, len(mesh.vertices), 3)
        ]
        smd.meshes.append(mesh)
    return smd, warnings


def _clamp(links: tuple[tuple[int, float], ...]) -> tuple[tuple[int, float], ...]:
    """Keep the strongest `MAX_LINKS` links and renormalise (VVD's hard limit)."""
    top = sorted(links, key=lambda pair: pair[1], reverse=True)[:MAX_LINKS]
    return _renormalise(tuple(top))


def _renormalise(links: tuple[tuple[int, float], ...]) -> tuple[tuple[int, float], ...]:
    total = sum(weight for _, weight in links)
    if total <= 0 or abs(total - 1.0) < 1e-9:
        return links
    return tuple((bone, weight / total) for bone, weight in links)


def _dominant(links: tuple[tuple[int, float], ...]) -> int:
    """The SMD 'parent bone' field: the heaviest link (0 when unweighted)."""
    if not links:
        return 0
    return max(links, key=lambda pair: pair[1])[0]


def quat_to_euler(q: tuple[float, float, float, float]) -> tuple[float, float, float]:
    """(x, y, z, w) → SMD ``rotX rotY rotZ`` (pitch, yaw, roll) in radians.

    Source's convention: the bone's rotation is ``Rz(roll) @ Ry(yaw) @ Rx(pitch)``.
    That composition fixes the matrix rows used below —

    ``Rz(roll)@Ry(yaw) = [[cr·cy, -sr, cr·sy], [sr·cy, cr, sr·sy], [-sy, 0, cy]]``

    — so ``yaw = asin(-m20)``, ``pitch = atan2(m21, m22)`` and
    ``roll = atan2(m10, m00)``. `_euler_to_quat` is the exact inverse, and the
    round-trip is asserted against the 104 real L4D2 bones in the test suite,
    because a ValveBiped bind pose is not identity (the pelvis is a 90° turn).
    """
    import math

    x, y, z, w = q
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm < 1e-9:
        raise ValueError("degenerate (zero-length) quaternion")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    m00 = 1.0 - 2.0 * (y * y + z * z)
    m10 = 2.0 * (x * y + w * z)
    m20 = 2.0 * (x * z - w * y)
    m21 = 2.0 * (y * z + w * x)
    m22 = 1.0 - 2.0 * (x * x + y * y)
    yaw = math.asin(max(-1.0, min(1.0, -m20)))
    pitch = math.atan2(m21, m22)
    roll = math.atan2(m10, m00)
    return (_clean(pitch), _clean(yaw), _clean(roll))


def _clean(angle: float) -> float:
    """Drop float noise so a round-trip prints 0.000000 instead of -2e-16."""
    return 0.0 if abs(angle) < 1e-9 else angle


def _euler_to_quat(rot: tuple[float, float, float]) -> tuple[float, float, float, float]:
    """SMD ``rotX rotY rotZ`` → (x, y, z, w); inverse of `quat_to_euler`.

    Composed as ``Rz(roll) @ Ry(yaw) @ Rx(pitch)`` (the order Source uses), then
    converted matrix → quaternion with the usual largest-component branch. Done
    in two steps on purpose: an inline quaternion product here is easy to get
    subtly wrong, and this form is checkable against the composed matrix.
    """
    import math

    pitch, yaw, roll = rot
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cr, sr = math.cos(roll), math.sin(roll)
    m00 = cr * cy
    m01 = cr * sy * sp - sr * cp
    m02 = cr * sy * cp + sr * sp
    m10 = sr * cy
    m11 = sr * sy * sp + cr * cp
    m12 = sr * sy * cp - cr * sp
    m20 = -sy
    m21 = cy * sp
    m22 = cy * cp
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s
    return (x, y, z, w)


def smd_to_model(smd: SmdModel) -> ModelData:
    """SMD → `ModelData`, so `transfer_group`/`diesel_model` can take an SMD.

    Bones are rebuilt from `nodes` (name + parent) with position/rotation from
    `skeleton`; unweighted vertices fall back to their SMD parent-bone field,
    which is what that field means when no weight links are written.
    """
    pos_by_id = {i: pos for i, pos, _rot in smd.skeleton}
    rot_by_id = {i: rot for i, _pos, rot in smd.skeleton}
    bones = [
        Bone(
            name=name,
            parent=parent,
            pos=pos_by_id.get(index, (0.0, 0.0, 0.0)),
            quat=_euler_to_quat(rot_by_id.get(index, (0.0, 0.0, 0.0))),
        )
        for index, (name, parent) in enumerate(smd.nodes)
    ]
    model = ModelData(name=smd.name, bones=bones, materials=[m.material for m in smd.meshes])
    for mesh in smd.meshes:
        base = len(model.vertices)
        for vert in mesh.vertices:
            weights = tuple(vert.links) if vert.links else ((vert.parent, 1.0),)
            model.vertices.append(SkinVertex(vert.pos, vert.normal, vert.uv, weights))
        flat: list[int] = []
        for tri in mesh.triangles:
            flat.extend(base + index for index in tri)
        model.meshes.append(SubMesh(material=mesh.material, triangle_indices=tuple(flat)))
    return model


# --------------------------------------------------------------------- QC stub


def qc_stub(model: ModelData, smd_name: str, modelname: str | None = None) -> str:
    """A minimal `$modelname`/`$body` QC for Crowbar or `studiomdl` to compile.

    Deliberately not clever: `$definebone` lists and `$bodygroup` sets belong to
    whoever exports the mesh, and a QC that guesses them is worse than one that
    does not try. That is also why every `$cdmaterials` folder is deduplicated —
    the L4D2 survivor names seven materials that all live in one folder, and
    seven identical lines read like a bug.
    """
    stem = modelname or Path(smd_name).stem
    folders: list[str] = []
    for material in model.materials or [f"models/{stem}"]:
        clean = material.replace("\\", "/")
        folder = clean.rsplit("/", 1)[0] if "/" in clean else f"models/{stem}"
        if folder not in folders:
            folders.append(folder)
    lines = [
        f'$modelname "{stem}.mdl"',
        f'$body "{Path(smd_name).name}"',
        "$surfaceprop flesh",
        *[f'$cdmaterials "{folder}"' for folder in folders],
        f'$sequence idle "{Path(smd_name).name}" fps 1',
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("addon", type=Path, help=".gma, .vpk or .zip (of either)")
    ap.add_argument("--out", type=Path, required=True, help="folder for the .smd/.qc")
    ap.add_argument("--qc", action="store_true", help="also write a stub .qc per model")
    ap.add_argument("--json", type=Path, help="write a summary of what was exported")
    args = ap.parse_args(argv)

    from inspect_textures import _model_triples, open_container  # noqa: PLC0415

    container = open_container(args.addon)
    args.out.mkdir(parents=True, exist_ok=True)
    written = []
    for mdl, vvd, vtx in _model_triples(container):
        from source_model import load_model  # noqa: PLC0415

        model = load_model(container.read(mdl), container.read(vvd), container.read(vtx))
        smd, warnings = model_to_smd(model, name=Path(mdl).stem)
        smd_path = args.out / f"{Path(mdl).stem}.smd"
        smd_path.write_text(write_smd(smd), encoding="utf-8")
        entry = {
            "model": mdl,
            "smd": str(smd_path),
            "bones": len(smd.nodes),
            "triangles": smd.triangle_count,
            "materials": [m.material for m in smd.meshes],
            "clamped_links": sum(m.clamped_links for m in smd.meshes),
            "warnings": warnings,
        }
        if args.qc:
            qc_path = args.out / f"{Path(mdl).stem}.qc"
            qc_path.write_text(qc_stub(model, smd_path.name), encoding="utf-8")
            entry["qc"] = str(qc_path)
        written.append(entry)
        print(
            f"{smd_path} — {len(smd.nodes)} bones, {smd.triangle_count} tris, "
            f"{len(smd.meshes)} materials"
            + (f", {entry['clamped_links']} vertices clamped to {MAX_LINKS} links"
               if entry["clamped_links"] else "")
        )
        for warning in warnings[:3]:
            print(f"  warning: {warning}")
    if args.json:
        args.json.write_text(json.dumps(written, indent=2))
        print(f"wrote {args.json}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
