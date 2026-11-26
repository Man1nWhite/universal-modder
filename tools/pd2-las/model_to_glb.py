#!/usr/bin/env python3
"""Convert a PAYDAY 2 Diesel ``.model`` into a glTF 2.0 ``.glb`` plus its ``.dds`` textures.

Why: a compiled Diesel unit cannot be opened by Blender, three.js or any DCC. The
two things a viewer needs are a standard interchange mesh (``.glb``) and the unit's
image data. PAYDAY 2 ``.texture`` files **are** DDS buffers with no container of
their own (`vtf.py`: "PAYDAY 2 `.texture` files are raw DDS buffers"), so the
texture half of the conversion is the byte copy written beside the ``.glb``, and
the mesh half is what this module builds.

What a ``.model`` carries, and what it does not: geometry, topology, per-atom
material ids and `SkinBones` (inverse bind matrices + a per-drawable bone
palette). It carries **no** texture bytes — those come from the unit's own
``.texture`` files — and no bone-parent section, so ``--skin`` writes the
skeleton flat. Names are not in the file either: they are recovered from the
sibling ``.object`` (drawables), the ``.material_config`` files (material names,
diffuse/normal assets, ``ALPHA_MASKED``, ``alpha_ref``) and the model's own
custom hashlist when it has one.

Conventions, all of them measured on the tracked packs rather than assumed:

* **Units and axes.** Diesel is z-up, centimetres, feet at ``z = 0``. glTF is
  y-up, metres, +Z toward the viewer, so positions, normals and bone matrices go
  through ``q = p @ A`` with ``A = [[0.01,0,0,0],[0,0,0.01,0],[0,-0.01,0,0],
  [0,0,0,1]]`` — a rotation of -90° about X with det > 0, so winding is preserved
  and no triangle needs flipping.
* **UVs.** Diesel's decoded ``uv0`` is bottom-up; glTF's image origin is
  top-left, so ``v_gltf = 1 - v``. That is exactly the convention the tracked
  sheets in `docs/renders/` were rasterised with (``v_img = 1 - v_raw`` in
  `render_mod_previews.py`), which is why the exported atlas lands right-way-up
  instead of mirrored.
* **Indices.** RenderAtom triangle indices are **global** vertex indices into the
  drawable's geometry (`AGENTS.md`, invariant 2), so every atom becomes one
  primitive of the same mesh over one vertex buffer.
* **Normal maps.** Diesel stores DXT5 with X in alpha and Y in green; glTF wants
  tangent-space RGB. X and Y are copied out and Z is rebuilt as
  ``sqrt(1 - x² - y²)`` (`AGENTS.md`, invariant 4).
* **Alpha.** ``ALPHA_MASKED`` templates become ``alphaMode: MASK`` with the
  material's own ``alpha_ref`` (0.05 for hair), so cutouts survive; everything
  else stays opaque, because in this engine diffuse alpha is gloss, not opacity.
* **Skinning.** ``SkinBones.Rotations[i]`` is ``inverse(bone.WorldTransform)``,
  so the joint node is ``W @ A`` and glTF's inverse bind matrix is ``A⁻¹ @ IB``;
  their product is the identity, i.e. the mesh stays in its bind pose.

Non-goals: this is a viewer/interchange export. Nothing here is a runtime
oracle, ``runtime_verified`` stays false. Ad-hoc exports go under ``build/``;
the owner may commit an export instead, and then ``build_arivus_glb_pack.py``
is the reproducible packaging step (`AGENTS.md`, "What you ship", D74).

    # a pack: every .model inside, plus every .texture it references
    .venv/bin/python tools/pd2-las/model_to_glb.py dist/Arivus/Arivus_over_Hoxton.zip --all-textures

    # one unit with its textures found two directories up
    .venv/bin/python tools/pd2-las/model_to_glb.py path/to/npc_criminals_suit_1.model \\
        --textures path/to/characters -o build/arivus

    # only the replaced head, with the bind-pose skin
    .venv/bin/python tools/pd2-las/model_to_glb.py pack.zip --drawable g_head_old_hoxton --skin
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import diesel_model as dm  # noqa: E402
import tmc_export  # noqa: E402  (the tree's one glTF binary writer)

ROOT = HERE.parents[1]

FLOAT, USHORT, UINT = 5126, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963

#: diesel (cm, z-up) -> glTF (m, y-up), row-vector convention: q = p @ TO_GLTF
TO_GLTF = np.array([[0.01, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.01, 0.0],
                    [0.0, -0.01, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0]], dtype=np.float64)
FROM_GLTF = np.linalg.inv(TO_GLTF)

#: rig names of the 2B reference skeleton: hashed, they name anonymous bones
_SKELETON_JSON = HERE / "las_target_skeleton.json"


# ------------------------------------------------------------------ containers


class SourceError(RuntimeError):
    pass


class Source:
    """Read access to a unit's files: a ZIP pack, or a directory and extra roots.

    Entries are keyed by lower-case relative path. Lookups accept the ``file=``
    value a ``.material_config`` gives (``units/.../old_hoxton_head_p_df``),
    which points at ``<...>/old_hoxton_head_p_df.texture``.
    """

    def __init__(self, path: Path, extra_roots: list[Path] | None = None) -> None:
        self.path = Path(path)
        self._zip: zipfile.ZipFile | None = None
        self._files: dict[str, str] = {}          # lower-case rel path -> key
        if self.path.is_file() and self.path.suffix.lower() == ".zip":
            self._zip = zipfile.ZipFile(self.path)
            for n in self._zip.namelist():
                if not n.endswith("/"):
                    self._files[n.lower()] = n
        else:
            if self.path.is_dir():
                roots = [self.path]
            else:
                # a lone .model: its own unit folder, plus the two folders above it,
                # which is where a PD2 tree keeps `shared_textures/` for the unit
                roots = [self.path.parent, *list(self.path.parent.parents)[:2]]
            roots += [Path(r) for r in (extra_roots or [])]
            for root in roots:
                for p in sorted(Path(root).rglob("*")):
                    if p.is_file():
                        self._files.setdefault(p.relative_to(root).as_posix().lower(), str(p))

    def keys(self, suffix: str) -> list[str]:
        return [k for k in sorted(self._files) if k.endswith(suffix.lower())]

    def display(self, key: str) -> str:
        """The path a key stands for, in the source's own spelling."""
        return self._files.get(key.lower(), key)

    def read(self, ref: str) -> bytes:
        """Bytes of a relative path (any case) or of a value ``find`` returned."""
        key = self._files.get(ref.lower())
        if key is None and ref in self._files.values():
            key = ref
        if key is None:
            raise SourceError(f"{ref}: not in {self.path}")
        if self._zip is not None:
            return self._zip.read(key)
        return Path(key).read_bytes()

    def find(self, asset: str, suffix: str = ".texture") -> str | None:
        """Relative path for a material asset path, a basename, or a bare stem."""
        want = asset.replace("\\", "/").lower()
        if want.endswith(suffix):
            want = want[: -len(suffix)]
        tail = "/" + want + suffix
        for key in self._files:
            if key == want + suffix or key.endswith(tail):
                return self._files[key]
        base = want.rsplit("/", 1)[-1] + suffix
        for key in sorted(self._files):
            if key.rsplit("/", 1)[-1] == base:
                return self._files[key]
        return None


# ------------------------------------------------------------------ unit parts


@dataclass
class MaterialInfo:
    """One ``<material>`` of a ``.material_config``."""

    name: str
    template: str = ""
    diffuse: str | None = None
    normal: str | None = None
    alpha_ref: float | None = None

    @property
    def masked(self) -> bool:
        return "ALPHA_MASKED" in self.template.upper()


@dataclass
class Drawable:
    name: str
    model_data: dict
    geometry: dict
    topology: dict
    materials: list[dict]


@dataclass
class Unit:
    """One decoded ``.model``, before it becomes glTF."""

    rel: str
    model: dm.ModelFile
    drawables: list[Drawable] = field(default_factory=list)
    names: dict[int, str] = field(default_factory=dict)


def _folder(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def _hash_names(mf: dm.ModelFile, obj_texts: list[str]) -> dict[int, str]:
    """hash -> name, from the model's custom hashlist, the ``.object``, the rig list."""
    names: dict[int, str] = {}
    for sec in mf.by_type(dm.CUSTOM_HASHLIST):
        for n in dm.decode_custom_hashlist(sec.payload)["names"]:
            names[dm.hash64(n)] = n
    for text in obj_texts:
        for n in re.findall(r'<object\s+name="([^"]+)"', text):
            names.setdefault(dm.hash64(n), n)
    if _SKELETON_JSON.is_file():
        doc = json.loads(_SKELETON_JSON.read_text())
        for n in list(doc.get("skeleton") or []) + list(doc.get("collision_and_graphics") or []):
            names.setdefault(dm.hash64(n), n)
    return names


def read_material_configs(src: Source) -> dict[str, MaterialInfo]:
    """material name -> its diffuse/normal assets, template and alpha_ref."""
    out: dict[str, MaterialInfo] = {}
    for key in src.keys(".material_config"):
        try:
            root = ET.fromstring(src.read(key))
        except ET.ParseError as exc:                     # a broken config is not fatal
            print(f"warning: {key}: {exc}", file=sys.stderr)
            continue
        for mat in root.findall("material"):
            name = mat.attrib.get("name")
            if not name:
                continue
            info = MaterialInfo(name=name, template=mat.attrib.get("render_template", ""))
            diff = mat.find("diffuse_texture")
            if diff is not None and diff.attrib.get("file"):
                info.diffuse = diff.attrib["file"]
            bump = mat.find("bump_normal_texture")
            if bump is not None and bump.attrib.get("file"):
                info.normal = bump.attrib["file"]
            for var in mat.findall("variable"):
                if var.attrib.get("name") == "alpha_ref" and var.attrib.get("value"):
                    try:
                        info.alpha_ref = float(var.attrib["value"])
                    except ValueError:
                        pass
            out.setdefault(name, info)
    return out


def read_unit(src: Source, rel: str, matcfg: dict[str, MaterialInfo]) -> Unit:
    """Decode one ``.model`` into drawables, resolving the names it can."""
    rel = rel.lower()                                    # Source keys are lower-case
    mf = dm.ModelFile.read(src.read(rel))
    folder = _folder(rel)
    obj_texts = [src.read(k).decode("utf-8", "replace") for k in src.keys(".object")
                 if _folder(k) in (folder, "")]
    names = _hash_names(mf, obj_texts)
    for info in matcfg.values():
        names.setdefault(dm.hash64(info.name), info.name)

    unit = Unit(rel=rel, model=mf, names=names)
    for sec in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(sec.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        unit.drawables.append(Drawable(
            name=names.get(md["name_hash"], f"#{md['name_hash']:016x}"),
            model_data=md, geometry=geo, topology=topo,
            materials=[dm.decode_material(mf.by_id(mid).payload) for mid in mg["material_ids"]],
        ))
    return unit


def enabled_drawables(src: Source, unit: Unit) -> set[str]:
    """Names the unit's ``.object`` enables (``enabled="true"``)."""
    folder = _folder(unit.rel.lower())
    out: set[str] = set()
    for key in src.keys(".object"):
        if _folder(key) != folder:
            continue
        for tag in re.findall(r"<object\s+[^>]*>", src.read(key).decode("utf-8", "replace")):
            name = re.search(r'name="([^"]+)"', tag)
            flag = re.search(r'enabled="(true|false)"', tag)
            if name and flag and flag.group(1) == "true":
                out.add(name.group(1))
    return out


# --------------------------------------------------------------------- images


def dds_bytes(raw: bytes) -> bytes:
    """`raw` when it is a DDS buffer; a PD2 ``.texture`` is one already."""
    if raw[:4] == b"DDS ":
        return raw
    off = raw.find(b"DDS ")
    if off < 0:
        raise ValueError("no DDS header in the texture")
    return raw[off:]


def normal_map_png(dds: bytes) -> bytes:
    """DXT5nm (X in alpha, Y in green) -> tangent-space RGB PNG for glTF."""
    arr = np.asarray(Image.open(io.BytesIO(dds)).convert("RGBA"), dtype=np.float32)
    x = arr[..., 3] / 127.5 - 1.0
    y = arr[..., 1] / 127.5 - 1.0
    z = np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0))
    rgb = np.stack([x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5], axis=-1) * 255.0
    out = io.BytesIO()
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").save(out, format="PNG")
    return out.getvalue()


def colour_png(dds: bytes) -> bytes:
    """Diffuse/icon DDS -> PNG; alpha is the hair cutout on masked materials."""
    out = io.BytesIO()
    Image.open(io.BytesIO(dds)).convert("RGBA").save(out, format="PNG")
    return out.getvalue()


def placeholder_colour(name: str) -> list[float]:
    """A stable pale tint per material name, so an untextured part stays readable."""
    h = dm.hash64(name)
    return [0.62 + ((h >> s) & 0x3F) / 0x3F * 0.30 for s in (0, 8, 16)] + [1.0]


class Textures:
    """Writes each texture once (DDS and/or PNG) and embeds its PNG in the GLB."""

    def __init__(self, src: Source, out_dir: Path, glb: tmc_export.Glb,
                 write_dds: bool, write_png: bool) -> None:
        self.src = src
        self.out_dir = out_dir
        self.glb = glb
        self.write_dds = write_dds
        self.write_png = write_png
        self.images: list[dict] = []
        self.entries: dict[tuple[str, bool], int | None] = {}
        self.missing: list[str] = []
        self.dds: list[Path] = []
        self.png: list[Path] = []

    def _save(self, rel: str, dds: bytes, png: bytes, normal: bool) -> str:
        stem = Path(rel).name.rsplit(".", 1)[0]
        if self.write_dds or self.write_png:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        if self.write_dds:
            p = self.out_dir / f"{stem}.dds"
            if not p.exists():
                p.write_bytes(dds)
                self.dds.append(p)
        if self.write_png and png:
            p = self.out_dir / f"{stem}{'_gltf_normal' if normal else ''}.png"
            if not p.exists():
                p.write_bytes(png)
                self.png.append(p)
        return stem

    def image(self, asset: str, *, normal: bool) -> int | None:
        """GLB image index for a material asset, or None when the source lacks it."""
        key = (asset, normal)
        if key in self.entries:
            return self.entries[key]
        rel = self.src.find(asset)
        if rel is None:
            if asset not in self.missing:
                self.missing.append(asset)
            self.entries[key] = None
            return None
        try:
            dds = dds_bytes(self.src.read(rel))
            png = normal_map_png(dds) if normal else colour_png(dds)
        except Exception as exc:                              # noqa: BLE001 - report, keep going
            print(f"warning: {rel}: {exc}", file=sys.stderr)
            if asset not in self.missing:
                self.missing.append(asset)
            self.entries[key] = None
            return None
        name = self._save(rel, dds, png, normal)
        self.images.append({"name": name, "mimeType": "image/png",
                            "bufferView": self.glb.add_view(png, None)})
        self.entries[key] = len(self.images) - 1
        return self.entries[key]

    def copy_all(self) -> None:
        """Every ``.texture`` in the source as ``.dds`` (and PNG), referenced or not."""
        for key in self.src.keys(".texture"):
            try:
                dds = dds_bytes(self.src.read(key))
            except Exception as exc:                          # noqa: BLE001
                print(f"warning: {key}: {exc}", file=sys.stderr)
                continue
            try:
                png = colour_png(dds)
            except Exception:                                 # noqa: BLE001 - not a colour map
                png = b""
            if png or self.write_dds:
                self._save(self.src.display(key), dds, png, False)


# --------------------------------------------------------------------- export


@dataclass
class SkinBinding:
    """What ``--skin`` needs from one drawable's ``SkinBones`` section."""

    bones: list[int]              # palette: BLENDINDICES value -> diesel bone id
    slots: np.ndarray             # (n, 4) palette indices
    weights: np.ndarray           # (n, 4) normalised
    note: str | None = None


def _bone_bind_matrices(mf: dm.ModelFile) -> dict[int, np.ndarray]:
    """diesel bone id -> inverse bind matrix, from every SkinBones section.

    A bone appears in more than one drawable's palette (the suit's body and head
    both weight the spine), and a section only carries the matrices of its own
    palette, so the union is what makes a shared skeleton possible.
    """
    out: dict[int, np.ndarray] = {}
    for sec in mf.by_type(dm.SKINBONES):
        sb = dm.decode_skinbones(sec.payload)
        for bone_id, rows in zip(sb["objects"], sb["rotations"]):
            out.setdefault(int(bone_id), np.asarray(rows, dtype=np.float64).reshape(4, 4))
    return out


def _skin_binding(draw: Drawable, unit: Unit,
                  bone_ibm: dict[int, np.ndarray]) -> SkinBinding | None:
    """Resolve a drawable's blend indices to bone ids and normalised weights.

    ``maps[0]`` is the palette a BLENDINDICES value indexes. Some packs written by
    `build_joy_head_mods.py` offset the palette by one (their head weights start at
    1 because the source rig's palette begins with Hips) while the model's own
    skin section keeps the 3-bone list: every palette index past the end then
    reads as the missing first bone. That is detected here — only when *every*
    stray index is exactly one past the end — and the skin's root bone is
    prepended to restore the intended palette; anything else is dropped, with a
    note either way.
    """
    geo, md = draw.geometry, draw.model_data
    if not (geo["blendindices"] and geo["blendweights"]) or md.get("skinbones") is None:
        return None
    sb = dm.decode_skinbones(unit.model.by_id(md["skinbones"]).payload)
    objects = [int(b) for b in sb["objects"]]
    order = [int(i) for i in (sb["maps"][0] if sb["maps"] else range(len(objects)))]
    bones = [objects[i] if i < len(objects) else -1 for i in order]
    local = np.asarray(geo["blendindices"], dtype=np.int64)
    weights = np.asarray([w + (0.0,) * (4 - len(w)) for w in geo["blendweights"]],
                         dtype=np.float32)
    note: str | None = None

    if bones:
        stray = local >= len(bones)
        if stray.any():
            over = local[stray]
            if ((over == len(bones)).all() and int(sb["root"]) in bone_ibm
                    and int(sb["root"]) not in bones):
                bones = [int(sb["root"])] + bones
                note = (f"skin palette is one bone short: BLENDINDICES {len(bones) - 1} is "
                        f"one past the end of {len(objects)} listed bones, read here as the "
                        f"skin root {int(sb['root'])} (which restores the intended rig)")
            else:
                note = (f"{int(stray.any(axis=1).sum())} vertex/vertices weight a bone that "
                        f"is not in the {len(bones)}-bone palette; those weights are dropped")
                weights = np.where(stray, 0.0, weights)
                local = np.clip(local, 0, len(bones) - 1)
    if any(b < 0 for b in bones):
        note = note or "the skin palette names a bone the section does not list"
        weights = np.where(np.asarray(bones)[local] < 0, 0.0, weights)

    sums = weights.sum(axis=1, keepdims=True)
    unweighted = sums[:, 0] <= 0.0
    weights = np.where(sums > 0, weights / np.maximum(sums, 1e-8), weights)
    weights[unweighted] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    if unweighted.any() and note is None:
        note = f"{int(unweighted.sum())} vertex/vertices are unweighted (bound to the first bone)"
    return SkinBinding(bones=bones, slots=local, weights=weights, note=note)


def export_glb(src: Source, unit: Unit, matcfg: dict[str, MaterialInfo], out_path: Path,
               *, only: set[str] | None = None, enabled: set[str] | None = None,
               skin: bool = False, write_dds: bool = True, write_png: bool = True,
               all_textures: bool = False) -> dict:
    """Write ``unit`` as a glTF 2.0 ``.glb`` with its textures beside it; return a report."""
    glb = tmc_export.Glb()
    tex = Textures(src, out_path.parent / "textures", glb, write_dds, write_png)
    if all_textures:
        tex.copy_all()

    targets = [d for d in unit.drawables
               if (not only or d.name in only) and (enabled is None or d.name in enabled)]

    warnings: list[str] = []
    bone_ibm = _bone_bind_matrices(unit.model) if skin else {}
    bindings: dict[str, SkinBinding] = {}
    if skin:
        for draw in targets:
            binding = _skin_binding(draw, unit, bone_ibm)
            if binding is not None:
                bindings[draw.name] = binding
                if binding.note:
                    warnings.append(f"{draw.name}: {binding.note}")

    # JOINTS_0 indexes the skin's own `joints` array, not the node array, so the
    # slot a bone gets has to be fixed before any vertex attribute is written.
    joint_slot: dict[int, int] = {}
    for binding in bindings.values():
        for bone in binding.bones:
            if bone >= 0 and bone in bone_ibm:
                joint_slot.setdefault(bone, len(joint_slot))

    nodes: list[dict] = []
    meshes: list[dict] = []
    materials: list[dict] = []
    textures: list[dict] = []
    material_index: dict[tuple, int] = {}
    mesh_nodes: list[int] = []
    joints: dict[int, tuple[int, np.ndarray]] = {}

    def joint_node(bone_id: int) -> int:
        """Node index for a diesel bone; the node transform is its bind world."""
        if bone_id in joints:
            return joints[bone_id][0]
        inv_bind = bone_ibm[bone_id]
        # IB = W^-1, W' = W @ A, IB' = A^-1 @ IB  =>  W' = IB^-1 @ A
        world = np.linalg.inv(inv_bind) @ TO_GLTF
        nodes.append({"name": unit.names.get(bone_id, f"bone_{bone_id:04d}"),
                      "matrix": [float(v) for v in world.flatten()]})
        joints[bone_id] = (len(nodes) - 1, FROM_GLTF @ inv_bind)
        return joints[bone_id][0]

    def texture_entry(image: int) -> int:
        for i, t in enumerate(textures):
            if t["source"] == image:
                return i
        textures.append({"source": image, "sampler": 0})
        return len(textures) - 1

    def material_for(mat: dict) -> int:
        name = unit.names.get(mat["name_hash"], f"#{mat['name_hash']:016x}")
        info = matcfg.get(name)
        diffuse = tex.image(info.diffuse, normal=False) if info and info.diffuse else None
        normal = tex.image(info.normal, normal=True) if info and info.normal else None
        cutoff = info.alpha_ref if info and info.alpha_ref is not None else 0.05
        key = (name, diffuse, normal, bool(info and info.masked), round(float(cutoff), 4))
        if key in material_index:
            return material_index[key]

        pbr: dict = {"metallicFactor": 0.0, "roughnessFactor": 0.85}
        if diffuse is not None:
            pbr["baseColorTexture"] = {"index": texture_entry(diffuse)}
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
        else:
            pbr["baseColorFactor"] = placeholder_colour(name)
        entry: dict = {"name": name, "doubleSided": True, "pbrMetallicRoughness": pbr}
        if normal is not None:
            entry["normalTexture"] = {"index": texture_entry(normal)}
        if info and info.masked:
            entry["alphaMode"] = "MASK"
            entry["alphaCutoff"] = round(float(cutoff), 4)
        extras: dict = {}
        if info:
            extras["pd2_template"] = info.template
        if diffuse is None and info and info.diffuse:
            extras["pd2_diffuse_missing"] = info.diffuse
        if extras:
            entry["extras"] = extras
        materials.append(entry)
        material_index[key] = len(materials) - 1
        return material_index[key]

    for draw in targets:
        geo, topo, md = draw.geometry, draw.topology, draw.model_data
        if not geo["verts"]:
            continue
        positions = (np.asarray(geo["verts"], dtype=np.float64)
                     @ TO_GLTF[:3, :3].T).astype(np.float32)
        attributes = {"POSITION": glb.add_accessor(positions, FLOAT, "VEC3", ARRAY_BUFFER,
                                                   len(positions))}
        if geo["normals"]:
            nrm = np.asarray(geo["normals"], dtype=np.float64) @ TO_GLTF[:3, :3].T
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
            attributes["NORMAL"] = glb.add_accessor(nrm.astype(np.float32), FLOAT, "VEC3",
                                                    ARRAY_BUFFER, len(nrm))
        if geo["uv0"]:
            uv = np.asarray(geo["uv0"], dtype=np.float32).copy()
            uv[:, 1] = 1.0 - uv[:, 1]           # diesel bottom-up -> glTF top-left
            attributes["TEXCOORD_0"] = glb.add_accessor(uv, FLOAT, "VEC2", ARRAY_BUFFER, len(uv))

        binding = bindings.get(draw.name)
        if binding is not None:
            palette_slots = np.asarray([joint_slot.get(b, -1) for b in binding.bones], np.int64)
            index = np.clip(binding.slots, 0, max(len(palette_slots) - 1, 0))
            slots = palette_slots[index] if len(palette_slots) else np.zeros(index.shape, np.int64)
            slots = np.where(slots >= 0, slots, 0)
            attributes["JOINTS_0"] = glb.add_accessor(
                np.ascontiguousarray(slots.astype(np.uint16)), USHORT, "VEC4",
                ARRAY_BUFFER, len(slots))
            attributes["WEIGHTS_0"] = glb.add_accessor(
                np.ascontiguousarray(binding.weights), FLOAT, "VEC4", ARRAY_BUFFER,
                len(binding.weights))
            for bone in binding.bones:
                if bone in joint_slot:
                    joint_node(bone)

        indices = np.asarray(topo["indices"], dtype=np.int64)
        primitives = []
        for atom in md["atoms"]:
            first, count = atom["base_index"] // 3, atom["tri_count"]
            tri = indices[first * 3:(first + count) * 3]
            if tri.size == 0:
                continue
            if tri.max() >= len(positions):
                warnings.append(f"{draw.name}: an atom indexes past the vertex buffer")
                continue
            material = (material_for(draw.materials[atom["material_id"]])
                        if atom["material_id"] < len(draw.materials) else 0)
            primitives.append({
                "attributes": dict(attributes),
                "indices": glb.add_accessor(np.ascontiguousarray(tri.astype(np.uint32)), UINT,
                                            "SCALAR", ELEMENT_ARRAY_BUFFER, len(tri)),
                "material": material,
                "mode": 4,
            })
        if not primitives:
            warnings.append(f"{draw.name}: no triangles")
            continue
        nodes.append({"name": draw.name, "mesh": len(meshes)})
        mesh_nodes.append(len(nodes) - 1)
        meshes.append({"name": draw.name, "primitives": primitives})

    skins: list[dict] = []
    if joints:
        order = sorted(joints, key=lambda b: joint_slot[b])
        rows = np.stack([np.asarray(joints[b][1], dtype=np.float32).reshape(16) for b in order])
        # a row-vector matrix's glTF (column-major) array is its row-major flattening
        acc = glb.add_accessor(np.ascontiguousarray(rows), FLOAT, "MAT4", None, len(rows))
        skins.append({"joints": [joints[b][0] for b in order], "inverseBindMatrices": acc})
        for node_index in mesh_nodes:
            nodes[node_index]["skin"] = 0

    gltf: dict = {
        "asset": {"version": "2.0",
                  "generator": "universal-modder tools/pd2-las/model_to_glb.py"},
        "scene": 0,
        "scenes": [{"name": Path(out_path).stem, "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
        "images": tex.images,
        "textures": textures,
        "extras": {"pd2_model": unit.rel,
                   "conventions": {"units": "m (1/100 of a diesel cm)",
                                   "up": "y-up (-90 deg about X from diesel z-up)",
                                   "uv_origin": "top-left (v = 1 - diesel v)",
                                   "front_face": "CCW (winding preserved)",
                                   "skin": "flat: a diesel .model stores no bone parents"}},
    }
    if skins:
        gltf["skins"] = skins
    if warnings:
        gltf["extras"]["warnings"] = sorted(set(warnings))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = glb.build(gltf)
    out_path.write_bytes(data)
    return {"glb": out_path, "bytes": len(data), "meshes": len(meshes),
            "primitives": sum(len(m["primitives"]) for m in meshes),
            "materials": len(materials), "images": len(tex.images),
            "skins": len(skins), "joints": len(joints),
            "dds": tex.dds, "png": tex.png, "missing": tex.missing,
            "warnings": sorted(set(warnings)),
            "drawables": [m["name"] for m in meshes]}


def models_in(src: Source, pattern: str | None) -> list[str]:
    keys = src.keys(".model")
    if pattern:
        keys = [k for k in keys if pattern.lower() in k.lower()]
    if not keys:
        raise SourceError(f"no .model in {src.path}"
                          + (f" matching {pattern!r}" if pattern else ""))
    return keys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="a .model, a .zip pack, or a directory holding them")
    ap.add_argument("-o", "--out", default=None,
                    help="output directory (default: build/model_glb/<model stem>/)")
    ap.add_argument("--model", default=None,
                    help="only .model paths containing this text (a pack holds several)")
    ap.add_argument("--drawable", action="append", default=None,
                    help="export only these drawables (e.g. g_head_old_hoxton); repeatable")
    ap.add_argument("--enabled-only", action="store_true",
                    help="export only the drawables the unit's .object enables")
    ap.add_argument("--skin", action="store_true",
                    help="also write the bind-pose skeleton and weights (flat: a "
                         "Diesel .model stores no bone hierarchy)")
    ap.add_argument("--textures", action="append", default=None,
                    help="extra directory to search for .texture files; repeatable")
    ap.add_argument("--all-textures", action="store_true",
                    help="write every .texture in the source as .dds, not only the used ones")
    ap.add_argument("--no-dds", action="store_true", help="do not write the .dds copies")
    ap.add_argument("--no-png", action="store_true", help="do not write the PNG copies")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)

    try:
        src = Source(Path(args.source), [Path(p) for p in (args.textures or [])])
        matcfg = read_material_configs(src)
        model_keys = models_in(src, args.model)
    except (SourceError, OSError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"model_to_glb: {exc}") from exc

    only = set(args.drawable) if args.drawable else None
    json_report = []
    for rel in model_keys:
        unit = read_unit(src, rel, matcfg)
        if not unit.drawables:
            print(f"skip {unit.rel}: no version-3 model data with render atoms",
                  file=sys.stderr)
            continue
        if only:
            unknown = sorted(only - {d.name for d in unit.drawables})
            if unknown:
                print(f"warning: {unit.rel}: no drawable named {', '.join(unknown)}",
                      file=sys.stderr)
        enabled: set[str] | None = None
        if args.enabled_only:
            enabled = enabled_drawables(src, unit)
            if not enabled:
                print(f"warning: {unit.rel}: no .object beside this unit, "
                      f"so --enabled-only exports nothing for it", file=sys.stderr)
        stem = Path(unit.rel).stem
        out_dir = Path(args.out) if args.out else ROOT / "build" / "model_glb" / stem
        report = export_glb(src, unit, matcfg, out_dir / f"{stem}.glb", only=only,
                            enabled=enabled, skin=args.skin, write_dds=not args.no_dds,
                            write_png=not args.no_png, all_textures=args.all_textures)
        if not report["meshes"]:
            # an empty glTF is not a conversion: leave no file behind to be mistaken for one
            Path(report["glb"]).unlink(missing_ok=True)
            report["glb"] = None
            continue
        report["source"] = unit.rel
        json_report.append(report)

    if args.json:
        print(json.dumps([{**r, "glb": str(r["glb"]),
                           "dds": [str(p) for p in r["dds"]],
                           "png": [str(p) for p in r["png"]]} for r in json_report], indent=2))
        return 0

    for r in json_report:
        unnamed = len([d for d in r["drawables"] if d.startswith("#")])
        print(f"{r['glb']}  ({r['bytes'] / 1e6:.2f} MB)")
        print(f"  source     {r['source']}")
        print(f"  meshes     {r['meshes']} drawables ({unnamed} unnamed), "
              f"{r['images']} image(s) embedded")
        print(f"  materials  {r['materials']}"
              + (f", {r['joints']} joints ({r['skins']} skin)" if r["skins"] else ""))
        if r["dds"]:
            print(f"  dds        {len(r['dds'])} file(s) in {r['dds'][0].parent}")
        if r["missing"]:
            print(f"  missing    {len(r['missing'])} texture(s) not in the source:")
            for m in r["missing"][:5]:
                print(f"             {m}")
            if len(r["missing"]) > 5:
                print(f"             ... and {len(r['missing']) - 5} more")
        for w in r["warnings"][:5]:
            print(f"  warning    {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
