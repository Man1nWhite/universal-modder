#!/usr/bin/env python3
"""Build the native OfficeSuite + Miranda Romance replacement for Hila (no LAS).

Replaces Hila's body drawable with the OfficeSuite outfit body and her head
drawable with the Miranda Romance head. The outfit's hands are cut where the palms
begin, so Hila's own stock gloves - drawable, `.object` node and all - stay exactly
as the game ships them and are what shows at the sleeve ends. The donor's forearm
seals the suit cuff, so no cuff tuck is needed. The shadow caster is the outfit
caster plus the solid head, one dominant bone per vertex.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np

from build_joy_head_mods import (HILA_UNIT_DIR, HILA_UNIT_STEM, ROOT,
                                 write_deterministic_zip)
import build_models as bm
import determinism
import diesel_model as dm
from dist_paths import dist_path
from hila_texture_atlas import TILES, atlas_uvs, make_atlas

PACK = "OfficeSuite_Miranda_Romance_over_Hila.zip"
INSTALL = "OfficeSuite and Miranda Romance over Hila"
HEAD_ROOT = "Miranda Romance over Hila/"
OUTFIT_DIR = "units/officesuite/skins/officesuite"
UNIT = f"{HILA_UNIT_DIR}/{HILA_UNIT_STEM}"
MATERIAL = f"{HILA_UNIT_DIR}/mtr_criminal_ecp_female"
SUIT_SHADER = "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
ATLAS_ASSETS = {"diffuse_texture": f"{UNIT}_suite_df", "bump_normal_texture": f"{UNIT}_suite_nm"}

#: Hila's stock glove drawable. The pack ships it exactly as the game has it: with
#: the outfit's palms cut away (D59) it is the hand the wearer sees.
GLOVE = "g_hands"

INSTALL_NOTE = f"""OfficeSuite + Miranda Romance over Hila

Extract the '{INSTALL}' folder into PAYDAY 2/assets/mod_overrides/.
Remove other Hila body/head overrides first, including the standalone Miranda over Hila mods.
Select Hila and her default outfit. Neither donor ZIP, LAS, SuperBLT nor BeardLib is required.

This replaces Hila's default third-person body and head in heists and the menu/lobby.
Her stock gloves - hand, glove and its skin - are untouched and show at the sleeve ends,
where the outfit's own palms used to be.
Hila's first-person arms, equipment, mask and armor behavior are not replaced.
Alternate outfits/armor mods can hide or clip through the replacement. The build has been
checked offline, not in the running game. Remove this folder to uninstall.
"""


def _section(model: dm.ModelFile, sid: int, tag: int) -> dm.Section:
    section = model.by_id(sid)
    if section.type != tag:
        raise ValueError(f"section {sid}: expected {dm.TAG_NAMES[tag]}, got {section.type:#x}")
    return section


@dataclass
class Drawable:
    section: dm.Section
    geometry: dm.Section
    topology: dm.Section
    skin: dm.Section
    data: dict
    geo: dict
    top: dict
    bind: dict

    @classmethod
    def read(cls, model: dm.ModelFile, name: str) -> Drawable:
        sid = dm.hash64(name)
        matches = [(s, d) for s in model.by_type(dm.MODEL_DATA)
                   if (d := dm.decode_model_data(s.payload))["name_hash"] == sid and d["version"] == 3]
        if len(matches) != 1:
            raise ValueError(f"expected one drawable named {name}, found {len(matches)}")
        section, d = matches[0]
        gp = dm.decode_passthroughgp(_section(model, d["passthroughgp"], dm.PASSTHROUGH_GP).payload)
        ip = dm.decode_topologyip(_section(model, d["topologyip"], dm.TOPOLOGY_IP).payload)
        if gp["topology"] != ip["topology"]:
            raise ValueError(f"{name}: GP and IP reference different topology")
        g = _section(model, gp["geometry"], dm.GEOMETRY)
        t = _section(model, gp["topology"], dm.TOPOLOGY)
        s = _section(model, d["skinbones"], dm.SKINBONES)
        return cls(section, g, t, s, d, dm.decode_geometry(g.payload), dm.decode_topology(t.payload),
                   dm.decode_skinbones(s.payload))

    @property
    def faces(self) -> np.ndarray:
        return np.asarray(self.top["indices"], dtype=np.int32).reshape(-1, 3)

    def material_hashes(self, model: dm.ModelFile) -> list[int]:
        group = _section(model, self.data["matgroup"], dm.MATERIAL_GROUP)
        return [dm.decode_material(_section(model, i, dm.MATERIAL).payload)["name_hash"]
                for i in dm.decode_material_group(group.payload)["material_ids"]]


def _exclusive(model: dm.ModelFile, draw: Drawable) -> None:
    """Check the native block can be edited in place without changing another model node."""
    for sec in model.by_type(dm.MODEL_DATA):
        data = dm.decode_model_data(sec.payload)
        if sec.id != draw.section.id and data["version"] == 3 and any(
                data[key] == draw.data[key] for key in ("passthroughgp", "topologyip", "skinbones")):
            raise ValueError("another drawable shares the native mesh block")
    for sec in model.by_type(dm.PASSTHROUGH_GP):
        if sec.id != draw.data["passthroughgp"]:
            ref = dm.decode_passthroughgp(sec.payload)
            if ref["geometry"] == draw.geometry.id or ref["topology"] == draw.topology.id:
                raise ValueError("another GP shares the native geometry or topology")
    for sec in model.by_type(dm.TOPOLOGY_IP):
        if sec.id != draw.data["topologyip"] and dm.decode_topologyip(sec.payload)["topology"] == draw.topology.id:
            raise ValueError("another IP shares the native topology")


def _skin_streams(draw: Drawable, bone_ids: dict[int, int], worlds: dict) -> tuple[np.ndarray, np.ndarray]:
    palette = draw.bind["objects"]
    if (len(draw.bind["maps"]) != len(draw.data["atoms"]) + 1
            or any(m != list(range(len(palette))) for m in draw.bind["maps"])):
        raise ValueError("expected identity SkinBones maps for each render atom")
    if any(np.max(np.abs(np.asarray(dm.mat_mul(inv, worlds[bone])) - dm.IDENTITY)) > 0.002
           for bone, inv in zip(palette, draw.bind["rotations"])):
        raise ValueError("inverse binds do not match drawable's skeleton")
    if not np.allclose(worlds[draw.section.id], dm.IDENTITY, atol=0.002, rtol=0):
        raise ValueError("expected world-space bind vertices")
    return (np.asarray([bone_ids[i] for i in palette])[np.asarray(draw.geo["blendindices"])[:, :3]],
            np.asarray(draw.geo["blendweights"], dtype=np.float64))


def _rim(draw: Drawable, wrist: np.ndarray, axis: np.ndarray, low: float, high: float,
         faces: np.ndarray) -> np.ndarray:
    """Find the open lip, ignoring UV splits in the ring."""
    points, welded = np.unique(np.round(draw.geo["verts"], 4), axis=0, return_inverse=True)
    a, b, c = welded[faces].T
    edges, counts = np.unique(np.sort(np.concatenate((np.stack((a, b), 1), np.stack((b, c), 1),
                                                       np.stack((c, a), 1))), axis=1), axis=0, return_counts=True)
    boundary = points[np.unique(edges[counts == 1])] - wrist
    t = boundary @ axis
    radial = np.linalg.norm(boundary - t[:, None] * axis, axis=1)
    rim = wrist + boundary[(t > low) & (t < high) & (radial < 6)]
    if not 8 <= len(rim) <= 32:
        raise ValueError(f"expected a wrist boundary ring, got {len(rim)} vertices")
    return rim


def _atom_faces(draw: Drawable, atom: dict) -> np.ndarray:
    start = atom["base_index"] // 3
    return draw.faces[start:start + atom["tri_count"]]


def _smoothstep(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = np.clip(t, 0, 1)
    return t*t*(3 - 2*t), 6*t*(1-t)


def _warp(geo: dict[str, np.ndarray], where: np.ndarray, axis: np.ndarray, delta: np.ndarray,
          amount: np.ndarray, derivative: np.ndarray, shrink: float = 0) -> None:
    """Apply a local deformation and its Jacobian to the tangent frame."""
    geo["verts"][where] += amount[:, None] * delta
    jac = (np.eye(3) - (amount * shrink)[:, None, None] * (np.eye(3) - np.outer(axis, axis))
           + (delta * derivative[:, None])[:, :, None] * axis)
    inv_transpose = np.linalg.inv(jac).transpose(0, 2, 1)
    for key in ("normals", "uvdir_u", "uvdir_v"):
        mat = inv_transpose if key == "normals" else jac
        values = (mat @ geo[key][where, :, None])[:, :, 0]
        length = np.linalg.norm(values, axis=1, keepdims=True)
        geo[key][where] = values / np.where(length == 0, 1, length)


def _fit(draw: Drawable, knees: list[tuple[np.ndarray, np.ndarray]]) -> dict[str, np.ndarray]:
    geo = {key: np.asarray(draw.geo[key], dtype=np.float64) for key in ("verts", "normals", "uvdir_v", "uvdir_u")}
    v = geo["verts"]
    for source, shift in knees:
        span = 20.0
        z = v[:, 2] - source[2]
        slots = np.flatnonzero((v[:, 0] * source[0] > 0) & (np.abs(z) < span))
        frac, slope = _smoothstep(1 - np.abs(z[slots]) / span)
        _warp(geo, slots, np.array([0, 0, 1]), np.broadcast_to(shift, (len(slots), 3)),
              frac, -np.sign(z[slots]) * slope/span)
    return geo


def _replace(draw: Drawable, streams: dict, faces: np.ndarray, atoms: list[dict],
             ids: np.ndarray, weights: np.ndarray, worlds: dict) -> None:
    verts = streams["verts"]
    if len(verts) > 65536 or faces.min() < 0 or faces.max() >= len(verts):
        raise ValueError("mesh does not fit the native 16-bit index buffer")
    if not (np.isfinite(weights).all() and (weights >= 0).all() and np.allclose(weights.sum(1), 1, atol=2e-6)):
        raise ValueError("invalid skin weights")
    palette = np.unique(ids[weights > 0]).tolist()
    indices = np.column_stack((np.where(weights > 0, np.searchsorted(palette, ids), 0), np.zeros(len(ids), dtype=int)))
    geo = {**draw.geo, **streams, "vert_count": len(verts), "blendindices": indices, "blendweights": weights}
    top = {**draw.top, "indices": faces.ravel().tolist()}
    bad = bm.atom_problems(geo, top, atoms)
    if bad:
        raise ValueError("; ".join(bad))
    draw.geometry.payload = dm.encode_geometry(geo)
    draw.topology.payload = dm.encode_topology(top)
    draw.skin.payload = dm.encode_skinbones({**draw.bind, "objects": palette,
                                            "maps": [list(range(len(palette))) for _ in range(len(atoms) + 1)],
                                            "rotations": [dm.mat_inv(worlds[i]) for i in palette]})
    draw.section.payload = dm.encode_model_data({**draw.data, "atoms": atoms,
                                                  "bounds_min": verts.min(0), "bounds_max": verts.max(0),
                                                  "bounding_radius": np.linalg.norm(verts, axis=1).max()})


def _fit_unit(hila: dm.ModelFile, honoko: dm.ModelFile) -> dm.ModelFile:
    """Hila's unit with the outfit body and the trimmed caster; her gloves stay as shipped."""
    if len({s.id for s in hila.sections}) != len(hila.sections):
        raise ValueError("duplicate section IDs in native Hila model")
    nt, nw = bm._resolve_worlds(hila)
    dt, dw = bm._resolve_worlds(honoko)
    names = {o["name_hash"]: sid for sid, o in nt.items()}
    body, shadow = [Drawable.read(honoko, name) for name in ("g_body", "s_body")]
    target_body, target_shadow, head = [Drawable.read(hila, name) for name in ("g_body", "s_body", "g_head")]
    for d in (target_body, target_shadow):
        _exclusive(hila, d)
    for draw, expected in ((target_body, "mtr_suite_body"), (target_shadow, "shadow_caster")):
        if draw.material_hashes(hila) != [dm.hash64(expected)]:
            raise ValueError(f"expected native material {expected}")

    # Follow bone names, never donor section IDs (these are unrelated across units).
    bones = set(body.bind["objects"]) | set(shadow.bind["objects"])
    rebind = {b: names[dt[b]["name_hash"]] for b in bones}
    for b, new in rebind.items():
        if np.linalg.norm(np.asarray(dw[b][12:15]) - nw[new][12:15]) > 3:
            raise ValueError("unexpected bind-pose offset; this donor needs another fit")
    knees = []
    for side in ("Left", "Right"):
        knee = next(b for b in bones if dt[b]["name_hash"] == dm.hash64(side + "Leg"))
        source = np.asarray(dw[knee][12:15])
        knees.append((source, np.asarray(nw[rebind[knee]][12:15]) - source))

    slots_by_hash = {dm.hash64(f"officesuite_{slot}"): slot for slot in TILES}
    slots = [slots_by_hash.get(h) for h in body.material_hashes(honoko)]
    if any(slot is None for slot in slots) or sorted(slots) != sorted(TILES):
        raise ValueError("expected the six OfficeSuite material slots")
    ids, weights = _skin_streams(body, rebind, dw)
    body_geo = _fit(body, knees)
    uv = np.asarray(body.geo["uv0"])
    body_geo["uv0"] = uv.copy()
    for atom in body.data["atoms"]:
        start = atom["base_vertex"]
        stop = start + atom["slice_len"]
        faces = _atom_faces(body, atom)
        if faces.min() < start or faces.max() >= stop:
            raise ValueError("outfit atom reads outside its own UV tile")
        body_geo["uv0"][start:stop] = atlas_uvs(uv[start:stop], faces - start, slots[atom["material_id"]])
    atoms = [{**a, "material_id": 0} for a in body.data["atoms"]]
    _replace(target_body, body_geo, body.faces, atoms, ids, weights, nw)

    # Keep the outfit caster (hands included, so the shadow has fingers), plus
    # the solid head, not the stale Hila suit/hair or glove silhouette. The
    # native shadow shader is one-weight, so each part keeps its dominant bone.
    shadow_ids, shadow_weights = _skin_streams(shadow, rebind, dw)
    shadow_geo = _fit(shadow, knees)
    parts = [(shadow_geo, shadow.faces, shadow_ids, shadow_weights)]
    solid, = (a for a in head.data["atoms"] if head.material_hashes(hila)[a["material_id"]] == dm.hash64("mtr_head"))
    local = {i: i for i in head.bind["objects"]}
    parts.append((head.geo, _atom_faces(head, solid), *_skin_streams(head, local, nw)))
    verts, normals, faces, dominant = [], [], [], []
    base = 0
    for geo, triangles, bid, w in parts:
        used, mapped = np.unique(triangles.ravel(), return_inverse=True)
        verts.append(np.asarray(geo["verts"])[used])
        normals.append(np.asarray(geo["normals"])[used])
        faces.append(mapped.reshape(-1, 3) + base)
        dominant.append(bid[used, w[used].argmax(1)])
        base += len(used)
    shadow_geo = {"verts": np.concatenate(verts), "normals": np.concatenate(normals)}
    topology = np.concatenate(faces)
    atoms = [dict(base_vertex=0, slice_len=base, base_index=0, tri_count=len(topology), material_id=0)]
    _replace(target_shadow, shadow_geo, topology, atoms,
             np.column_stack((np.concatenate(dominant), np.zeros((base, 2), dtype=int))),
             np.tile([1., 0., 0.], (base, 1)), nw)
    # Hila's stock glove drawable is what covers the palm cut: it stays in the
    # model exactly as the game ships it, and so does its `.object` node (D59).
    return hila


def _material_config(xml: bytes) -> bytes:
    root = ET.fromstring(xml, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    material, = root.findall("material[@name='mtr_suite_body']")
    for slot, path in ATLAS_ASSETS.items():
        if material.find(slot).get("file") != path:
            raise ValueError(f"unexpected Hila suit {slot} texture path")
    material.set("render_template", SUIT_SHADER)
    # Hila's old GSMA is painted for another UV layout. OfficeSuite uses gloss in
    # the diffuse alpha and a DXT5nm normal map; leave every other slot alone.
    material.remove(material.find("material_texture"))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def build(honoko_zip: Path, head_zip: Path, out: Path) -> None:
    with ZipFile(head_zip) as src:
        files = {info.filename.removeprefix(HEAD_ROOT): src.read(info) for info in src.infolist()
                 if not info.is_dir() and info.filename.startswith(HEAD_ROOT)}
    with ZipFile(honoko_zip) as src:
        def outfit(path: str) -> bytes:
            return src.read(f"OfficeSuite/assets/{OUTFIT_DIR}/officesuite{path}")

        model = dm.ModelFile.read(outfit(".model"))
        for channel, suffix in (("diffuse_texture", "df"), ("bump_normal_texture", "nm")):
            files[ATLAS_ASSETS[channel] + ".texture"] = make_atlas(
                {slot: outfit(f"_{slot}_{suffix}.texture") for slot in TILES}, normal=(suffix == "nm"))
    base = files[UNIT + ".model"]
    menu = files[UNIT + "_menu.model"]
    files[UNIT + ".model"] = _fit_unit(dm.ModelFile.read(base), model).write()
    files[UNIT + "_menu.model"] = (files[UNIT + ".model"] if menu == base
                                   else _fit_unit(dm.ModelFile.read(menu), model).write())
    for suffix in ("", "_cc"):
        path = MATERIAL + suffix + ".material_config"
        files[path] = _material_config(files[path])
    files["README.txt"] = INSTALL_NOTE.encode("utf-8")
    write_deterministic_zip({f"{INSTALL}/{name}": data for name, data in files.items()}, [out])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--honoko", type=Path, default=dist_path(ROOT, "OfficeSuite.zip"), help="OfficeSuite body donor ZIP")
    parser.add_argument("--head", type=Path, default=dist_path(ROOT, "Miranda_Romance_over_Hila.zip"), help="Hila head donor ZIP")
    parser.add_argument("--out", type=Path, default=dist_path(ROOT, PACK), help="output ZIP (plus SHA-256 sidecar)")
    args = parser.parse_args(argv)
    determinism.enter(__file__)
    if args.out.resolve() in (args.honoko.resolve(), args.head.resolve()):
        parser.error("--out cannot overwrite a donor ZIP")
    build(args.honoko, args.head, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
