#!/usr/bin/env python3
"""Read the pack's own geometry back and judge it as a renderer would.

Offline checks so far looked at *counts* (weights, bones, influences). This
one looks at the shape itself:

* triangle winding - if the faces are wound inside-out the engine culls the
  visible side and the character renders as holes;
* the UV frame (the two "duv" streams PD2 uses for the tangent frame) - a
  frame that disagrees with the UVs mirrors the normal map's lighting.

Missing enabled drawables and units with no analyzable triangles fail the check.
Drawables without the needed streams (for example legacy shadow meshes) are
reported as uncovered. Tangent agreement is a diagnostic, not a pass threshold.
Source normal-map channel checks are separate (check_nm_convention.py).

    python tools/pd2-port/check_mesh_geometry.py [pack.zip]

The analysis works on any Diesel model pack zip: it discovers the third-person
and optional first-person ``.model`` entries inside the archive automatically
(defaulting to ``dist/Miranda_Romance/Miranda_Romance_LAS.zip``).
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import sys as _dist_sys
_dist_sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "pd2-las"))
import diesel_model  # noqa: E402
from dist_paths import dist_path  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from dmodel import DieselModel, hash_str  # noqa: E402

PACK = dist_path(ROOT, "Miranda_Romance_LAS.zip")


# ------------------------------------------------------------------ helpers
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a):
    m = math.sqrt(dot(a, a))
    return (a[0] / m, a[1] / m, a[2] / m) if m else (0.0, 0.0, 0.0)


def packed_vec(b: bytes):
    """PD2 packs a direction as 4 signed bytes (z, y, x, pad)."""
    return tuple(((b[i] / 255.0) * 2.0 - 1.0) for i in (2, 1, 0))


class Geometry:
    """One geometry section of our own container, decoded exactly."""

    def __init__(self, raw: bytes, sec):
        d = raw[sec.start:sec.end]
        n, hc = struct.unpack_from("<II", d, 0)
        headers = [struct.unpack_from("<II", d, 8 + 8 * i) for i in range(hc)]
        self.n = n
        self.headers = headers
        off = 8 + 8 * hc
        self.pos = []
        self.uv = []
        self.nrm = []
        self.bitangent = []      # channel 22: the V direction
        self.tangent = []        # channel 23: the U direction
        for isz, ity in headers:
            if ity == 1:
                for _ in range(n):
                    self.pos.append(struct.unpack_from("<3f", d, off))
                    off += 12
            elif ity == 7:
                for _ in range(n):
                    if isz == 2:
                        u, v = struct.unpack_from("<2f", d, off)
                        off += 8
                    else:
                        u, v = struct.unpack_from("<2e", d, off)
                        off += 4
                    self.uv.append((u, -v))
            elif ity == 2:
                for _ in range(n):
                    if isz == 3:
                        self.nrm.append(struct.unpack_from("<3f", d, off))
                        off += 12
                    else:
                        self.nrm.append(packed_vec(d[off:off + 4]))
                        off += 4
            elif ity in (20, 22):
                for _ in range(n):
                    if isz == 3:
                        self.bitangent.append(struct.unpack_from("<3f", d, off))
                        off += 12
                    else:
                        self.bitangent.append(packed_vec(d[off:off + 4]))
                        off += 4
            elif ity in (21, 23):
                for _ in range(n):
                    if isz == 3:
                        self.tangent.append(struct.unpack_from("<3f", d, off))
                        off += 12
                    else:
                        self.tangent.append(packed_vec(d[off:off + 4]))
                        off += 4
            elif 0 < isz < len(diesel_model.PAYDAY_ITEM_SIZES):
                off += diesel_model.PAYDAY_ITEM_SIZES[isz] * n
            else:
                raise ValueError(f"unexpected channel size code {isz} (type {ity})")


def meshes_of(model: DieselModel, enabled: dict[int, str] | None):
    """Return checked drawables and explicit gaps in geometry coverage."""
    pending = dict(enabled or {})
    meshes, uncovered = [], []
    for sec in model.sections:
        if sec.tag != "model_data" or sec.obj is None:
            continue
        md = sec.obj
        key = getattr(md, "name_hash", None)
        if enabled is not None and key not in enabled:
            continue
        name = enabled[key] if enabled is not None else f"section {sec.id}"
        # Runtime objects and placeholder/collision sections may have no render atoms.
        atoms = [a for a in getattr(md, "render_atoms", []) if a["tri_count"]]
        if not atoms:
            continue
        pending.pop(key, None)
        pt = model.by_id.get(md.passthrough_id)
        if pt is None or pt.obj is None:
            raise ValueError(f"{name}: no geometry passthrough")
        geo_sec = model.by_id.get(pt.obj.geometry_id)
        top_sec = model.by_id.get(pt.obj.topology_id)
        if geo_sec is None or top_sec is None or top_sec.obj is None:
            raise ValueError(f"{name}: missing geometry or topology section")
        g = Geometry(model.data, geo_sec)
        faces = top_sec.obj.faces
        tris = []
        for atom in atoms:
            # Indices are absolute into the geometry buffer, and a range starts on a triangle.
            start, rem = divmod(atom["base_index"], 3)
            end = start + atom["tri_count"]
            if rem or start < 0 or end <= start or end > len(faces):
                raise ValueError(f"{name}: render atom points outside its triangle list")
            tris.extend(faces[start:end])
        if any(v < 0 or v >= g.n for face in tris for v in face):
            raise ValueError(f"{name}: triangle index outside the vertex buffer")
        gaps = [label for stream, label in ((g.pos, "positions"), (g.nrm, "normals"), (g.uv, "UVs"),
                                            (g.tangent, "tangents"), (g.bitangent, "bitangents"))
                if len(stream) != g.n]
        if gaps:
            uncovered.append(f"{name}: {len(tris)} triangles not analyzed (missing {', '.join(gaps)})")
        else:
            meshes.append((name, g, tris))
    return meshes, uncovered, sorted(pending.values())


def analyse(name: str, g: Geometry, tris) -> dict:
    flipped = 0
    degenerate = 0
    signed_volume = 0.0
    t_sign = []
    frame_hand = []
    zero_tangent = 0
    # Edge-orientation breaks: the exact hole test on a *welded* mesh (a
    # shared edge must be traversed in opposite directions by its two faces).
    # On welded, skinned meshes the vertex-normal heuristic over-fires at
    # joints (blended normals lean away while the winding is correct), so the
    # effective flipped count uses orientation breaks when the mesh has shared
    # edges, and falls back to the normal heuristic for corner-split meshes
    # (like the COLLADA source of the shipped port) where no edges are shared
    # at all.
    edge_dir = {}
    for a, b, c in tris:
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            edge_dir.setdefault(key, []).append(1 if x < y else -1)
    breaks = sum(1 for dirs in edge_dir.values()
                 if len(dirs) == 2 and dirs[0] == dirs[1])
    welded = any(len(dirs) >= 2 for dirs in edge_dir.values())
    for v in range(len(g.tangent)):
        if math.sqrt(dot(g.tangent[v], g.tangent[v])) < 0.1:
            zero_tangent += 1
    for a, b, c in tris:
        p0, p1, p2 = g.pos[a], g.pos[b], g.pos[c]
        gn = cross(sub(p1, p0), sub(p2, p0))
        if math.sqrt(dot(gn, gn)) < 1e-9:
            degenerate += 1
            continue
        gn = norm(gn)
        avg = norm((g.nrm[a][0] + g.nrm[b][0] + g.nrm[c][0],
                    g.nrm[a][1] + g.nrm[b][1] + g.nrm[c][1],
                    g.nrm[a][2] + g.nrm[b][2] + g.nrm[c][2]))
        if dot(gn, avg) < 0:
            flipped += 1
        signed_volume += dot(p0, cross(p1, p2)) / 6.0
        # UV-derived tangent vs the frame the file stores
        u0, v0 = g.uv[a]
        u1, v1 = g.uv[b]
        u2, v2 = g.uv[c]
        du1, dv1 = u1 - u0, v1 - v0
        du2, dv2 = u2 - u0, v2 - v0
        det = du1 * dv2 - du2 * dv1
        if abs(det) > 1e-12:
            e1, e2 = sub(p1, p0), sub(p2, p0)
            t = norm((e1[0] * dv2 - e2[0] * dv1,
                      e1[1] * dv2 - e2[1] * dv1,
                      e1[2] * dv2 - e2[2] * dv1))
            if det < 0:  # normalization drops |det|, not its sign on mirrored UVs
                t = (-t[0], -t[1], -t[2])
            for v in (a, b, c):
                t_sign.append(dot(t, g.tangent[v]))
                nn, tt, bb = g.nrm[v], g.tangent[v], g.bitangent[v]
                frame_hand.append(dot(cross(nn, tt), bb))
    return {
        "name": name,
        "tris": len(tris),
        "flipped": breaks if welded else flipped,
        "normal_flagged": flipped,
        "orientation_breaks": breaks,
        "welded": welded,
        "degenerate": degenerate,
        "volume": signed_volume,
        "tangent_agree": sum(1 for s in t_sign if s > 0) / max(1, len(t_sign)),
        "frame_hand": (sum(frame_hand) / len(frame_hand)) if frame_hand else 0.0,
        "zero_tangent": zero_tangent,
        "verts": len(g.tangent),
    }


def _enabled_for(z: zipfile.ZipFile, model_entry: str, names: set[str]) -> dict[int, str] | None:
    obj_entry = model_entry.removesuffix(".model") + ".object"
    if obj_entry not in names:
        return None
    root = ET.fromstring(z.read(obj_entry))
    enabled = {}
    for el in root.findall(".//graphics//object"):
        if el.get("enabled") == "true":
            name = el.get("name")
            if not name:
                raise ValueError(f"{obj_entry}: unnamed enabled drawable")
            enabled[hash_str(name)] = name
    return enabled


def check_pack(path: Path) -> int:
    flipped = degenerate = tris_total = 0
    incomplete = False
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        models = sorted(n for n in names if n.endswith(".model"))
        if not models:
            raise ValueError("no .model files")
        for entry in models:
            stem = Path(entry).stem
            label = f"{'first' if stem.startswith('fps_') else 'third'} person ({stem})"
            print(f"=== {label} unit")
            enabled = _enabled_for(z, entry, names)
            if enabled is None:
                print("  NOTE: no companion .object; checking all model drawables with render atoms")
            meshes, uncovered, missing = meshes_of(DieselModel.from_bytes(z.read(entry)), enabled)
            for note in uncovered:
                print(f"  WARN: {note}")
            if missing:
                print(f"ERROR: enabled drawables missing geometry in {label}: {', '.join(missing)}")
                incomplete = True
            if not meshes:
                print(f"ERROR: no analyzable triangles in {label} unit (check drawables and geometry streams)")
                incomplete = True
            for name, g, tris in meshes:
                r = analyse(name, g, tris)
                flipped += r["flipped"]
                degenerate += r["degenerate"]
                tris_total += r["tris"]
                print(f"  {name}: {r['tris']} triangles")
                print(f"    winding: {r['flipped']} flipped, {r['degenerate']} degenerate"
                      f"  (signed volume {r['volume'] / 1000:.1f} cm3)")
                print(f"    UV frame: {r['tangent_agree'] * 100:.1f}% of the stored "
                      f"tangents agree with the UVs; handedness {r['frame_hand']:+.3f}; "
                      f"{r['zero_tangent']}/{r['verts']} vertices have no UV frame")
    print(f"\nsummary: {tris_total} triangles, {flipped} inverted, {degenerate} degenerate")
    return int(bool(flipped or degenerate or incomplete))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack", nargs="?", type=Path, default=PACK)
    args = ap.parse_args(argv)
    try:
        return check_pack(args.pack)
    except (OSError, ValueError, KeyError, IndexError, struct.error, ET.ParseError, zipfile.BadZipFile) as error:
        print(f"ERROR: {args.pack}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
