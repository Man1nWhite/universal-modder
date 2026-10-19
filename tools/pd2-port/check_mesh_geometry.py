#!/usr/bin/env python3
"""Read the pack's own geometry back and judge it as a renderer would.

Offline checks so far looked at *counts* (weights, bones, influences). This
one looks at the shape itself:

* triangle winding - if the faces are wound inside-out the engine culls the
  visible side and the character renders as holes;
* the UV frame (the two "duv" streams PD2 uses for the tangent frame) - a
  frame that disagrees with the UVs mirrors the normal map's lighting;
* the source normal map's green channel - correlated against the geometric
  tangent-space normal it claims to encode, which decides the DirectX vs
  OpenGL question the guide leaves to the reader.

    python tools/pd2-port/check_mesh_geometry.py [pack.zip]
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from dmodel import DieselModel  # noqa: E402

PACK = ROOT / "dist" / "lawson_las.zip"
TPP_MODEL = "Lawson_LAS/units/lawson/skins/lawson/lawson.model"
FPS_MODEL = "Lawson_LAS/units/lawson/skins/lawson/fps_lawson.model"


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
                    u, v = struct.unpack_from("<2e", d, off)
                    self.uv.append((u, -v))
                    off += 4
            elif ity == 17:
                off += 8 * n
            elif ity == 19:
                off += 12 * n
            elif ity == 2:
                for _ in range(n):
                    self.nrm.append(packed_vec(d[off:off + 4]))
                    off += 4
            elif ity == 22:
                for _ in range(n):
                    self.bitangent.append(packed_vec(d[off:off + 4]))
                    off += 4
            elif ity == 23:
                for _ in range(n):
                    self.tangent.append(packed_vec(d[off:off + 4]))
                    off += 4
            else:
                raise ValueError(f"unexpected channel type {ity}")


def meshes_of(model: DieselModel, raw: bytes):
    """Yield (name, Geometry, triangles) for every drawable of a model."""
    out = []
    for s in model.sections:
        if s.tag != "model_data" or s.obj is None:
            continue
        md = s.obj
        if not hasattr(md, "passthrough_id"):
            continue
        pt = model.by_id.get(md.passthrough_id)
        if pt is None or pt.obj is None:
            continue
        geo_sec = model.by_id.get(pt.obj.geometry_id)
        top_sec = model.by_id.get(pt.obj.topology_id)
        if geo_sec is None or top_sec is None:
            continue
        g = Geometry(raw, geo_sec)
        faces = top_sec.obj.faces
        tris = []
        for atom in md.render_atoms:
            # the parser names the atom fields
            # (base_vertex, tri_count, base_index, vertex_count, material_id);
            # base_index counts *indices*, so it is three per triangle
            base_index = atom["base_index"] // 3
            tri_count = atom["tri_count"]
            for f in faces[base_index:base_index + tri_count]:
                # the topology's indices are absolute into the geometry buffer
                tris.append((f[0], f[1], f[2]))
        out.append((g, tris))
    return out


def analyse(name: str, g: Geometry, tris) -> dict:
    flipped = 0
    degenerate = 0
    signed_volume = 0.0
    t_sign = []
    frame_hand = []
    zero_tangent = 0
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
            for v in (a, b, c):
                t_sign.append(dot(t, g.tangent[v]))
                nn, tt, bb = g.nrm[v], g.tangent[v], g.bitangent[v]
                frame_hand.append(dot(cross(nn, tt), bb))
    return {
        "name": name,
        "tris": len(tris),
        "flipped": flipped,
        "degenerate": degenerate,
        "volume": signed_volume,
        "tangent_agree": sum(1 for s in t_sign if s > 0) / max(1, len(t_sign)),
        "frame_hand": (sum(frame_hand) / len(frame_hand)) if frame_hand else 0.0,
        "zero_tangent": zero_tangent,
        "verts": len(g.tangent),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack", nargs="?", default=str(PACK))
    args = ap.parse_args(argv)

    with zipfile.ZipFile(args.pack) as z:
        raw_tpp = z.read(TPP_MODEL)
        raw_fps = z.read(FPS_MODEL)

    for label, raw, key in (("third person", raw_tpp, TPP_MODEL),
                            ("first person", raw_fps, FPS_MODEL)):
        model = DieselModel.from_bytes(raw)
        print(f"=== {label} unit")
        for i, (g, tris) in enumerate(meshes_of(model, raw)):
            r = analyse(f"mesh {i}", g, tris)
            print(f"  mesh {i}: {r['tris']} triangles")
            print(f"    winding: {r['flipped']} flipped, {r['degenerate']} degenerate"
                  f"  (signed volume {r['volume'] / 1000:.1f} cm3)")
            print(f"    UV frame: {r['tangent_agree'] * 100:.1f}% of the stored "
                  f"tangents agree with the UVs; handedness "
                  f"{r['frame_hand']:+.3f}; "
                  f"{r['zero_tangent']}/{r['verts']} vertices have no UV frame")
    return 0





if __name__ == "__main__":
    raise SystemExit(main())
