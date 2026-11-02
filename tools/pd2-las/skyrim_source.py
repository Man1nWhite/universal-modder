"""Adapter: a Skyrim SE outfit from `.nif` files -> `ModelData` for the LAS authoring path.

`build_models.py` re-authors a Source-engine character onto the PAYDAY 2 player
skeleton. This module produces the same `ModelData` contract from Skyrim SE
meshes instead: bones resolved to **PD2 names already**, vertices in world space,
per-vertex weights folded off the XPMSE helper bones, and one submesh per
material.

Three things make the conversion safe:

1. Every NIF in the outfit is exported from the same BodySlide project, so the
   node transforms are identical across files (verified: max matrix delta 0.0).
   One file's bone hierarchy is therefore the master skeleton for all of them.
2. The garments and the body share that skeleton, so a garment vertex keeps
   riding the same bone transforms as the skin under it.
3. Helper bones (twists, breasts, belly, butt) are folded into their nearest PD2
   bone by weight *before* anything else looks at the mesh — a skirt weighted to
   `NPC L RearThigh` must not lose 30 % of its skin weight when that bone has no
   PD2 equivalent.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

import decimate  # noqa: E402
from source_model import Bone, ModelData, SkinVertex, SubMesh  # noqa: E402


def _load_reader():
    """Import tools/skyrim-nif/nif.py by path.

    The reader's directory also holds `preview.py`, which would shadow
    pd2-las/preview.py if it went on sys.path — so it never does.
    """
    path = REPO / "tools" / "skyrim-nif" / "nif.py"
    spec = importlib.util.spec_from_file_location("skyrim_nif_reader", path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks the class's module up in sys.modules while decorating
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


nif = _load_reader()

CM_PER_UNIT = 1.428  # one Gamebryo unit in centimetres (Skyrim convention)
MAX_INFLUENCES = 3   # Diesel SKINNED_3WEIGHTS


@dataclass(frozen=True)
class MeshSpec:
    """One NIF and the shapes taken from it, under one logical material."""

    path: Path
    shapes: tuple[str, ...]
    material: str
    #: cluster-decimate the shape down to this vertex count (see `decimate.py`).
    #: Jewellery authored for close-up renders needs it; garments do not.
    decimate_to: int | None = None


def default_outfit(root: Path, jacket: str = "both") -> list[MeshSpec]:
    """The Business Woman outfit: 3BA body + feet + jacket layers + skirt + heels.

    `Jacket_0.nif` holds **two garments worn together**, not two alternatives:
    `0_Jacket` is the blazer (hips to collar, 101.8-163 cm, sleeves included)
    and `0_Jacket2` is the buttoned bustier underneath it (waist to collar,
    116.6-165.1 cm). The plugin's "Business Woman Jacket Xtra" armour record
    points at the same NIF, so both shapes always render; `jacket="blazer"` or
    `"bustier"` drops one for experiments.
    """
    layers = {
        "both": ("0_Jacket", "0_Jacket2"),
        "blazer": ("0_Jacket",),
        "bustier": ("0_Jacket2",),
        "none": (),
    }[jacket]
    specs = [
        MeshSpec(root / "Jacket_0.nif", ("3BA", "3BA_Vagina", "3BA_Anus"), "skin"),
        MeshSpec(root / "Heels_0.nif", ("feet",), "skin"),
    ]
    if "0_Jacket" in layers:
        specs.append(MeshSpec(root / "Jacket_0.nif", ("0_Jacket",), "jacket"))
    if "0_Jacket2" in layers:
        specs.append(MeshSpec(root / "Jacket_0.nif", ("0_Jacket2",), "jacket2"))
    specs += [
        MeshSpec(root / "Skirt_0.nif", ("0_Skirt",), "skirt"),
        MeshSpec(root / "Heels_0.nif", ("0_Heels001",), "heels"),
        # 26,961 vertices for a 4 mm-bead chain: a twelfth of that is visually
        # identical at heister distance and 0.3 mm off the source surface
        MeshSpec(root / "Necklace_0.nif", ("0_Necklace",), "necklace",
                 decimate_to=3000),
    ]
    return specs


# ---------------------------------------------------------------------------
# skeleton
# ---------------------------------------------------------------------------
def _world_mat(nodes: dict[int, nif.Node], node: nif.Node) -> np.ndarray:
    return node.world_matrix(nodes)


def quat_from_matrix(m: np.ndarray) -> tuple[float, float, float, float]:
    """3x3 rotation (column-vector convention) -> (x, y, z, w) quaternion."""
    r = np.asarray(m, dtype=np.float64)
    tr = r[0, 0] + r[1, 1] + r[2, 2]
    if tr > 0.0:
        s = np.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (r[2, 1] - r[1, 2]) / s
        y = (r[0, 2] - r[2, 0]) / s
        z = (r[1, 0] - r[0, 1]) / s
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
        w = (r[2, 1] - r[1, 2]) / s
        x = 0.25 * s
        y = (r[0, 1] + r[1, 0]) / s
        z = (r[0, 2] + r[2, 0]) / s
    elif r[1, 1] > r[2, 2]:
        s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
        w = (r[0, 2] - r[2, 0]) / s
        x = (r[0, 1] + r[1, 0]) / s
        y = 0.25 * s
        z = (r[1, 2] + r[2, 1]) / s
    else:
        s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
        w = (r[1, 0] - r[0, 1]) / s
        x = (r[0, 2] + r[2, 0]) / s
        y = (r[1, 2] + r[2, 1]) / s
        z = 0.25 * s
    q = np.array([x, y, z, w], dtype=np.float64)
    return tuple(float(v) for v in q / np.linalg.norm(q))


class BoneResolver:
    """NIF node name -> PD2 deform bone, with helper-bone folding.

    Resolution order per node: the explicit `map`, then `fold`, then the nearest
    ancestor that resolves. Names listed in `drop.bones` are skipped (their
    weight goes to the fallback, usually `Hips`).
    """

    def __init__(self, nif_file: nif.NifFile, bone_map: dict):
        self.nodes = nif_file.nodes
        self.map = bone_map["map"]
        self.fold = {k: v for k, v in bone_map.get("fold", {}).items() if k != "comment"}
        drop = bone_map.get("drop", {})
        self.drop = set(drop.get("bones", [])) | set(drop.get("patterns", []))
        self.fallback = drop.get("fallback_target", "Hips")
        self._by_name = {n.name: n for n in self.nodes.values()}
        self._cache: dict[str, str | None] = {}

    def parent_name(self, name: str) -> str | None:
        node = self._by_name.get(name)
        if node is None or node.parent is None:
            return None
        return self.nodes[node.parent].name

    def resolve(self, name: str) -> str | None:
        if name in self._cache:
            return self._cache[name]
        out: str | None = None
        cur: str | None = name
        seen: set[str] = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            if cur in self.map and cur not in self.drop:
                out = self.map[cur]
                break
            if cur in self.fold:
                out = self.fold[cur]
                break
            cur = self.parent_name(cur)
        self._cache[name] = out
        return out

    # -- bones ----------------------------------------------------------
    def primary_source(self) -> dict[str, str]:
        """Target bone -> the NIF node whose joint position defines it.

        Twists and breast bones fold into a target but never define its joint;
        only explicit `map` pairs do.
        """
        out: dict[str, str] = {}
        for src, dst in self.map.items():
            if src in self.drop or src not in self._by_name:
                continue
            out.setdefault(dst, src)
        return out


def build_bones(nif_file: nif.NifFile, resolver: BoneResolver) -> tuple[list[Bone], dict[str, int]]:
    """One flat `Bone` per target name, storing its world transform.

    Parents are -1 on purpose: `source_bone_worlds()` composes local matrices,
    and the world transform is already measured. Flat bones cannot mis-order a
    hierarchy, and the retarget step only reads world positions.
    """
    bones: list[Bone] = []
    index: dict[str, int] = {}
    for target, src in sorted(resolver.primary_source().items()):
        node = resolver._by_name[src]
        m = _world_mat(nif_file.nodes, node)
        # translation in [12:15]; rotation is the 3x3 transposed into
        # column-vector convention for the quaternion helper
        pos = (float(m[0, 3]), float(m[1, 3]), float(m[2, 3]))
        quat = quat_from_matrix(m[:3, :3].T)
        index[target] = len(bones)
        bones.append(Bone(name=target, parent=-1, pos=pos, quat=quat))
    return bones, index


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def _vertex_weights(shape: nif.Shape, resolver: BoneResolver) -> list[list[tuple[str, float]]]:
    """Per vertex: [(target_bone, weight)] folded onto PD2 bones, top 3 kept."""
    if shape.weights is None or shape.bone_indices is None:
        return []
    w = shape.weights.astype(np.float64)
    idx = shape.bone_indices
    resolved = [resolver.resolve(b) for b in shape.bones]
    out: list[list[tuple[str, float]]] = []
    for v in range(shape.num_vertices):
        acc: dict[str, float] = {}
        for slot in range(4):
            weight = float(w[v, slot])
            if weight <= 1e-6:
                continue
            bone_id = int(idx[v, slot])
            target = resolved[bone_id] if bone_id < len(resolved) else None
            target = target or resolver.fallback
            acc[target] = acc.get(target, 0.0) + weight
        if not acc:
            acc = {resolver.fallback: 1.0}
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:MAX_INFLUENCES]
        total = sum(value for _name, value in top)
        out.append([(name, value / total) for name, value in top if value > 1e-6])
    return out


#: How tall the shoe is allowed to stay below the ankle when the outfit is
#: re-fitted for a flat-footed skeleton. See `fit_feet_to_ground`.
HEEL_BLEND_CM = 2.5


def ankle_height(f: "nif.NifFile") -> float | None:
    """World Z of the foot joint, in file units (the space `load_outfit` uses)."""
    for node in f.nodes.values():
        if " Foot " in node.name or node.name.endswith(" Foot"):
            return float(node.world_matrix(f.nodes)[2, 3])
    return None


def fit_feet_to_ground(vertices: np.ndarray, ankle_z: float,
                       blend_cm: float = HEEL_BLEND_CM) -> tuple[np.ndarray, dict]:
    """Squash the stiletto so the sole lands on z = 0.

    The source is a Skyrim **high-heel** outfit: the shoe is modelled standing
    on a floor at z = -12 cm, ~20.7 cm below the foot joint, because Skyrim's
    heel rigs raise the whole character by the heel height. Diesel has no such
    offset — the unit's origin is the floor and the foot joint sits at 9.9 cm —
    so shipped verbatim the character stands with her ankles in the ground.

    There is no way to keep a 12 cm stiletto *and* a 9.9 cm ankle: the shoe has
    to lose the height somewhere. This compresses the geometry below the ankle
    joint by `k = ankle / (ankle - min_z)` with a short blend so no crease
    appears; the result is a low-heeled pump that stands and animates
    correctly. Returning the shoe unchanged is the alternative (`heels="keep"`)
    and it sinks the character ~12 cm into the floor.
    """
    out = vertices.copy()
    lowest = float(out[:, 2].min())
    if lowest >= 0.0:
        return out, {"applied": False, "min_z": lowest}
    span = ankle_z - lowest
    k = ankle_z / span
    below = out[:, 2] < ankle_z
    if not below.any():
        return out, {"applied": False, "min_z": lowest}
    depth = ankle_z - out[below, 2]
    # ease the squashing in over the first `blend_cm` so the ankle itself is not
    # pinched, then move every deeper vertex by the same proportion
    ramp = np.clip(depth / max(blend_cm, 1e-6), 0.0, 1.0)
    ease = 1.0 - (1.0 - ramp) ** 2                 # smooth start at the joint
    out[below, 2] = ankle_z - depth * (1.0 - ease * (1.0 - k))
    out[below, 2] = np.maximum(out[below, 2], 0.0)
    return out, {
        "applied": True,
        "ankle_z": round(ankle_z, 3),
        "min_z_before": round(lowest, 3),
        "min_z_after": round(float(out[:, 2].min()), 3),
        "compression": round(k, 4),
        "vertices": int(below.sum()),
    }


def load_outfit(specs: list[MeshSpec], bone_map: dict,
                master: Path | None = None,
                heels: str = "flatten") -> tuple[ModelData, dict]:
    """Read every NIF and return one `ModelData` + a conversion report.

    `heels="flatten"` re-fits the outfit for Diesel's flat-footed skeleton (see
    `fit_feet_to_ground`); `"keep"` leaves the source's heel pose alone.
    """
    files: dict[Path, nif.NifFile] = {}
    for spec in specs:
        if spec.path not in files:
            files[spec.path] = nif.parse(spec.path.read_bytes(), str(spec.path))

    master_path = master or specs[0].path
    master_file = files[master_path]
    resolver = BoneResolver(master_file, bone_map)
    bones, bone_index = build_bones(master_file, resolver)

    vertices: list[SkinVertex] = []
    meshes: list[SubMesh] = []
    report: dict = {"files": {}, "materials": {}, "unresolved_bones": {}}
    unresolved: set[str] = set()

    for spec in specs:
        f = files[spec.path]
        by_name = {s.name: s for s in f.shapes}
        entry = report["files"].setdefault(spec.path.name, {"shapes": [], "vertices": 0})
        for shape_name in spec.shapes:
            shape = by_name.get(shape_name)
            if shape is None:
                raise KeyError(f"{spec.path.name}: no shape {shape_name!r} "
                               f"(has {sorted(by_name)})")
            for bone in shape.bones:
                if resolver.resolve(bone) is None:
                    unresolved.add(bone)
            world = f.shape_world_matrix(shape)
            rot = world[:3, :3]
            base = len(vertices)
            verts = shape.vertices.astype(np.float64) @ rot.T + world[:3, 3]
            if nif.has_normals(shape):
                normals = shape.normals
            else:
                # BodySlide writes the 3BA body and `feet` with the normal
                # attribute off; rebuild them from the topology like a renderer
                normals = nif.smooth_normals(shape.vertices, shape.triangles)
                report.setdefault("generated_normals", []).append(shape_name)
            norms = normals.astype(np.float64) @ np.linalg.inv(rot).T
            norms /= np.maximum(np.linalg.norm(norms, axis=1, keepdims=True), 1e-9)
            weights = _vertex_weights(shape, resolver)
            uvs = np.asarray(shape.uvs, dtype=np.float64)

            if spec.decimate_to:
                # carry the blend weights over by copying them from the nearest
                # original vertex — averaging them would invent weights for
                # bones the bead never touched
                before = verts.shape[0]
                dec = decimate.decimate(verts, shape.triangles, uvs=uvs,
                                        normals=norms, max_vertices=spec.decimate_to)
                weights = [weights[i] for i in dec.source_index]
                verts, norms, uvs = dec.vertices, dec.normals, dec.uvs
                shape_tris = dec.triangles
                report.setdefault("decimated", []).append({
                    "shape": shape_name,
                    "vertices_before": int(before),
                    "vertices_after": int(verts.shape[0]),
                    "triangles_after": int(shape_tris.shape[0]),
                    "cell_cm": round(dec.cell * CM_PER_UNIT, 3),
                    **{f"error_{k}_cm": round(v * CM_PER_UNIT, 3)
                       for k, v in decimate.surface_error(
                           np.asarray(shape.vertices, dtype=np.float64) * CM_PER_UNIT,
                           shape.triangles, dec.vertices * CM_PER_UNIT).items()},
                })
            else:
                shape_tris = shape.triangles

            for v in range(verts.shape[0]):
                vertices.append(SkinVertex(
                    pos=tuple(float(x) for x in verts[v]),
                    normal=tuple(float(x) for x in norms[v]),
                    uv=(float(uvs[v, 0]), float(uvs[v, 1])),
                    weights=tuple((bone_index[name], w) for name, w in weights[v])
                    if weights else (),
                ))
            # NIF front faces are clockwise (the D3D convention); the shared
            # authoring path takes COLLADA-style counter-clockwise and swaps it
            # for Diesel on the way out. Reverse here so the two cancel and the
            # stored normals keep pointing the way the winding says they do.
            tris = (shape_tris[:, ::-1] + base).reshape(-1)
            meshes.append(SubMesh(material=spec.material,
                                  triangle_indices=tuple(int(i) for i in tris)))
            entry["shapes"].append(shape_name)
            entry["vertices"] += int(verts.shape[0])
            report["materials"][spec.material] = \
                report["materials"].get(spec.material, 0) + int(verts.shape[0])

    if heels == "flatten":
        ankle = ankle_height(master_file)
        if ankle is None:
            raise KeyError(f"{master_path.name}: no foot joint to fit the heels to")
        flat, feet_report = fit_feet_to_ground(
            np.array([v.pos for v in vertices], dtype=np.float64), ankle)
        vertices = [replace(v, pos=(float(p[0]), float(p[1]), float(p[2])))
                    for v, p in zip(vertices, flat)]
        report["feet"] = feet_report
    elif heels != "keep":
        raise ValueError(f"heels must be 'flatten' or 'keep', not {heels!r}")

    report["bones"] = [b.name for b in bones]
    report["unresolved_bones"] = sorted(unresolved)
    report["vertices"] = len(vertices)
    report["triangles"] = sum(len(m.triangle_indices) // 3 for m in meshes)
    model = ModelData(name="business_woman", bones=bones, materials=sorted(report["materials"]),
                      vertices=vertices, meshes=meshes)
    return model, report


def identity_skel_map(model: ModelData) -> dict:
    """A `skeleton_map` shaped no-op for `build_models.retarget_maps`.

    The bones are already PD2 names, so every pair is `name -> name`: the
    similarity fit then measures each PD2 joint against its own source joint,
    which is exactly what the anatomy-aware retarget expects.
    """
    return {"map": {b.name: b.name for b in model.bones}, "fold": {},
            "drop": {"patterns": [], "bones": [], "fallback_target": "Hips"}}
