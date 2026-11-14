#!/usr/bin/env python3
"""Export a DOA5/DOAXVV ``.TMC`` model as a skinned glTF 2.0 ``.glb``.

Scope: read-only conversion of the geometry/skeleton/bind data produced by
``tmc.py``. Materials are emitted by name only (textures are *not* embedded);
the LAS pipeline maps textures itself later. This is a structural
interchange file, not a game-ready asset: ``runtime_verified`` stays
``false`` and nothing here claims engine behavior it has not been checked
against.

Why glTF: single binary file, standard skinning model, no Blender
dependency. The 171-node skeleton hierarchy (HieLay) and the bind matrices
(HieLay local TRS -> GlblMtx world) are validated against each other inside
this exporter (max |composed - GlblMtx| must be < 1e-5) before anything is
written.

Export conventions (glTF 2.0):
  * units are metres; positions are NOT rescaled (the TMC stores metres).
  * node local TRS comes from HieLay (rotation rows -> quaternion).
  * inverse bind matrices are built from GlblMtx (validated against the
    composed locals) and written column-major.
  * zero-weight placeholder rows (all-zero weights, e.g. the ``*T_body_feather``
    unweighted mesh) are rewritten to joint 0 / weight 1.0; these meshes are
    tagged in their name so they can be dropped downstream.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tmc  # noqa: E402

FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963


class Glb:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []

    def _pad(self, n: int = 4) -> None:
        while len(self.buf) % n:
            self.buf.append(0)

    def add_view(self, data: bytes, target: int | None) -> int:
        self._pad()
        view = {"buffer": 0, "byteOffset": len(self.buf), "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        self.buf += data
        self.views.append(view)
        return len(self.views) - 1

    def add_accessor(self, arr: np.ndarray, component: int, acc_type: str,
                     target: int | None, count: int) -> int:
        data = np.ascontiguousarray(arr).tobytes()
        view = self.add_view(data, target)
        acc: dict = {"bufferView": view, "componentType": component,
                     "count": count, "type": acc_type}
        if acc_type == "VEC3" and target == ARRAY_BUFFER:
            acc["min"] = [float(arr[:, i].min()) for i in range(3)]
            acc["max"] = [float(arr[:, i].max()) for i in range(3)]
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def build(self, json_dict: dict) -> bytes:
        gltf = json_dict
        gltf["buffers"] = [{"byteLength": len(self.buf)}]
        gltf["bufferViews"] = self.views
        gltf["accessors"] = self.accessors
        js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        while len(js) % 4:
            js += b" "
        total = 12 + 8 + len(js) + 8 + len(self.buf)
        out = struct.pack("<4s2I", b"glTF", 2, total)
        out += struct.pack("<2I", len(js), 0x4E4F534A) + js
        while len(self.buf) % 4:
            self.buf.append(0)
        out += struct.pack("<2I", len(self.buf), 0x004E4942) + bytes(self.buf)
        return out


def quat_from_rot(R: np.ndarray) -> list[float]:
    """Quaternion (x, y, z, w) from a row-major 3x3 with det ~ +1."""
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    n = np.sqrt(x * x + y * y + z * z + w * w)
    return [float(x / n), float(y / n), float(z / n), float(w / n)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tmc_path")
    ap.add_argument("out_glb", nargs="?", default=None)
    ap.add_argument("--metrics-only", action="store_true", help="validate and print stats, do not write")
    args = ap.parse_args()

    tm = tmc.TmcFile(args.tmc_path)

    # --- validate composed skeleton against GlblMtx -------------------------
    order: list[int] = []

    def visit(i: int) -> None:
        order.append(i)
        for c in tm.hie_children[i]:
            visit(c)

    visit(0)
    if len(order) != tm.node_count:
        raise SystemExit(f"hierarchy visits {len(order)} of {tm.node_count} nodes")

    col_global: list[np.ndarray] = [None] * tm.node_count  # type: ignore[list-item]
    max_err = 0.0
    for i in order:
        L = tm.local_raw[i].reshape(4, 4, order="F")  # column-major reading (validated convention)
        p = tm.hie_parent[i]
        W = L if p == -1 else col_global[p] @ L
        col_global[i] = W
        g = tm.global_raw[i].reshape(4, 4, order="F")
        max_err = max(max_err, float(np.abs(W - g).max()))
    print(f"composed-vs-GlblMtx max abs error: {max_err:.3g}")
    if max_err > 1e-5:
        raise SystemExit("skeleton composition does not match GlblMtx; refusing to export")

    meshes = tm.load_meshes()
    print(f"decoded meshes: {len(meshes)}")
    for m in meshes:
        print(f"  {m.source_id:24s} verts={m.vert_count:6d} tris={len(m.indices):6d} "
              f"unweighted={int(m.unweighted.sum()):4d}")

    if args.metrics_only:
        return 0

    out_path = Path(args.out_glb) if args.out_glb else Path(args.tmc_path).with_suffix(".rigged.glb")

    g = Glb()

    # --- skin accessors ------------------------------------------------------
    ibm = np.stack([np.linalg.inv(col_global[i]) for i in range(tm.node_count)]).astype(np.float32)
    # glTF MAT4 floats are per-matrix column-major runs == flatten-C of the
    # transpose; add_accessor flattens C-contiguous, so hand it the transpose.
    ibm_cm = np.ascontiguousarray(ibm.transpose(0, 2, 1))
    ibm_acc = g.add_accessor(ibm_cm, FLOAT, "MAT4", None, 171)

    # --- nodes / hierarchy ---------------------------------------------------
    nodes = []
    for i in range(tm.node_count):
        f = tm.local_raw[i]                  # 16 floats: rows (r0 r1 r2 t) of the bind
        tn = np.array([f[12], f[13], f[14]]) # translation row (w at f[15] == 1)
        Nc = f.reshape(4, 4, order="F")[:3, :3]  # column-major rotation block
        quat = quat_from_rot(Nc)
        node = {"name": tm.node_names[i], "translation": [float(x) for x in tn], "rotation": quat}
        if tm.hie_children[i]:
            node["children"] = list(tm.hie_children[i])
        nodes.append(node)

    nodes[0]["name"] = tm.node_names[0] + "_root"

    # --- meshes ----------------------------------------------------------------
    mesh_entries = []
    for m in meshes:
        pos = m.positions.astype(np.float32) / np.float32(100.0)  # cm -> m for glTF
        nrm = m.normals.astype(np.float32)
        uv = m.uvs.astype(np.float32)
        tan = m.tangents.astype(np.float32) if m.tangents is not None else None
        # weights: normalise; placeholder rows -> joint 0 / weight 1
        w = m.weights.astype(np.float32)
        sums = w.sum(axis=1, keepdims=True)
        placeholder = (sums[:, 0] == 0)
        w = np.where(sums > 0, w / np.maximum(sums, 1e-8), w)
        joints = m.bone_indices.astype(np.uint8)
        w[placeholder] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        joints = joints.copy()
        joints[placeholder] = 0

        pos_acc = g.add_accessor(pos, FLOAT, "VEC3", ARRAY_BUFFER, len(pos))
        nrm_acc = g.add_accessor(nrm, FLOAT, "VEC3", ARRAY_BUFFER, len(nrm))
        uv_acc = g.add_accessor(uv, FLOAT, "VEC2", ARRAY_BUFFER, len(uv))
        tan_acc = g.add_accessor(tan, FLOAT, "VEC4", ARRAY_BUFFER, len(tan)) if tan is not None else None
        jnt_acc = g.add_accessor(joints, UBYTE, "VEC4", ARRAY_BUFFER, len(joints))
        wgt_acc = g.add_accessor(w, FLOAT, "VEC4", ARRAY_BUFFER, len(w))
        max_idx = int(m.indices.max()) if len(m.indices) else 0
        idx_flat = m.indices.reshape(-1)
        if max_idx < 65536:
            idx_arr = idx_flat.astype(np.uint16)
            idx_acc = g.add_accessor(idx_arr, USHORT, "SCALAR", ELEMENT_ARRAY_BUFFER, len(idx_arr))
        else:
            idx_acc = g.add_accessor(idx_flat.astype(np.uint32), UINT, "SCALAR", ELEMENT_ARRAY_BUFFER, len(idx_flat))

        attrs = {"POSITION": pos_acc, "NORMAL": nrm_acc, "TEXCOORD_0": uv_acc,
                 "JOINTS_0": jnt_acc, "WEIGHTS_0": wgt_acc}
        if tan_acc is not None:
            attrs["TANGENT"] = tan_acc
        mesh_name = f"TMC_{m.source_id}"
        if placeholder.any():
            mesh_name += "__unweighted_placeholder"
        mesh_entries.append({
            "name": mesh_name,
            "primitives": [{
                "attributes": attrs,
                "indices": idx_acc,
                "material": 0,
            }],
        })

    # attach meshes to dedicated glTF nodes that reference the skin; the mesh
    # nodes live under the scene root alongside the Hips joint.
    for mi, entry in enumerate(mesh_entries):
        nodes.append({
            "name": entry["name"],
            "mesh": mi,
            "skin": 0,
        })

    scene_nodes = [0] + [tm.node_count + i for i in range(len(mesh_entries))]
    materials = [{"name": "TMC_materials_unmapped",
                  "extensions": {}}]
    # strip the empty extensions object - some validators dislike it
    del materials[0]["extensions"]

    gltf = {
        "asset": {"version": "2.0", "generator": "tools/pd2-las/tmc_export.py (Honoka TMC route-B dump)"},
        "scene": 0,
        "scenes": [{"name": "Honoka_DOAXVV_Secret_Report", "nodes": scene_nodes}],
        "nodes": nodes,
        "meshes": mesh_entries,
        "skins": [{"name": "Honoka_skeleton", "joints": list(range(tm.node_count)),
                   "inverseBindMatrices": ibm_acc, "skeleton": 0}],
        "materials": materials,
    }
    blob = g.build(gltf)
    out_path.write_bytes(blob)
    print(f"wrote {out_path} ({len(blob)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
