#!/usr/bin/env python3
"""COLLADA (.dae) importer for the ME2 Miranda Lawson source.

Parses the rigged/skinned COLLADA shipped in
``PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson
(Romance).zip`` into plain Python data: joint hierarchy with bind transforms,
geometries (positions/normals/UVs/triangles) and per-vertex skin weights.

Conventions:

- COLLADA matrices are column-major text; they are stored here transposed
  (row-vector style, translation in ``rows[3][0..2]``) to match the Diesel
  convention used by ``dmodel.py``. Composition is ``mmul(local, parent_world)``.
- Skin bind operators combine as ``mmul(inv_bind, world)`` applied to row
  vectors (the transpose of ``world @ inv_bind`` in column form).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}


def identity() -> list[list[float]]:
    return [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]


def mmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def minv(m: list[list[float]]) -> list[list[float]]:
    n = [row[:] + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(m)]
    for col in range(4):
        piv = max(range(col, 4), key=lambda r: abs(n[r][col]))
        n[col], n[piv] = n[piv], n[col]
        d = n[col][col] or 1e-12
        n[col] = [x / d for x in n[col]]
        for r in range(4):
            if r != col and n[r][col]:
                f = n[r][col]
                n[r] = [x - f * y for x, y in zip(n[r], n[col])]
    return [row[4:] for row in n]


def _mat_from_text(text: str) -> list[list[float]]:
    """COLLADA <matrix> text -> row-vector-style rows (Diesel convention).

    This file's matrices are written row-major of the column-vector matrix M
    (translation in M[0..2][3], i.e. flat indices 3, 7, 11 — verified against
    the rig: 'root' resolves to z≈101 cm like the PD2 donor). We store
    S = M^T (row-vector style, translation in ``rows[3][0..2]``), matching
    ``dmodel.world_rows``.
    """
    a = [float(x) for x in text.split()]
    if len(a) != 16:
        raise ValueError(f"matrix must have 16 values, got {len(a)}")
    return [[a[4 * c + r] for c in range(4)] for r in range(4)]


@dataclass
class Joint:
    name: str
    parent: Optional[str]
    local: list[list[float]]
    world: list[list[float]] = field(default_factory=identity)


@dataclass
class SkinBind:
    joint: str
    weight: float


@dataclass
class Mesh:
    name: str
    material: str                       # source material name (e.g. 'Body 1')
    positions: list[tuple[float, float, float]]
    normals: list[tuple[float, float, float]]
    uvs: list[tuple[float, float]]
    triangles: list[tuple[int, int, int]]
    # per vertex, up to `max_weights` SkinBind, normalized to sum 1
    weights: list[list[SkinBind]]
    bind_shape: list[list[float]] = field(default_factory=identity)
    inv_binds: dict[str, list[list[float]]] = field(default_factory=dict)


@dataclass
class DaeScene:
    unit_scale: float                   # meters per asset unit (1.0 = meters)
    up_axis: str                        # 'Z_UP' / 'Y_UP' / ...
    joints: dict[str, Joint]
    joint_order: list[str]
    meshes: list[Mesh]
    images: dict[str, str]              # image id -> init_from filename
    material_images: dict[str, dict]    # material name -> slot -> image id


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_source(root: ET.Element, sid: str) -> ET.Element:
    for src in root.iter():
        if _local(src.tag) == "source" and src.get("id") == sid:
            return src
    raise KeyError(f"source #{sid} not found")


def _float_array(root: ET.Element, sid: str) -> list[float]:
    src = _find_source(root, sid)
    arr = next((c for c in src if _local(c.tag) == "float_array"), None)
    if arr is None:
        raise ValueError(f"source #{sid} has no float_array")
    return [float(x) for x in arr.text.split()]


def _name_array(root: ET.Element, sid: str) -> list[str]:
    src = _find_source(root, sid)
    arr = next((c for c in src if _local(c.tag) in ("Name_array", "IDREF_array")), None)
    if arr is None:
        raise ValueError(f"source #{sid} has no Name_array")
    return arr.text.split()


def _accessor(root: ET.Element, sid: str) -> tuple[int, list[str]]:
    src = _find_source(root, sid)
    acc = next((e for e in src.iter() if _local(e.tag) == "accessor"), None)
    if acc is None:
        raise ValueError(f"source #{sid} has no accessor")
    params = [p.get("name", "") for p in acc if _local(p.tag) == "param"]
    return int(acc.get("count")), params


def _read_joints(root: ET.Element) -> tuple[dict[str, Joint], list[str]]:
    """Return (joints by name, order). Only type="JOINT" nodes are joints; the
    surrounding NODE wrappers (scene root, mesh instance nodes) are kept
    internally so world transforms compose through them."""
    all_nodes: dict[str, Joint] = {}
    order: list[str] = []

    def walk(node: ET.Element, parent: Optional[str]) -> None:
        for ch in node:
            if _local(ch.tag) != "node":
                continue
            name = ch.get("name") or ch.get("id")
            mat_el = next((c for c in ch if _local(c.tag) == "matrix"), None)
            local = _mat_from_text(mat_el.text) if mat_el is not None else identity()
            all_nodes[name] = Joint(name=name, parent=parent, local=local)
            order.append(name)
            walk(ch, name)

    scene = next(e for e in root.iter() if _local(e.tag) == "visual_scene")
    walk(scene, None)

    def compute(name: str) -> list[list[float]]:
        j = all_nodes[name]
        if j.parent is None:
            j.world = j.local
        else:
            j.world = mmul(j.local, compute(j.parent))
        return j.world

    for n in order:
        compute(n)

    joints = {}
    for el in scene.iter():
        if _local(el.tag) == "node" and el.get("type") == "JOINT":
            name = el.get("name") or el.get("id")
            joints[name] = all_nodes[name]
    order = [n for n in order if n in joints]
    return joints, order


def _read_skin(root: ET.Element, controller_id: str,
               max_weights: int = 3) -> tuple[str, dict[str, list[list[float]]], str]:
    """Return (geometry_id, {joint: inv_bind_rows}, bind_shape note)."""
    ctrl = next(e for e in root.iter()
                if _local(e.tag) == "controller" and e.get("id") == controller_id)
    skin = next(c for c in ctrl if _local(c.tag) == "skin")
    geom_id = skin.get("source", "").lstrip("#")
    bsm = next((c for c in skin if _local(c.tag) == "bind_shape_matrix"), None)
    bind_shape = _mat_from_text(bsm.text) if bsm is not None else identity()
    joints_el = next(c for c in skin if _local(c.tag) == "joints")
    joint_src = next(i.get("source", "").lstrip("#") for i in joints_el
                     if i.get("semantic") == "JOINT")
    ibm_src = next(i.get("source", "").lstrip("#") for i in joints_el
                   if i.get("semantic") == "INV_BIND_MATRIX")
    names = _name_array(root, joint_src)
    flat = _float_array(root, ibm_src)
    inv_binds = {names[i]: _mat_from_text(" ".join(str(x) for x in flat[i * 16:(i + 1) * 16]))
                 for i in range(len(names))}
    return geom_id, inv_binds, bind_shape


def _read_weights(root: ET.Element, controller_id: str, vert_count: int,
                  max_weights: int = 3) -> list[list[SkinBind]]:
    ctrl = next(e for e in root.iter()
                if _local(e.tag) == "controller" and e.get("id") == controller_id)
    skin = next(c for c in ctrl if _local(c.tag) == "skin")
    vw = next(c for c in skin if _local(c.tag) == "vertex_weights")
    inputs = {i.get("semantic"): i for i in vw if _local(i.tag) == "input"}
    joint_names = _name_array(root, inputs["JOINT"].get("source", "").lstrip("#"))
    weight_vals = _float_array(root, inputs["WEIGHT"].get("source", "").lstrip("#"))
    j_off = int(inputs["JOINT"].get("offset", 0))
    w_off = int(inputs["WEIGHT"].get("offset", 0))
    stride = 1 + max(j_off, w_off)
    vcount = [int(x) for x in next(c for c in vw if _local(c.tag) == "vcount").text.split()]
    vflat = [int(x) for x in next(c for c in vw if _local(c.tag) == "v").text.split()]
    if len(vcount) != vert_count:
        raise ValueError(f"vcount {len(vcount)} != positions {vert_count}")
    out: list[list[SkinBind]] = []
    p = 0
    for n in vcount:
        binds: dict[str, float] = {}
        for k in range(n):
            j = joint_names[vflat[p + j_off]]
            w = weight_vals[vflat[p + w_off]]
            binds[j] = binds.get(j, 0.0) + w
            p += stride
        top = sorted(binds.items(), key=lambda kv: -kv[1])[:max_weights]
        total = sum(w for _, w in top) or 1.0
        out.append([SkinBind(j, w / total) for j, w in top])
    return out


def _read_geometry(root: ET.Element, geom_id: str) -> dict:
    geom = next(e for e in root.iter()
                if _local(e.tag) == "geometry" and e.get("id") == geom_id)
    mesh = next(c for c in geom if _local(c.tag) == "mesh")
    verts_el = next(c for c in mesh if _local(c.tag) == "vertices")
    pos_src = next(i.get("source", "").lstrip("#") for i in verts_el
                   if i.get("semantic") == "POSITION")
    count, _ = _accessor(root, pos_src)
    pos_flat = _float_array(root, pos_src)
    positions = [(pos_flat[i * 3], pos_flat[i * 3 + 1], pos_flat[i * 3 + 2])
                 for i in range(count)]

    tris_el = next(c for c in mesh if _local(c.tag) == "triangles")
    material = tris_el.get("material", "")
    inputs = [i for i in tris_el if _local(i.tag) == "input"]
    stride = 1 + max(int(i.get("offset", 0)) for i in inputs)
    idx = [int(x) for x in next(c for c in tris_el if _local(c.tag) == "p").text.split()]
    n_tri = int(tris_el.get("count"))

    def expand(semantic: str):
        inp = next((i for i in inputs if i.get("semantic") == semantic), None)
        if inp is None:
            return None, 0
        off = int(inp.get("offset", 0))
        src = inp.get("source", "").lstrip("#")
        if semantic == "VERTEX":
            return positions, off
        if semantic == "NORMAL":
            c2, _ = _accessor(root, src)
            flat = _float_array(root, src)
            return [(flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]) for i in range(c2)], off
        c2, params = _accessor(root, src)
        flat = _float_array(root, src)
        n = len(params) or 2
        return [(flat[i * n], flat[i * n + 1]) for i in range(c2)], off

    pos_l, pos_off = expand("VERTEX")
    nrm_l, nrm_off = expand("NORMAL")
    uv_l, uv_off = expand("TEXCOORD")
    return {
        "material": material,
        "positions": positions,
        "triangles_raw": (idx, stride, n_tri, pos_off, nrm_off, uv_off),
        "normals_src": nrm_l,
        "uvs_src": uv_l,
    }


def load_dae(data: bytes | str, *, max_weights: int = 3) -> DaeScene:
    if isinstance(data, bytes):
        data = data.decode("utf-8", "replace")
    root = ET.fromstring(data)

    asset = next((e for e in root if _local(e.tag) == "asset"), None)
    unit = next((c for c in asset if _local(c.tag) == "unit"), None) if asset is not None else None
    unit_scale = float(unit.get("meter", 1.0)) if unit is not None else 1.0
    up_el = next((c for c in asset if _local(c.tag) == "up_axis"), None) if asset is not None else None
    up_axis = (up_el.text or "Y_UP").strip() if up_el is not None else "Y_UP"

    joints, order = _read_joints(root)

    images: dict[str, str] = {}
    for img in root.iter():
        if _local(img.tag) == "image":
            init = next((c for c in img if _local(c.tag) == "init_from"), None)
            if init is not None and init.text:
                images[img.get("id")] = init.text.strip()

    material_images: dict[str, dict] = {}
    for mat in root.iter():
        if _local(mat.tag) != "material":
            continue
        name = mat.get("name") or mat.get("id", "")
        slots = {}
        for el in mat.iter():
            if _local(el.tag) == "texture":
                slots.setdefault("diffuse", el.get("texture"))
        material_images[name] = slots

    # link mesh node instances: node name -> (geometry id, controller id, material)
    # This DAE uses <instance_controller url="#...-skin"> on each mesh node; the
    # skin's source names the geometry. Some DAEs use <instance_geometry> instead.
    controller_geom: dict[str, str] = {}
    for ctrl in root.iter():
        if _local(ctrl.tag) != "controller":
            continue
        skin = next((c for c in ctrl if _local(c.tag) == "skin"), None)
        if skin is not None:
            controller_geom[ctrl.get("id")] = skin.get("source", "").lstrip("#")

    instance: dict[str, tuple[str, str, str]] = {}
    for node in root.iter():
        if _local(node.tag) != "node":
            continue
        nname = node.get("name") or node.get("id")
        holder = next((c for c in node if _local(c.tag) in
                       ("instance_geometry", "instance_controller")), None)
        if holder is None:
            continue
        if _local(holder.tag) == "instance_controller":
            ctrl_id = holder.get("url", "").lstrip("#")
            geom_id = controller_geom[ctrl_id]
        else:
            geom_id = holder.get("url", "").lstrip("#")
            ctrl_id = ""
        mat = ""
        for im in holder.iter():
            if _local(im.tag) == "instance_material":
                mat = (im.get("target") or im.get("symbol") or "").lstrip("#")
                break
        instance[nname] = (geom_id, ctrl_id, mat)

    meshes: list[Mesh] = []
    for nname, (geom_id, ctrl_id, mat_symbol) in instance.items():
        g = _read_geometry(root, geom_id)
        bind_shape = identity()
        if ctrl_id:
            cgeom, inv_binds, bind_shape = _read_skin(root, ctrl_id, max_weights)
            if cgeom != geom_id:
                raise ValueError(f"controller {ctrl_id} skins {cgeom}, node has {geom_id}")
            weights = _read_weights(root, ctrl_id, len(g["positions"]), max_weights)
        else:
            inv_binds = {}
            weights = [[] for _ in g["positions"]]

        idx, stride, n_tri, pos_off, nrm_off, uv_off = g["triangles_raw"]
        # apply bind_shape to rest positions/normals (model-space rest)
        bs = bind_shape

        def xform(p):
            return (p[0] * bs[0][0] + p[1] * bs[1][0] + p[2] * bs[2][0] + bs[3][0],
                    p[0] * bs[0][1] + p[1] * bs[1][1] + p[2] * bs[2][1] + bs[3][1],
                    p[0] * bs[0][2] + p[1] * bs[1][2] + p[2] * bs[2][2] + bs[3][2])

        src_positions = [xform(p) for p in g["positions"]]
        src_normals = [xform(p) if g["normals_src"] else None for p in (g["normals_src"] or [])]
        # expand to unique (pos,nrm,uv) corners, then weld identical corners
        corners: dict[tuple, int] = {}
        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        tri_list: list[tuple[int, int, int]] = []
        w_out: list[list[SkinBind]] = []
        for t in range(n_tri):
            tri = []
            for k in range(3):
                base = (t * 3 + k) * stride
                pi = idx[base + pos_off]
                ni = idx[base + nrm_off] if g["normals_src"] is not None else -1
                ui = idx[base + uv_off] if g["uvs_src"] is not None else -1
                key = (pi, ni, ui)
                if key not in corners:
                    corners[key] = len(positions)
                    positions.append(src_positions[pi])
                    normals.append(src_normals[ni] if src_normals and ni >= 0 else (0.0, 0.0, 1.0))
                    uvs.append(g["uvs_src"][ui] if g["uvs_src"] and ui >= 0 else (0.0, 0.0))
                    w_out.append(weights[pi])
                tri.append(corners[key])
            tri_list.append((tri[0], tri[1], tri[2]))

        if nname == "Eyelashes":
            # In ME2, Eyelashes is rendered TwoSided and the upper eyelash
            # ribbon has DAE face/vertex normals with +Y (which becomes -Y,
            # backward-facing and backface-culled in Direct3D9, after the
            # 180 deg Z rotation to PAYDAY 2's +Y forward frame). Orient all
            # 224 eyelash triangles and their vertex normals forward (-Y in
            # DAE -> +Y in PD2) so upper eyelashes are never backface-culled.
            fixed_tris: list[tuple[int, int, int]] = []
            v_acc = [[0.0, 0.0, 0.0] for _ in positions]
            for a, b, c in tri_list:
                pa, pb, pc = positions[a], positions[b], positions[c]
                e1 = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
                e2 = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
                fny = e1[2] * e2[0] - e1[0] * e2[2]
                if fny > 0.0:
                    b, c = c, b
                    e1, e2 = e2, e1
                fn = (
                    e1[1] * e2[2] - e1[2] * e2[1],
                    e1[2] * e2[0] - e1[0] * e2[2],
                    e1[0] * e2[1] - e1[1] * e2[0],
                )
                fixed_tris.append((a, b, c))
                for v in (a, b, c):
                    v_acc[v][0] += fn[0]
                    v_acc[v][1] += fn[1]
                    v_acc[v][2] += fn[2]
            tri_list = fixed_tris
            for i, (nx, ny, nz) in enumerate(normals):
                ax, ay, az = v_acc[i]
                if nx * ax + ny * ay + nz * az < 0.0:
                    normals[i] = (-nx, -ny, -nz)

        meshes.append(Mesh(
            name=nname,
            material=g["material"] or mat_symbol or nname,
            positions=positions,
            normals=normals,
            uvs=uvs,
            triangles=tri_list,
            weights=w_out,
            bind_shape=bind_shape,
            inv_binds=inv_binds,
        ))

    return DaeScene(
        unit_scale=unit_scale,
        up_axis=up_axis,
        joints=joints,
        joint_order=order,
        meshes=meshes,
        images=images,
        material_images=material_images,
    )
