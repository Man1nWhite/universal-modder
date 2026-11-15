"""The invariants of `tools/pd2-las`, one test each, named after the invariant.

`tools/pd2-las/README.md` has a table called Invariants. Every row of it names
exactly one test in this file, and the test's name starts with the row's name:
`test_units_...`, `test_uvs_...`, `test_winding_...` and so on, so a red test
says which invariant broke and the table says what it means
(`tests/test_pd2_las_status.py` keeps the two lists equal).

These tests read the **tracked packs** in `dist/`, decoded with the codec alone
(`diesel_model`). Nothing is built and the 2B templates are not needed, so they
run on a fresh clone and in CI, where the authoring tests in
`test_build_models.py` and `test_bust_variant.py` skip
for want of the templates. Those keep the detail; this file keeps the contract.
Two builder modules are imported for constants only: where the source models
sit inside the VPK, and the region the chest variant declares.

Every number in an assertion was measured on the tracked packs first; the
comment beside it gives the measured value.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import re
import struct
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "tools" / "pd2-las"
sys.path.insert(0, str(HERE))

import build_las  # noqa: E402  (the paths of the source models inside the VPK)
import bust_variant  # noqa: E402  (the chest region the variant declares)
import diesel_model as dm  # noqa: E402
from extract_2b import MISSING, TEMPLATES  # noqa: E402
from source_model import load_model  # noqa: E402
from vpk import VpkArchive  # noqa: E402


def _status():
    spec = importlib.util.spec_from_file_location("pd2_las_status", HERE / "status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: tracked pack -> the LAS item id it registers: also its unit folder and its file stem.
#: Written out so that collecting this file opens no archive; the registration test
#: holds it to each pack's BUILD_INFO.json and to the list `status.py` reports on.
ITEMS = {"Miranda_LAS": "miranda", "Miranda_Busty_LAS": "miranda_busty",
         "Christie_LAS": "christie", "Christie_LAS_Slim": "christie_slim"}
PACKS = tuple(ITEMS)
RESTORE = "a tracked pack is missing; restore it with `git checkout -- dist build`"


# ----------------------------------------------------------------- reading


@dataclass
class Drawable:
    """One mesh node of a built model, decoded."""

    name: str
    verts: np.ndarray        # (n, 3) cm
    normals: np.ndarray      # (n, 3)
    uvs: list                # [(u, v)] as the codec returns them: (u, 1 - v_image)
    faces: np.ndarray        # (m, 3) absolute vertex indices
    weights: np.ndarray      # (n, 3), or (0, 3) for an unskinned node
    indices: np.ndarray      # (n, 4) palette-local bone indices
    palette: list            # bone names, in palette order
    rest: np.ndarray         # (len(palette), 3) joint positions the vertices are bound to
    atoms: list              # render atoms: base_vertex, slice_len, base_index, tri_count, material_id
    materials: list          # material name hashes, indexed by an atom's material_id


@dataclass
class Model:
    pack: str
    stem: str
    data: bytes
    drawables: dict          # name -> Drawable
    joints: dict             # bone name -> world position in the embedded skeleton
    parent: dict             # bone name -> parent bone name (or None)

    @property
    def first_person(self) -> bool:
        return self.stem.startswith("fps_")

    def skinned(self) -> list:
        return [d for d in self.drawables.values() if len(d.weights)]


@functools.lru_cache(maxsize=None)
def _zip(pack: str) -> zipfile.ZipFile:
    path = REPO / "dist" / f"{pack}.zip"
    assert path.is_file(), f"{path.relative_to(REPO)}: {RESTORE}"
    return zipfile.ZipFile(path)


@functools.lru_cache(maxsize=None)
def _info(pack: str) -> dict:
    return json.loads(_zip(pack).read(f"{pack}/BUILD_INFO.json"))


def _unit_dir(pack: str) -> str:
    return f"{pack}/assets/units/{ITEMS[pack]}/skins/{ITEMS[pack]}"


@functools.lru_cache(maxsize=None)
def _model(pack: str, stem: str) -> Model:
    data = _zip(pack).read(f"{_unit_dir(pack)}/{stem}.model")
    mf = dm.ModelFile.read(data)
    names = {dm.hash64(n): n
             for n in dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]}

    # every node of the scene graph: bones are Object3D, meshes are model data
    nodes = {}
    for section in mf.sections:
        if section.type == dm.OBJECT3D:
            nodes[section.id] = dm.decode_object3d(section.payload)
        elif section.type == dm.MODEL_DATA:
            nodes[section.id] = dm.decode_model_data(section.payload)
    name_of = {sid: names.get(node["name_hash"], f"#{node['name_hash']:016x}")
               for sid, node in nodes.items()}

    def world(sid):
        node = nodes[sid]
        local = list(node["matrix"])
        local[12:15] = node["pos"]
        return tuple(local) if node["parent"] == 0 else dm.mat_mul(tuple(local), world(node["parent"]))

    joints = {name_of[sid]: np.array(world(sid)[12:15]) for sid in nodes}
    parent = {name_of[sid]: name_of.get(node["parent"]) for sid, node in nodes.items()}

    drawables = {}
    for sid, node in nodes.items():
        if node.get("version") != 3:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(node["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        group = dm.decode_material_group(mf.by_id(node["matgroup"]).payload)
        skinned = bool(geo["blendweights"])
        skin = dm.decode_skinbones(mf.by_id(node["skinbones"]).payload) if skinned else None
        drawables[name_of[sid]] = Drawable(
            name=name_of[sid],
            verts=np.asarray(geo["verts"], float).reshape(-1, 3),
            normals=np.asarray(geo["normals"], float).reshape(-1, 3),
            uvs=list(geo["uv0"]),
            faces=np.asarray(topo["indices"], int).reshape(-1, 3),
            weights=np.asarray(geo["blendweights"], float).reshape(-1, 3),
            indices=np.asarray(geo["blendindices"], int).reshape(-1, 4),
            palette=[name_of[b] for b in skin["objects"]] if skinned else [],
            # the skin section stores each bone's inverse bind: its inverse is where
            # the bone is in the pose the vertices were authored in
            rest=(np.array([dm.mat_inv(m)[12:15] for m in skin["rotations"]])
                  if skinned else np.zeros((0, 3))),
            atoms=list(node["atoms"]),
            materials=[dm.decode_material(mf.by_id(i).payload)["name_hash"]
                       for i in group["material_ids"]],
        )
    return Model(pack=pack, stem=stem, data=data, drawables=drawables, joints=joints, parent=parent)


def _stems(pack: str) -> tuple:
    """The two models of a pack: third person, then first person."""
    return (ITEMS[pack], f"fps_{ITEMS[pack]}")


def _all_models() -> list:
    return [pytest.param(pack, stem, id=f"{pack}/{stem}") for pack in PACKS for stem in _stems(pack)]


each_model = pytest.mark.parametrize(("pack", "stem"), _all_models())
each_pack = pytest.mark.parametrize("pack", PACKS)


@functools.lru_cache(maxsize=None)
def _source(first_person: bool):
    """The L4D2 model the Miranda packs are built from, as the Source reader decodes it."""
    arc = VpkArchive.from_zip(str(REPO / "models" / "l4d2_miranda_lawson_1.zip"),
                              "miranda_rochelle.vpk")
    paths = build_las.FPS_MDLS if first_person else build_las.TPP_MDLS
    return load_model(*(arc.read(p) for p in paths))


@dataclass
class Texture:
    """A `.texture` file: a DXT5 DDS."""

    size: tuple              # (width, height) of level 0
    flags: int               # DDS header flags
    caps: int                # DDS header caps
    levels: list             # one (n, 16) uint8 array of 4x4 blocks per mip level

    def endpoints(self) -> tuple:
        """The two RGB565 colour endpoints of every block, all levels."""
        blocks = np.vstack(self.levels).astype(np.int32)
        return blocks[:, 8] | (blocks[:, 9] << 8), blocks[:, 10] | (blocks[:, 11] << 8)

    def alpha(self, level: int = 0) -> np.ndarray:
        """The alpha of every texel of one level, decoded, as an image.

        A level smaller than a block still fills a block; the texels beyond the
        level's own size are not part of the image and are cut off here.
        """
        blocks = self.levels[level]
        a0, a1 = blocks[:, 0].astype(np.int32), blocks[:, 1].astype(np.int32)
        bits = np.zeros(len(blocks), dtype=np.uint64)
        for k in range(6):
            bits |= blocks[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
        index = np.stack([(bits >> np.uint64(3 * k)) & np.uint64(7) for k in range(16)],
                         axis=1).astype(np.int64)
        eight = a0 > a1                           # 8 interpolated values, else 6 plus 0 and 255
        palette = np.zeros((len(blocks), 8), dtype=np.int32)
        palette[:, 0], palette[:, 1] = a0, a1
        for k in range(1, 7):
            six = ((5 - k) * a0 + k * a1) // 5 if k < 5 else np.full_like(a0, 0 if k == 5 else 255)
            palette[:, k + 1] = np.where(eight, ((7 - k) * a0 + k * a1) // 7, six)
        texels = np.take_along_axis(palette, index, axis=1)
        width, height = (max(1, side >> level) for side in self.size)
        across, down = (width + 3) // 4, (height + 3) // 4
        image = texels.reshape(down, across, 4, 4).transpose(0, 2, 1, 3).reshape(down * 4, across * 4)
        return image[:height, :width]


def _texture(raw: bytes) -> Texture:
    assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5", "not a DXT5 DDS"
    flags, height, width = struct.unpack_from("<3I", raw, 8)
    count = max(1, struct.unpack_from("<I", raw, 28)[0])
    caps = struct.unpack_from("<I", raw, 108)[0]
    sizes = [max(1, ((width >> level) + 3) // 4) * max(1, ((height >> level) + 3) // 4)
             for level in range(count)]
    assert len(raw) == 128 + 16 * sum(sizes), (
        f"the header declares {count} levels of {width}x{height}: {128 + 16 * sum(sizes)} bytes, "
        f"the file has {len(raw)}")
    data = np.frombuffer(raw, dtype=np.uint8, offset=128).reshape(-1, 16)
    starts = np.cumsum([0] + sizes)
    return Texture(size=(width, height), flags=flags, caps=caps,
                   levels=[data[a:b] for a, b in zip(starts[:-1], starts[1:])])


def _area(verts: np.ndarray, faces: np.ndarray) -> float:
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    return float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2.0)


def _signed_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def _declared_materials(pack: str, stem: str) -> dict:
    """name -> what the unit's material_config declares for it."""
    config = _zip(pack).read(f"{_unit_dir(pack)}/{stem}.material_config").decode()
    declared = {}
    for match in re.finditer(r"<material\b([^>]*?)(/?)>", config):
        attributes = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1)))
        body = "" if match.group(2) else config[match.end():config.index("</material>", match.end())]
        declared[attributes["name"]] = {
            "template": attributes.get("render_template", "").split(":"),
            "unique": attributes.get("unique") == "true",
            "variables": set(re.findall(r'<variable\b[^>]*\bname="(\w+)"', body)),
            "textures": set(re.findall(r"<(\w+_texture)\b", body)),
        }
    assert declared, f"{stem}.material_config declares no material"
    return declared


def _material_names(pack: str, stem: str) -> dict:
    """name hash -> name, for the materials the unit's material_config declares."""
    return {dm.hash64(name): name for name in _declared_materials(pack, stem)}


# ------------------------------------------------------------- invariants


@each_model
def test_units_are_centimetres_at_the_scale_of_the_rig(pack, stem):
    """**Units.** Source is inches, Diesel centimetres, and nothing multiplies by 2.54.

    The mesh is fitted bone by bone onto the PAYDAY 2 player skeleton that the 2B
    template carries, and the fits bring the scale with them. So the test is not a
    conversion factor but the result:

    1. the embedded skeleton is the player rig, in centimetres;
    2. every vertex lies within reach of the bone that owns it;
    3. the third-person body stands on the ground and ends where the rig says a body
       ends, at the collar or above the Head joint;
    4. in the Miranda packs, which carry their whole source, the mesh is the
       source enlarged by the scale the fits found, which is not 2.54 in either
       model. It is measured on surface area, so the pose does not matter.

    A mesh still in inches fails 2, 3 and 4. One that was only multiplied by 2.54
    fails 4, and in third person 3 as well: the source is shorter than the rig.

    The Christie packs have no check 4. They are a cut of their source (no head;
    slim also without hands, and thinner), so the source's area is no measure for
    them, and a first-person Christie mesh that was only multiplied by 2.54 passes.
    """
    model = _model(pack, stem)
    hips, neck, head = (model.joints[name][2] for name in ("Hips", "Neck", "Head"))
    assert 100.0 < hips < 104.0 and 157.0 < neck < 162.0 and 164.0 < head < 170.0, (
        f"not the PD2 player rig in cm: Hips {hips:.1f}, Neck {neck:.1f}, Head {head:.1f}")
    # measured: 101.8 / 159.3 / 166.8 in all eight models

    for d in model.skinned():
        owner = d.indices[np.arange(len(d.verts)), d.weights.argmax(axis=1)]
        reach = np.linalg.norm(d.verts - d.rest[owner], axis=1)
        # measured: at most 46.6 cm in third person (Christie's shoe, on `LeftLeg`)
        # and 34.9 cm in first person (Christie's shoulder, on `Spine1`)
        limit = 45.0 if model.first_person else 60.0
        assert reach.max() < limit, (
            f"{d.name}: a vertex sits {reach.max():.1f} cm from the bone it is bound to")

    if not model.first_person:
        body = np.vstack([d.verts for d in model.skinned() if d.name.startswith("g_")])
        low, top = body[:, 2].min(), body[:, 2].max()
        assert -6.0 < low < 3.0, f"the feet are at z = {low:.1f} cm, not on the ground"  # -0.75 / -3.15
        if any(d.name.startswith("g_head") for d in model.skinned()):
            # measured: 188.1 cm. The source is 64.9 in tall: times 2.54 is 164.9 cm,
            # below this rig's Head joint.
            assert top > head + 10.0, f"the head ends at z = {top:.1f} cm, Head joint at {head:.1f}"
        else:
            # body only: the collar ends between the Neck and the Head joint (163.8)
            assert neck - 3.0 < top < head + 3.0, f"the body ends at z = {top:.1f} cm"

    if pack.startswith("Miranda"):
        source = _source(model.first_person)
        faces = np.array([i for mesh in source.meshes for i in mesh.triangle_indices]).reshape(-1, 3)
        shadow = model.drawables["s_body"]          # every triangle of the model, once
        scale = (_area(shadow.verts, shadow.faces)
                 / _area(np.array([v.pos for v in source.vertices]), faces)) ** 0.5
        # measured: 2.90 in third person (2.91 with the larger chest), 2.35 in first
        low, high = (2.2, 2.45) if model.first_person else (2.75, 3.05)
        assert low < scale < high, (
            f"the mesh is {scale:.3f} x its source: not the scale the fits give "
            f"({low} to {high}; 2.54 would be a bare unit conversion)")


@pytest.mark.parametrize("first_person", [False, True], ids=["Miranda_LAS/miranda",
                                                              "Miranda_LAS/fps_miranda"])
def test_uvs_are_stored_as_u_and_one_minus_v(first_person):
    """**UVs.** A vertex keeps the source's texture coordinate as `(u, 1 - v_src)`.

    That is the 2B convention (image row 0 at v = 1). Source V tiles, so values
    outside 0-1 are normal and must not be wrapped or clamped: every material's
    coordinates are compared as a multiset with the source's, which a wrap, a clamp
    or a missing flip all change.

    The eyes are the one exception, on purpose: the build draws its own eye texture
    and `repair_skin_boundary_normals` projects the eyeballs onto it, inside 0.02-0.98.
    """
    stem = "fps_miranda" if first_person else "miranda"
    model, source = _model("Miranda_LAS", stem), _source(first_person)
    named = _material_names("Miranda_LAS", stem)

    def key(uv):
        return (round(uv[0], 5), round(uv[1], 5))

    want = {}       # pack material -> the source coordinates, flipped
    pack_material = {"miranda_body": "mtr_body", "miranda_face": "mtr_face",
                     "miranda_head": "mtr_head", "miranda_hair": "mtr_hair",
                     "eyeball_l": "mtr_eyes", "eyeball_r": "mtr_eyes"}
    for mesh in source.meshes:
        used = dict.fromkeys(mesh.triangle_indices)        # each vertex once, in order
        want.setdefault(pack_material[mesh.material], Counter()).update(
            key((source.vertices[i].uv[0], 1.0 - source.vertices[i].uv[1])) for i in used)
    assert any(not 0.0 <= v <= 1.0 for uvs in want.values() for _, v in uvs), (
        "the source no longer tiles in V; this test would not notice a clamp")

    got = {}
    for name in ("g_body", "g_head"):
        d = model.drawables[name]
        for atom in d.atoms:
            block = d.uvs[atom["base_vertex"]:atom["base_vertex"] + atom["slice_len"]]
            got.setdefault(named[d.materials[atom["material_id"]]], []).extend(block)
    if first_person:
        got = {"mtr_body": model.drawables["g_body"].uvs}  # g_head repeats the arms there

    assert set(got) == set(want), (sorted(got), sorted(want))
    for material, uvs in sorted(got.items()):
        if material == "mtr_eyes":
            assert all(0.02 - 1e-6 <= c <= 0.98 + 1e-6 for uv in uvs for c in uv), (
                "an eyeball vertex is off the eye texture")
            continue
        assert Counter(map(key, uvs)) == want[material], (
            f"{material}: the stored coordinates are not the source's (u, 1 - v)")


@each_model
def test_winding_is_outward_with_no_inverted_triangle(pack, stem):
    """**Winding.** Triangles are wound the other way round from Source: `(a,b,c) -> (a,c,b)`.

    Three things follow and all three are checked. No shared edge is walked in the
    same direction by both of its triangles: on these welded meshes that is the exact
    test for a triangle the engine culls into a hole (`build_models.orientation_breaks`).
    Taken as a whole, the faces point the way the stored normals do: that tells an
    inside-out mesh from a correct one even where the mesh is an open sleeve. It is
    a count over the mesh and not a per-triangle test, which on a skinned mesh
    misfires at the joints. And the third-person shadow body encloses a positive
    volume, where the source mesh, wound as Source winds it, encloses a negative one.
    """
    model = _model(pack, stem)
    for d in model.skinned():
        direction = {}
        for a, b, c in d.faces.tolist():
            for x, y in ((a, b), (b, c), (c, a)):
                direction.setdefault((x, y) if x < y else (y, x), []).append(x < y)
        breaks = sum(1 for seen in direction.values() if len(seen) == 2 and seen[0] == seen[1])
        assert breaks == 0, f"{d.name}: {breaks} edges whose two triangles disagree"

        normal = np.cross(d.verts[d.faces[:, 1]] - d.verts[d.faces[:, 0]],
                          d.verts[d.faces[:, 2]] - d.verts[d.faces[:, 0]])
        real = np.linalg.norm(normal, axis=1) > 1e-9
        agree = np.einsum("ij,ij->i", normal, d.normals[d.faces].sum(axis=1))[real] > 0.0
        # measured: 97.5 % (Christie slim) to 100 %; an inside-out mesh scores under 3 %.
        # Not 100: a skinned normal at a joint can lean past its own face.
        assert agree.mean() > 0.95, (
            f"{d.name}: only {agree.mean():.1%} of the faces point along their normals")

    if not model.first_person:
        shadow = model.drawables["s_body"]
        volume = _signed_volume(shadow.verts, shadow.faces)
        assert volume > 50_000.0, f"s_body encloses {volume:.0f} cm3"   # 72,179 to 189,919
        if pack == "Miranda_LAS":
            source = _source(False)
            faces = np.array([i for mesh in source.meshes for i in mesh.triangle_indices]).reshape(-1, 3)
            as_source_winds = _signed_volume(np.array([v.pos for v in source.vertices]), faces)
            assert as_source_winds < 0.0 < volume, (as_source_winds, volume)   # -3,021 in3


@each_model
def test_skin_has_three_weights_and_a_root_first_palette(pack, stem):
    """**Skin.** Three weights per vertex that sum to 1, indices local to the palette, root first.

    The vertex format of the 2B templates holds three weights and four index slots:
    the build fills three and leaves the fourth index at 0. An index counts into the
    drawable's own palette, not into the skeleton, so it is below the palette's
    length. The palette keeps the order of the 2B `g_body` palette, root first: a
    parent comes before its children, which puts `Hips` at 0 in every drawable that
    uses it (Miranda's head and her first-person arms do not).
    """
    model = _model(pack, stem)
    assert model.skinned(), "no skinned drawable"
    for d in model.skinned():
        assert d.weights.shape == (len(d.verts), 3)
        assert d.weights.min() >= 0.0
        total = d.weights.sum(axis=1)
        assert np.abs(total - 1.0).max() < 1e-4, f"{d.name}: weights sum to {total.min():.4f}"
        assert not d.indices[:, 3].any(), f"{d.name}: the fourth index slot is in use"
        used = d.indices[:, :3][d.weights > 0.0]
        assert used.max() < len(d.palette), (
            f"{d.name}: index {used.max()} in a palette of {len(d.palette)}")
        for row, weights in zip(d.indices[:, :3].tolist(), d.weights.tolist()):
            live = [i for i, w in zip(row, weights) if w > 1e-6]
            assert len(live) == len(set(live)), f"{d.name}: a bone twice on one vertex: {row}"

        assert len(set(d.palette)) == len(d.palette), f"{d.name}: a bone twice in the palette"
        place = {bone: i for i, bone in enumerate(d.palette)}
        late = [bone for bone in d.palette
                if model.parent.get(bone) in place and place[model.parent[bone]] > place[bone]]
        assert not late, f"{d.name}: listed before their parent: {late}"
        if "Hips" in place:
            assert place["Hips"] == 0, f"{d.name}: Hips is entry {place['Hips']}"
    if not model.first_person:
        for name in ("g_body", "s_body"):
            assert model.drawables[name].palette[0] == "Hips", name


@each_model
def test_atoms_index_global_vertices_inside_their_own_block(pack, stem):
    """**Atoms.** A render atom is a range, and its triangle indices are global.

    `base_vertex` and `slice_len` select a block of the drawable's vertices,
    `base_index` and `tri_count` a run of its triangles, `material_id` what they are
    drawn with. An index counts from the start of the vertex array, never from the
    start of the block. The atoms tile both arrays with nothing shared and nothing
    left over, and in the tracked packs every triangle stays inside its own atom's
    block. (The builder's gate, `build_models.atom_problems`, is looser by one case:
    it refuses only a triangle that lies wholly beyond its own block.)

    A wrong offset keeps the file valid and draws some other part of the mesh with
    this atom's material; local indices would put every later atom's triangles into
    the first block. Neither shows in a preview that reads the mesh directly.
    """
    model = _model(pack, stem)
    for d in model.drawables.values():
        assert d.atoms, f"{d.name}: no render atom"
        next_vertex = next_triangle = 0
        for number, atom in enumerate(d.atoms):
            assert atom["base_vertex"] == next_vertex, (
                f"{d.name}: atom {number} does not follow the vertex block ending at {next_vertex}")
            assert atom["base_index"] == 3 * next_triangle, (
                f"{d.name}: atom {number} draws from triangle {atom['base_index'] / 3:g}, "
                f"not {next_triangle}")
            block_end = atom["base_vertex"] + atom["slice_len"]
            drawn = d.faces[next_triangle:next_triangle + atom["tri_count"]]
            assert len(drawn) == atom["tri_count"], f"{d.name}: atom {number} runs past the triangles"
            outside = int(((drawn < atom["base_vertex"]) | (drawn >= block_end)).any(axis=1).sum())
            assert outside == 0, (
                f"{d.name}: atom {number} draws {outside} triangles with a corner outside "
                f"its vertex block {atom['base_vertex']}..{block_end - 1}")
            next_vertex, next_triangle = block_end, next_triangle + atom["tri_count"]
        assert next_vertex == len(d.verts), f"{d.name}: the atoms cover {next_vertex} of {len(d.verts)} vertices"
        assert next_triangle == len(d.faces), f"{d.name}: the atoms draw {next_triangle} of {len(d.faces)} triangles"
    # the case the rule exists for: several atoms in one drawable
    if not model.first_person or pack.startswith("Christie"):
        assert max(len(d.atoms) for d in model.drawables.values()) > 1


@each_model
def test_materials_are_the_ones_the_material_config_declares(pack, stem):
    """**Materials.** A drawable's materials are found in the unit's `.material_config` by name hash.

    The model stores only the 64-bit hash of a material's name; the name itself, with
    its shader and textures, is in the config, so the two files have to agree on the
    hash. What the config says about a material that is drawn follows the LAS outfit
    guide: in third person a skin material (one with a normal map) is `unique` and
    has `CONTOUR` with its two variables; in first person it has `DEPTH_SCALING` and
    no contour. Shadow meshes use `shadow_caster`.

    The `c_block` box that the first-person template brings along keeps the
    template's own material, which the config does not declare, exactly as in the
    2B pack.
    """
    model = _model(pack, stem)
    declared = _declared_materials(pack, stem)
    named = {dm.hash64(name): name for name in declared}
    assert declared["shadow_caster"]["template"][0] == "shadow_caster_only"
    drawn = set()
    checked = 0
    for d in model.drawables.values():
        if not d.name.startswith(("g_", "s_")):
            assert d.name == "c_block", f"an unexpected drawable: {d.name}"
            continue
        for atom in d.atoms:
            assert atom["material_id"] < len(d.materials), f"{d.name}: atom without a material"
        unknown = [f"{h:016x}" for h in d.materials if h not in named]
        assert not unknown, f"{d.name}: materials the config does not declare: {unknown}"
        if d.name.startswith("s_"):
            assert [named[h] for h in d.materials] == ["shadow_caster"], d.name
        else:
            drawn |= {named[h] for h in d.materials}
        checked += 1
    assert checked >= 3, "the model has no body, lod and shadow drawable"

    assert drawn and "shadow_caster" not in drawn, sorted(drawn)
    for name in sorted(drawn):
        material = declared[name]
        assert material["template"][0] == "generic" and "DIFFUSE_TEXTURE" in material["template"], name
        assert "diffuse_texture" in material["textures"], f"{name}: no diffuse texture"
        if model.first_person:
            assert "DEPTH_SCALING" in material["template"], f"{name}: first person without DEPTH_SCALING"
            assert "CONTOUR" not in material["template"], f"{name}: a contour in first person"
        elif "bump_normal_texture" in material["textures"]:
            assert "CONTOUR" in material["template"], f"{name}: a skin material without CONTOUR"
            assert material["unique"], f'{name}: a skin material without unique="true"'
            assert {"contour_color", "contour_opacity"} <= material["variables"], (
                f"{name}: the contour variables are missing")
        else:
            # Miranda's eyes: diffuse only, the plain template
            assert "CONTOUR" not in material["template"], name


@each_model
def test_objects_listed_by_the_unit_are_the_ones_the_model_has(pack, stem):
    """**Objects.** A unit's `.object` file lists the drawables its model has.

    The `.unit` names the `.object`; the `.object` names the material config and,
    in its one graphic group, every object to show or to hide. The model stores
    those names as hashes, so a line with no object behind it is found here or in
    the game. The Miranda builders write the file from the model they built
    (`las_pack.install_models`); this test is what holds for the bytes that are
    tracked.

    1. `.unit` and `.object` name the unit's own path, and the orientation object
       is a node of the model;
    2. the `<object>` lines are the model's `g_` drawables, no more and no fewer;
    3. the body is switched on, and in third person the head when the pack ships
       one; the LODs and a first-person head are off, as in the 2B units;
    4. the culling object is `c_block`. The first-person model has it and the
       third-person model does not, which is the 2B layout too: `2b.object` names
       it and `2b.model` has none. So a culling object that is not there is the
       template's own layout, which an `<object>` line with no object is not.
    """
    z, unit, item = _zip(pack), _unit_dir(pack), ITEMS[pack]
    path = f"units/{item}/skins/{item}/{stem}"
    model = _model(pack, stem)
    assert re.findall(r'<object file="([^"]*)"', z.read(f"{unit}/{stem}.unit").decode()) == [path], (
        f"{stem}.unit does not name its own .object")
    text = z.read(f"{unit}/{stem}.object").decode()
    assert re.findall(r'<diesel materials="([^"]*)" orientation_object="([^"]*)"', text) == [
        (path, "root_point")], f"{stem}.object does not name its own material config and root_point"
    assert "root_point" in model.joints, f"{stem}.model has no root_point"

    groups = re.findall(r"<graphic_group\b([^>]*)>", text)
    assert len(groups) == 1 and 'culling_object="c_block"' in groups[0], (
        f"{stem}.object: not one graphic group culled by c_block")
    assert ("c_block" in model.joints) == model.first_person, (
        f"{stem}.model: c_block belongs to the first-person model, and only to it")

    lines = re.findall(r'<object name="([^"]*)" enabled="(true|false)" />', text)
    listed = dict(lines)
    assert len(lines) == text.count("<object ") and len(listed) == len(lines), (
        f"{stem}.object: a line that is not `name` + `enabled`, or a name listed twice")
    drawn = {name for name in model.drawables if name.startswith("g_")}
    assert drawn <= set(listed), (
        f"{stem}.object does not list {sorted(drawn - set(listed))}, which the model has")
    assert set(listed) <= drawn, (
        f"{stem}.object lists {sorted(set(listed) - drawn)} and the model has no drawable of "
        f"that name: write the file from the model (`las_pack.install_models`)")

    on = {name for name, enabled in listed.items() if enabled == "true"}
    head = set() if model.first_person else {"g_head"} & drawn
    assert on == {"g_body"} | head, (
        f"{stem}.object switches on {sorted(on)}, expected {sorted({'g_body'} | head)}")


@each_pack
def test_textures_keep_gloss_low_and_normals_in_the_diesel_layout(pack):
    """**Textures.** Diffuse alpha is gloss and stays low; a normal map has X in alpha and Y in green.

    Every texture of a unit is a DXT5 DDS with the full mip pyramid down to 1x1, in
    the header shape of the game's own files. Its payload is exactly the chain the
    header declares, with the colour endpoints of every block in the order c0 >= c1
    (the other order is DXT1's transparent mode, which some decoders apply to DXT5
    too and draw as holes). A converted texture brings the source's pyramid; the
    repainted face keeps it and gets the repaint in every level
    (`build_las.repainted_face_texture`); the eyes are drawn, and their levels
    are made with them (`build_las.eye_texture`). How close each of those levels
    is to the picture it stands for is `tests/test_mip_audit.py`. The menu icon is
    not a unit texture and has one level, like 2B's.

    The skin shader reads the alpha of the diffuse texture as gloss. Source leaves
    that channel at 255; the build attenuates it, and it has to stay low on every
    level, or the skin turns shiny with distance. A normal map keeps two channels,
    X in alpha and Y in green (Source's green, inverted); the build writes 255 into
    red and 0 into blue, which the shader does not read. A map that still has X in
    red is the Source layout, unconverted.
    """
    z, unit, item = _zip(pack), _unit_dir(pack), ITEMS[pack]
    roles = {name[len(unit) + len(item) + 2:-len(".texture")]: name
             for name in z.namelist() if name.startswith(f"{unit}/") and name.endswith(".texture")}
    normal = {role for role in roles if role.endswith("_nm")}
    diffuse = set(roles) - normal
    assert normal and {role[:-3] + "_df" for role in normal} <= diffuse, sorted(roles)

    for role, name in sorted(roles.items()):
        texture = _texture(z.read(name))
        width, height = texture.size
        assert width == height and len(texture.levels) == width.bit_length(), (
            f"{role}: {len(texture.levels)} mip levels for {width}x{height}, "
            f"the full pyramid has {max(width, height).bit_length()}")
        # CAPS | HEIGHT | WIDTH | PIXELFORMAT | MIPMAPCOUNT | LINEARSIZE; TEXTURE | COMPLEX | MIPMAP
        assert (texture.flags, texture.caps) == (0x000A1007, 0x00401008), (
            f"{role}: header flags {texture.flags:#x}, caps {texture.caps:#x}")
        c0, c1 = texture.endpoints()
        assert not (c0 < c1).any(), f"{role}: {int((c0 < c1).sum())} blocks with c0 < c1"

        alpha = texture.alpha()
        if role in diffuse:
            # measured, over all levels: mean 3.5 to 29.5 of 255; at most 0.77 % of
            # a level above 128
            for level in range(len(texture.levels)):
                gloss = texture.alpha(level)
                assert gloss.mean() < 40.0, f"{role}, level {level}: mean gloss {gloss.mean():.1f} of 255"
                assert (gloss > 128).mean() < 0.02, (
                    f"{role}, level {level}: {(gloss > 128).mean():.1%} of it above half gloss")
        else:
            red = np.concatenate([c0 >> 11, c1 >> 11])
            blue = np.concatenate([c0 & 31, c1 & 31])
            assert (red == 31).all() and (blue == 0).all(), (
                f"{role}: red and blue are not the constant 255 and 0 of a converted normal map")
            green = (c0 >> 5) & 63
            # measured: X spans at least 140 of 255 (alpha), Y at least 22 of 63 (green endpoints)
            assert int(alpha.max()) - int(alpha.min()) > 100, f"{role}: no X in alpha"
            assert int(green.max()) - int(green.min()) > 15, f"{role}: no Y in green"


def _codec_cases() -> list:
    cases = [pytest.param(("pack", pack, stem), id=f"{pack}/{stem}")
             for pack in PACKS for stem in _stems(pack)]
    cases += [pytest.param(("template", name, None), id=f"2B/{name}",
                           marks=pytest.mark.skipif(not TEMPLATES.exists(), reason=MISSING))
              for name in ("2b.model", "fps_2b.model")]
    return cases


@pytest.mark.parametrize("case", _codec_cases())
def test_codec_round_trips_byte_for_byte(case):
    """**Codec.** `ModelFile.read` then `write` returns the bytes it was given.

    On the 2B templates, which is what makes it safe to build on them, and on every
    model in the tracked packs. Each decoder is also re-encoded section by section:
    a field the codec drops would otherwise only show once something edits it.
    """
    kind, name, stem = case
    data = (TEMPLATES / name).read_bytes() if kind == "template" else _model(name, stem).data
    mf = dm.ModelFile.read(data)
    assert mf.write() == data

    codecs = {
        dm.GEOMETRY: (dm.decode_geometry, dm.encode_geometry),
        dm.TOPOLOGY: (dm.decode_topology, dm.encode_topology),
        dm.SKINBONES: (dm.decode_skinbones, dm.encode_skinbones),
        dm.MATERIAL: (dm.decode_material, dm.encode_material),
        dm.MATERIAL_GROUP: (dm.decode_material_group, dm.encode_material_group),
        dm.PASSTHROUGH_GP: (dm.decode_passthroughgp, dm.encode_passthroughgp),
        dm.TOPOLOGY_IP: (dm.decode_topologyip, dm.encode_topologyip),
        dm.CUSTOM_HASHLIST: (dm.decode_custom_hashlist, dm.encode_custom_hashlist),
    }
    seen = Counter()
    for section in mf.sections:
        if section.type in codecs:
            decode, encode = codecs[section.type]
            assert encode(decode(section.payload)) == section.payload, (
                f"section {section.id} ({dm.TAG_NAMES.get(section.type, section.type)})")
            seen[section.type] += 1
    assert seen[dm.GEOMETRY] and seen[dm.TOPOLOGY] and seen[dm.SKINBONES]


@each_pack
def test_registration_follows_the_2b_contract(pack):
    """**Registration.** The pack registers itself the way the 2B reference pack does.

    A BeardLib `main.xml` with `Localization`, `Hooks` and `AddFiles`; one hook on
    `lib/tweak_data/armorskinstweakdata` that creates `LegendaryArmours.<id>` with the
    two units and the flags; every texture and unit file of the pack listed under
    `AddFiles`, and nothing listed that the pack lacks; the three menu strings. The
    `Hooks` element names the folder the hooks are really in: the 2B pack itself
    says `Hooks` where its folder is `hooks`, which is one of the defects not to
    copy. `BUILD_INFO.json` says the same as the files.
    """
    # the tracked LAS packs in dist/ (the two Christie packs are tracked but their builder
    # is deleted; they are still verified here, from the tracked bytes)
    las = {"Miranda_LAS", "Miranda_Busty_LAS", "Christie_LAS", "Christie_LAS_Slim"}
    assert set(ITEMS) == las, "this file no longer covers every tracked LAS pack"
    z = _zip(pack)
    files = {n[len(pack) + 1:] for n in z.namelist() if not n.endswith("/")}
    info = _info(pack)
    item, registration = info["item_id"], info["registration"]
    assert item == ITEMS[pack], f"BUILD_INFO.json says the item is {item}"
    main = z.read(f"{pack}/main.xml").decode()

    for element in ("<Localization", "<Hooks", "<AddFiles"):
        assert element in main, f"main.xml has no {element}>"
    hooks_dir = re.search(r'<Hooks\b[^>]*\bdirectory="([^"]*)"', main).group(1)
    hooks = dict(re.findall(r'<hook file="([^"]+)" source_file="([^"]+)"', main))
    for name in hooks:
        assert f"{hooks_dir}/{name}" in files, f"main.xml hooks {name}, which is not in the pack"
    on_armor_skins = [name for name, source in hooks.items()
                      if source == "lib/tweak_data/armorskinstweakdata"]
    assert len(on_armor_skins) == 1, hooks
    assert registration["hook_source"] == "lib/tweak_data/armorskinstweakdata"

    lua = z.read(f"{pack}/{hooks_dir}/{on_armor_skins[0]}").decode()
    assert re.search(r"^LegendaryArmours = LegendaryArmours or \{\}$", lua, flags=re.M)
    assert re.search(r"^la = LegendaryArmours$", lua, flags=re.M)
    assert re.search(rf"^la\.{re.escape(item)} = \{{$", lua, flags=re.M), (
        f"the hook does not create LegendaryArmours.{item}")
    assert registration["table"] == f"LegendaryArmours.{item}"
    fields = dict(re.findall(r'^\s*(\w+) = ("[^"]*"|true|false),?$', lua, flags=re.M))
    assert fields["category"] == f'"{item}"'
    for key in ("unit", "fps_unit"):
        assert fields[key] == f'"{registration[key]}"', key
        assert f"assets/{registration[key]}.unit" in files, f"{key} names no unit in the pack"
    assert registration["flags"], "no flags recorded"
    for flag in registration["flags"]:
        assert fields.get(flag) == "true", f"{flag} is not switched on in the hook"
    assert {"hide_mask", "hide_armor", "fps_hide_armor", "fps_replace_body"} <= set(registration["flags"])
    # a full outfit replaces everything; a body-only one leaves the heister's head
    assert len({"replace_all", "replace_body"} & set(registration["flags"])) == 1

    add_dir = re.search(r'<AddFiles\b[^>]*\bdirectory="([^"]*)"', main).group(1)
    listed = set()
    for kind, path in re.findall(r'<(texture|df_nm|unit_mat) path="([^"]+)"', main):
        endings = {"texture": (".texture",), "df_nm": ("_df.texture", "_nm.texture"),
                   "unit_mat": (".unit", ".material_config", ".object", ".model")}[kind]
        listed |= {f"{add_dir}/{path}{ending}" for ending in endings}
    shipped = {name for name in files if name.startswith(f"{add_dir}/")}
    assert listed - shipped == set(), f"AddFiles lists files the pack lacks: {sorted(listed - shipped)}"
    assert shipped - listed == set(), f"files AddFiles does not list: {sorted(shipped - listed)}"
    icon = re.search(r'<table\b[^>]*\bimage="([^"]+)"', main).group(1)
    assert f"{add_dir}/{icon}.texture" in files, "the menu icon is not in the pack"

    localization = re.search(r'<Localization\b[^>]*directory="([^"]*)"[^>]*default="([^"]*)"', main)
    strings = json.loads(z.read(f"{pack}/{localization.group(1)}/{localization.group(2)}"))
    for key in (f"bm_menu_{item}_armor_skins", f"bm_askn_{item}", f"bm_askn_{item}_desc"):
        assert strings.get(key), f"no menu string {key}"


@each_pack
def test_tracked_bytes_match_their_sidecar_and_build_info(pack):
    """**Tracked bytes.** A zip equals its `.sha256` sidecar, and `BUILD_INFO.json` hashes the payload.

    The packs are in git so that they can be installed straight from the repository,
    which makes the bytes the product. The sidecar pins the archive; `BUILD_INFO.json`
    inside it pins every file, with nothing missing and nothing extra; the entries
    carry one fixed timestamp, which is what lets a rebuild reproduce the archive.
    Where a staged copy is tracked under `build/pd2-las/`, it is the same archive.
    """
    path = REPO / "dist" / f"{pack}.zip"
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    assert sidecar.is_file(), f"{sidecar.relative_to(REPO)}: {RESTORE}"
    assert sidecar.read_text().split()[0] == digest, "the zip is not the one its sidecar names"

    z = _zip(pack)
    entries = [i for i in z.infolist() if not i.is_dir()]
    assert {i.filename.split("/")[0] for i in entries} == {pack}, "one top-level folder, the pack"
    assert {i.date_time for i in entries} == {(2020, 1, 1, 0, 0, 0)}, "a timestamp that is not fixed"

    info = _info(pack)
    assert info["models_present"] is True
    payload = info["payload_sha256"]
    shipped = {i.filename[len(pack) + 1:] for i in entries} - {"BUILD_INFO.json"}
    assert set(payload) == shipped, (sorted(set(payload) ^ shipped))
    assert "WIP_DO_NOT_INSTALL.txt" not in shipped
    for name, expected in payload.items():
        assert hashlib.sha256(z.read(f"{pack}/{name}")).hexdigest() == expected, name

    staged = REPO / "build" / "pd2-las" / f"{pack}.zip"
    if pack.startswith("Miranda"):       # the two packs that are also tracked there
        assert staged.is_file(), f"{staged.relative_to(REPO)}: {RESTORE}"
        assert staged.read_bytes() == raw, "the staged copy differs from dist/"
        assert staged.with_name(staged.name + ".sha256").read_text().split()[0] == digest


def test_variants_change_only_what_they_claim():
    """**Variants.** The busty pack is the base pack plus the chest, and nothing else.

    The same head and the same first-person arms, value for value; the same
    textures, byte for byte; the same unit files but for the pack's own name; and a
    body that differs from the base body only inside the region `bust_variant`
    declares for the chest. The variant has its own menu icon, so the two can be
    told apart in the outfit grid.

    The first-person model is not the same file. The base model carries `g_head`
    and `g_head_lod1` as disabled copies of the arms; the variant's has neither,
    and so its `.object` is the base file without the lines of those two.
    """
    base, busty = "Miranda_LAS", "Miranda_Busty_LAS"
    base_id, busty_id = ITEMS[base], ITEMS[busty]

    def same(a: Drawable, b: Drawable) -> bool:
        return (np.array_equal(a.verts, b.verts) and np.array_equal(a.normals, b.normals)
                and a.uvs == b.uvs and np.array_equal(a.faces, b.faces)
                and np.array_equal(a.weights, b.weights) and np.array_equal(a.indices, b.indices)
                and a.palette == b.palette)

    theirs, ours = _model(base, base_id), _model(busty, busty_id)
    for name in ("g_head", "g_head_lod1"):
        assert same(theirs.drawables[name], ours.drawables[name]), f"the head changed ({name})"
    arms_base, arms = _model(base, f"fps_{base_id}"), _model(busty, f"fps_{busty_id}")
    head_slots = {"g_head", "g_head_lod1"}
    assert set(arms_base.drawables) - set(arms.drawables) == head_slots
    assert set(arms.drawables) <= set(arms_base.drawables)
    for name, d in arms.drawables.items():
        assert same(arms_base.drawables[name], d), f"the first-person arms changed ({name})"

    def key(p):
        return (round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[2]), 4))

    for name in ("g_body", "s_body"):
        before = Counter(map(key, theirs.drawables[name].verts))
        after = Counter(map(key, ours.drawables[name].verts))
        changed = np.array(list((before - after).elements()) + list((after - before).elements()))
        # measured on g_body: 257 base vertices gone and 3,549 new, all within
        # |x| 13.4, y 6.5 to 23.2 and z 132.6 to 151.0
        assert len(changed) > 1000, f"{name}: the variant changed almost nothing"
        assert np.abs(changed[:, 0]).max() <= bust_variant.X_ZERO + 1e-3, f"{name}: changed beside the chest"
        assert bust_variant.BAND_LO <= changed[:, 2].min(), f"{name}: changed below the chest"
        assert changed[:, 2].max() <= bust_variant.BAND_HI, f"{name}: changed above the chest"
        assert changed[:, 1].min() > bust_variant.GATE_LO, f"{name}: changed behind the chest"

    def chest_front(model: Model) -> float:
        v = model.drawables["g_body"].verts
        inside = ((np.abs(v[:, 0]) < bust_variant.X_ZERO)
                  & (v[:, 2] > bust_variant.BAND_LO) & (v[:, 2] < bust_variant.BAND_HI))
        return float(v[inside, 1].max())

    # measured: 19.98 cm in the base pack, 23.21 cm in the variant
    assert chest_front(ours) > chest_front(theirs) + 2.0, (chest_front(ours), chest_front(theirs))

    z_base, z_busty = _zip(base), _zip(busty)
    base_dir, busty_dir = _unit_dir(base), _unit_dir(busty)
    textures = [n[len(base_dir) + 1:] for n in z_base.namelist()
                if n.startswith(base_dir + "/") and n.endswith(".texture")]
    assert len(textures) == 7
    for name in textures:
        twin = f"{busty_dir}/{name.replace(base_id, busty_id, 1)}"
        assert z_busty.read(twin) == z_base.read(f"{base_dir}/{name}"), f"{name}: a texture changed"
    for stem in ("", "fps_"):
        for ending in (".unit", ".object", ".material_config"):
            text = z_base.read(f"{base_dir}/{stem}{base_id}{ending}").decode()
            twin = z_busty.read(f"{busty_dir}/{stem}{busty_id}{ending}").decode()
            if (stem, ending) == ("fps_", ".object"):
                lines = text.splitlines(keepends=True)
                kept = [line for line in lines
                        if not any(f'<object name="{slot}"' in line for slot in head_slots)]
                assert len(kept) == len(lines) - len(head_slots), (
                    f"fps_{base_id}.object has no line for each of {sorted(head_slots)}")
                text = "".join(kept)
            assert twin == text.replace(base_id, busty_id), f"{stem}{busty_id}{ending} differs"

    def icon(pack, item):
        return _zip(pack).read(f"{pack}/assets/guis/dlcs/{item}/armor_skins/{item}.texture")

    assert icon(base, base_id) != icon(busty, busty_id), "the variant has the base pack's icon"
