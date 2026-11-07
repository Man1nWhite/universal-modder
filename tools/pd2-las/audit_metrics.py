"""Reproduce the shading/geometry numbers quoted in the screenshot audits.

The 2026-11-07 slim screenshot review compared a few offline metrics against
"the 2B reference". Several of those numbers did not reproduce, so this script
exists to make every row of that table checkable in one command:

    .venv/bin/python tools/pd2-las/audit_metrics.py \
        --template "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

It reads the shipped packs from ``dist/`` (they are the reviewed artifacts) and,
if given, the 2B LAS template model that the project treats as ground truth.
Nothing is written; the script only reports.

Definitions (all on the ``g_body`` drawable, bind pose, model units = cm):

- **verts / tris** — geometry vertex count and triangle count.
- **area** — summed triangle area in cm^2.
- **tris/1000cm^2** — triangle density.
- **texels/cm** — 1024 / sqrt(area): texel pitch of a 1024x1024 atlas stretched
  over that surface. Comparable across packs because every pack ships 1024^2
  body textures (the 2B reference included).
- **bad verts** — vertices that have at least one incident face whose normal is
  more than 90 degrees off the vertex's own stored normal. Accumulate with a
  union over *all* corners: ``bad[f[:, k]] |= ...`` under-counts when an index
  appears twice in the column (numpy gathers once and the last write wins), so
  the corner list is unioned explicitly here.
- **dup pairs** — pairs of vertices at the same authored position; **diverged**
  counts pairs whose normals differ by more than 30 degrees.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import diesel_model as dm  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _drawable(model_bytes: bytes, want: str = "g_body"):
    mf = dm.ModelFile.read(model_bytes)
    hashlist = dm.decode_custom_hashlist(
        mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    for section in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(section.payload)
        name = next((n for n in hashlist if dm.hash64(n) == md["name_hash"]), "")
        if name == want and md.get("version") == 3:
            gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            return (dm.decode_geometry(mf.by_id(gp["geometry"]).payload),
                    dm.decode_topology(mf.by_id(gp["topology"]).payload))
    raise SystemExit(f"no {want} drawable in model")


def _model_bytes(path: Path) -> bytes:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist()
                     if n.endswith(".model") and "/fps_" not in n
                     and not n.endswith("lod1.model")]
            if not names:
                raise SystemExit(f"no model in {path}")
            return zf.read(names[0])
    return path.read_bytes()


def measure(model_bytes: bytes) -> dict:
    geo, top = _drawable(model_bytes)
    verts = np.asarray(geo["verts"], float)
    normals = np.asarray(geo["normals"], float)
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    faces = np.asarray(top["indices"], int).reshape(-1, 3)

    tri = verts[faces]
    face_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = np.linalg.norm(face_n, axis=1).sum() / 2.0
    face_n /= np.maximum(np.linalg.norm(face_n, axis=1, keepdims=True), 1e-12)

    cos = np.stack([np.einsum("ij,ij->i", face_n, normals[faces[:, k]])
                    for k in range(3)], axis=1)
    bad = set(faces[cos < 0.0].ravel().tolist())

    groups: dict[tuple, list[int]] = {}
    for i, p in enumerate(verts):
        groups.setdefault(tuple(p), []).append(i)
    pairs = [g for g in groups.values() if len(g) > 1]
    diverged = 0
    for g in pairs:
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                if np.degrees(np.arccos(np.clip(normals[g[a]] @ normals[g[b]],
                                                -1, 1))) > 30:
                    diverged += 1

    return {
        "verts": len(verts), "tris": len(faces), "area": area,
        "tris_per_1000cm2": len(faces) / area * 1000,
        "texels_per_cm": 1024 / np.sqrt(area),
        "bad_verts": len(bad), "bad_pct": len(bad) / len(verts) * 100,
        "dup_pairs": sum(len(g) * (len(g) - 1) // 2 for g in pairs),
        "diverged": diverged,
        "diverged_pct": diverged / max(1, sum(len(g) * (len(g) - 1) // 2
                                              for g in pairs)) * 100,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", type=Path, default=Path(
        "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"),
        help="2B LAS template folder (bootstrap.sh extracts it here)")
    ap.add_argument("--dist", type=Path, default=REPO / "dist")
    args = ap.parse_args()

    targets = [("2B reference (PD2)",
                args.template / "2b.model"),
               ("Christie base", args.dist / "Christie_LAS.zip"),
               ("Christie slim", args.dist / "Christie_LAS_Slim.zip")]

    head = (f"{'pack':22s} {'verts':>6s} {'tris':>6s} {'area cm2':>9s} "
            f"{'t/1000cm2':>9s} {'texels/cm':>9s} {'bad verts':>16s} "
            f"{'dup pairs':>10s} {'diverged':>14s}")
    print(head)
    print("-" * len(head))
    for label, path in targets:
        if not Path(path).is_file():
            print(f"{label:22s} missing: {path}")
            continue
        m = measure(_model_bytes(Path(path)))
        print(f"{label:22s} {m['verts']:6d} {m['tris']:6d} {m['area']:9.0f} "
              f"{m['tris_per_1000cm2']:9.0f} {m['texels_per_cm']:9.2f} "
              f"{m['bad_verts']:5d} ({m['bad_pct']:4.1f}%) "
              f"{m['dup_pairs']:10d} {m['diverged']:5d} ({m['diverged_pct']:4.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
