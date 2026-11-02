"""Minimal, dependency-free reader for Skyrim SE / AE NIF files (20.2.0.7).

Why this exists: the outfit we want to port (Melodic "Business Woman", 3BA) is a
set of ``.nif`` meshes authored for Skyrim. Nothing in the repo could read that
format, so this module implements just the parts needed to *inspect* a mesh:
block table, node hierarchy, ``BSTriShape`` vertex/triangle payloads, skinning
(``BSDismemberSkinInstance`` -> ``NiSkinData``), and ``BSLightingShaderProperty``
-> ``BSShaderTextureSet`` material names.

Field order follows nifly (github.com/ousnius/nifly), which is the reference
implementation used by the Skyrim modding toolchain. Blocks we do not model are
skipped using the per-block size table, so unknown types are not fatal.

Geometry comes back in file units (a Skyrim unit is 1.428 cm; an adult NPC is
~128 units tall) in Skyrim's right-handed, Z-up world space - the same axes as
Blender's default. Vertices are bind-pose: the mesh is authored on a reference
skeleton, and the per-vertex bone weights say which bones move it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# block types we understand
# ---------------------------------------------------------------------------
NODE_TYPES = {"NiNode", "BSFadeNode", "NiBSParticleNode", "RootCollisionNode", "BSTreeNode"}
SHAPE_TYPES = {"BSTriShape", "BSSubIndexTriShape"}
# Legacy geometry: the `_g` (ground collision) NIFs use NiTriShape + NiTriShapeData
# blocks instead of BSTriShape. They carry no skin, but they are the meshes the
# game plants on the floor, so a port may want their bounds.
LEGACY_SHAPE_TYPES = {"NiTriShape", "NiTriStrips"}
SKIN_TYPES = {"BSDismemberSkinInstance", "NiSkinInstance", "BSSkin::Instance"}

# dismember / body-part ids (Skyrim BSDismemberSkinInstance partID)
BODY_PARTS = {
    0: "Torso", 1: "Head", 2: "Head2", 3: "LeftArm", 4: "LeftArm2",
    5: "RightArm", 6: "RightArm2", 7: "LeftLeg", 8: "LeftLeg2",
    9: "RightLeg", 10: "RightLeg2", 11: "Tail", 12: "Shield",
    13: "Pelvis2", 14: "Pelvis", 15: "Unknown15", 16: "Unknown16",
    17: "Unknown17", 18: "Unknown18", 19: "Unknown19", 20: "Unknown20",
    21: "Unknown21", 22: "Unknown22", 23: "Unknown23", 24: "Unknown24",
    25: "Unknown25", 26: "Unknown26", 27: "Unknown27", 28: "Unknown28",
    29: "Unknown29", 30: "Weapon", 31: "Weapon2", 32: "Quiver",
    33: "Unknown33", 34: "Unknown34", 35: "Unknown35", 36: "Unknown36",
    37: "Unknown37", 38: "Unknown38", 39: "Unknown39", 40: "Unknown40",
    41: "Unknown41", 42: "Unknown42", 43: "Unknown43", 44: "Unknown44",
    45: "Unknown45", 46: "Unknown46", 47: "Unknown47", 48: "Unknown48",
    49: "Unknown49", 50: "Unknown50", 51: "Unknown51", 52: "Unknown52",
    53: "Unknown53", 54: "Unknown54", 55: "Unknown55", 56: "Unknown56",
    57: "Unknown57", 58: "Unknown58", 59: "Unknown59", 60: "Unknown60",
    61: "Shield2", 62: "Unknown62",
}


class NifError(Exception):
    pass


class Reader:
    """Little-endian binary reader with a position, and bounds checks."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def _take(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.data):
            raise NifError(f"read past EOF at {self.pos} (+{n}, file {len(self.data)})")
        chunk = self.data[self.pos:end]
        self.pos = end
        return chunk

    def u8(self) -> int:
        return self._take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self._take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self._take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def f16(self) -> float:
        return float(struct.unpack("<e", self._take(2))[0])

    def f16s(self, n: int) -> np.ndarray:
        return np.frombuffer(self._take(2 * n), dtype="<f2").astype(np.float32)

    def vec3(self) -> tuple[float, float, float]:
        return struct.unpack("<3f", self._take(12))

    def string(self, size: int = 4) -> str:
        n = {1: self.u8, 2: self.u16, 4: self.u32}[size]()
        if n == 0:
            return ""
        raw = self._take(n)
        return raw.rstrip(b"\x00").decode("cp1252", "replace")

    def bool8(self) -> bool:
        return self.u8() != 0

    def strings(self, size: int = 4, count_size: int = 4) -> list[str]:
        n = self.u32() if count_size == 4 else self.u16()
        return [self.string(size) for _ in range(n)]


@dataclass
class Transform:
    """NIF MatTransform: translation, 3x3 rotation (row-major, 9 floats), scale."""

    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    scale: float = 1.0

    def matrix(self) -> np.ndarray:
        m = np.eye(4)
        m[:3, :3] = np.asarray(self.rotation, dtype=np.float64).reshape(3, 3) * self.scale
        m[:3, 3] = self.translation
        return m


@dataclass
class Shape:
    index: int
    name: str
    vertices: np.ndarray            # (n, 3) float32, file units, bind pose
    normals: np.ndarray             # (n, 3) float32
    uvs: np.ndarray                 # (n, 2) float32
    colors: np.ndarray | None       # (n, 4) uint8 or None
    weights: np.ndarray | None      # (n, 4) float32 or None
    bone_indices: np.ndarray | None  # (n, 4) uint8 or None
    triangles: np.ndarray           # (t, 3) int32
    shader_type: int | None
    alpha_flags: int | None
    alpha_threshold: int | None
    textures: list[str]
    bones: list[str]                 # skin instance bone list
    body_parts: list[int]            # BSDismemberSkinInstance partIDs
    transform: Transform
    flags: int

    # ---- derived -------------------------------------------------------
    @property
    def num_vertices(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def num_triangles(self) -> int:
        return int(self.triangles.shape[0])

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        if self.num_vertices == 0:
            return np.zeros(3), np.zeros(3)
        return self.vertices.min(axis=0), self.vertices.max(axis=0)

    def bone_weights(self) -> dict[str, float]:
        """Total vertex weight per bone name (for "who drives this mesh")."""
        if self.weights is None or self.bone_indices is None:
            return {}
        out: dict[str, float] = {}
        for slot in range(4):
            w = self.weights[:, slot].astype(np.float64)
            idx = self.bone_indices[:, slot]
            for bone_id in np.unique(idx):
                if bone_id >= len(self.bones):
                    continue
                total = float(w[idx == bone_id].sum())
                if total > 1e-6:
                    out[self.bones[bone_id]] = out.get(self.bones[bone_id], 0.0) + total
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


@dataclass
class Node:
    index: int
    name: str
    transform: Transform
    children: list[int] = field(default_factory=list)
    parent: int | None = None

    def world_matrix(self, nodes: dict[int, "Node"]) -> np.ndarray:
        m = self.transform.matrix()
        p = self.parent
        while p is not None:
            m = nodes[p].transform.matrix() @ m
            p = nodes[p].parent
        return m


@dataclass
class NifFile:
    path: str
    version: str
    user_version: int
    stream_version: int
    creator: str
    block_types: list[str]
    nodes: dict[int, Node]
    shapes: list[Shape]
    extra_data: dict[str, str]       # type -> short description, per file
    collision_blocks: list[str]
    roots: list[int]
    warnings: list[str]
    parents: dict[int, int] = field(default_factory=dict)  # child block -> node

    def shape_world_matrix(self, shape: "Shape") -> np.ndarray:
        """Parent-node world transform composed with the shape's own transform."""
        parent = self.parents.get(shape.index)
        if parent is None or parent not in self.nodes:
            return shape.transform.matrix()
        return self.nodes[parent].world_matrix(self.nodes) @ shape.transform.matrix()

    def node_names(self) -> list[str]:
        return [n.name for n in self.nodes.values()]

    def bones(self) -> list[str]:
        seen: list[str] = []
        for s in self.shapes:
            for b in s.bones:
                if b not in seen:
                    seen.append(b)
        return seen

    def shade(self) -> str:
        """Bottom line for a porter: is the file a skinned mesh or a prop?"""
        if not self.shapes:
            return "no geometry"
        if all(s.weights is None for s in self.shapes):
            return "static mesh (no skinning)"
        return "skinned mesh"


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def _read_header(r: Reader) -> dict:
    line = bytearray()
    while True:
        b = r._take(1)[0]
        if b == 0x0A:
            break
        line.append(b)
    text = line.decode("cp1252", "replace")
    if "NetImmerse" not in text and "Gamebryo" not in text:
        raise NifError(f"not a NIF (header {text!r})")
    if "Version" not in text:
        raise NifError("NIF header without version string")
    version = text.split("Version", 1)[1].strip()
    r.u32()  # file version (repeats the version string)
    r.u8()   # endian flag
    user_version = r.u32()
    num_blocks = r.u32()
    stream_version = r.u32()          # Bethesda stream version (100 = SSE)
    creator = r.string(1)
    r.string(1)                       # export info 1
    r.string(1)                       # export info 2
    if stream_version == 130:
        r.string(1)

    num_types = r.u16()
    types = [r.string(4) for _ in range(num_types)]
    type_indices = [r.u16() for _ in range(num_blocks)]
    sizes = [r.u32() for _ in range(num_blocks)]
    num_strings = r.u32()
    r.u32()                           # max string length
    strings = [r.string(4) for _ in range(num_strings)]
    num_groups = r.u32()
    for _ in range(num_groups):
        r.u32()
    return dict(
        version=version,
        user_version=user_version,
        stream_version=stream_version,
        creator=creator,
        types=types,
        type_indices=type_indices,
        sizes=sizes,
        strings=strings,
        num_blocks=num_blocks,
    )


class _Ctx:
    def __init__(self, header: dict):
        self.header = header
        self.strings: list[str] = header["strings"]

    def s(self, idx: int) -> str:
        if idx == 0xFFFFFFFF or idx >= len(self.strings):
            return ""
        return self.strings[idx]


def _read_net_object(r: Reader, ctx: _Ctx) -> tuple[str, list[int], int | None]:
    """NiObjectNET: name, extra-data refs, controller ref."""
    name = ctx.s(r.u32())
    n_extra = r.u32()
    extras = [r.u32() for _ in range(n_extra)]
    controller = r.u32()
    return name, extras, (None if controller == 0xFFFFFFFF else controller)


def _read_av_object(r: Reader, ctx: _Ctx) -> tuple[str, list[int], int | None, Transform, int, int]:
    name, extras, controller = _read_net_object(r, ctx)
    flags = r.u32()
    t = Transform(r.vec3(), tuple(r.f32() for _ in range(9)), r.f32())
    collision = r.u32()
    return name, extras, controller, t, flags, collision




def _read_legacy_shape(r: Reader, ctx: _Ctx, index: int, block_type: str) -> Shape:
    """NiTriShape (NiTriBasedGeom) + its NiTriShapeData payload.

    Layout verified against nifly's NiGeometry::Sync / NiGeometryData::Sync for
    file version 20.2.0.7 / stream 100.
    """
    name, extras, controller, t, flags, collision = _read_av_object(r, ctx)
    data_ref = r.u32()
    skin_ref = r.u32()
    num_materials = r.u32()                       # NiStringVector<NiFixedString>
    for _ in range(num_materials):
        r.string(4)
    if num_materials:
        for _ in range(num_materials):
            r.u32()                               # material extra data (i32 each)
    r.u32()                                       # active material index
    r.bool8()                                     # defaultMatNeedsUpdateFlag
    shader_ref = r.u32()
    alpha_ref = r.u32()
    r.u32()                                       # particleDataSize (stream 100)

    shape = Shape(
        index=index, name=name,
        vertices=np.zeros((0, 3), np.float32), normals=np.zeros((0, 3), np.float32),
        uvs=np.zeros((0, 2), np.float32), colors=None, weights=None, bone_indices=None,
        triangles=np.zeros((0, 3), np.int32),
        shader_type=None, alpha_flags=None, alpha_threshold=None,
        textures=[], bones=[], body_parts=[], transform=t, flags=flags,
    )
    shape._skin_ref = skin_ref
    shape._shader_ref = shader_ref
    shape._alpha_ref = alpha_ref
    shape._data_ref = data_ref
    return shape


def _read_geometry_data(r: Reader, ctx: _Ctx, block_type: str) -> dict:
    """NiTriShapeData (NiTriShapeData <- NiTriBasedGeomData <- NiGeometryData)."""
    stream_version = ctx.header["stream_version"]
    if block_type in ("NiTriShapeData", "NiTriStripsData"):
        r.u32()                                   # groupID (file >= 10.1.0.114)
    num_vertices = r.u16()
    r.u8()                                        # keep flags
    r.u8()                                        # compress flags
    verts = np.zeros((num_vertices, 3), np.float32)
    if r.bool8():                                 # hasVertices
        verts = np.frombuffer(r._take(12 * num_vertices), "<f4").reshape(-1, 3).copy()
    data_flags = r.u16()
    if stream_version > 34:
        r.u32()                                   # material CRC
    norms = np.zeros((num_vertices, 3), np.float32)
    if r.bool8():                                 # hasNormals
        norms = np.frombuffer(r._take(12 * num_vertices), "<f4").reshape(-1, 3).copy()
        nbt = data_flags & 0xF000
        if nbt:
            r._take(12 * num_vertices)            # tangents
            r._take(12 * num_vertices)            # bitangents
    r.vec3()                                      # bounds centre
    r.f32()                                       # bounds radius
    colors = None
    if r.bool8():                                 # hasVertexColors
        colors = np.frombuffer(r._take(4 * num_vertices), np.uint8).reshape(-1, 4).copy()
    num_uv_sets = data_flags & 1 if stream_version >= 34 else data_flags & 0x3F
    uvs = np.zeros((num_vertices, 2), np.float32)
    for i in range(num_uv_sets):
        block = np.frombuffer(r._take(8 * num_vertices), "<f4").reshape(-1, 2)
        if i == 0:
            uvs = block.copy()
    r.u16()                                       # consistency flags
    r.u32()                                       # additional data ref
    num_triangles = r.u16()                       # NiTriBasedGeomData
    tris = np.zeros((0, 3), np.int32)
    if block_type == "NiTriShapeData":
        r.u32()                                   # numTrianglePoints
        if r.bool8():                             # hasTriangles
            tris = np.frombuffer(r._take(6 * num_triangles), "<u2").reshape(-1, 3).astype(np.int32)
        num_groups = r.u16()
        for _ in range(num_groups):
            count = r.u16()
            r._take(2 * count)
    return {"vertices": verts, "normals": norms, "uvs": uvs, "colors": colors,
            "triangles": tris}


def _read_vertex_stream(r: Reader, desc: int, num_vertices: int, num_triangles: int,
                        stream_version: int):
    """Read one BSVertexData array + the triangle list that follows it.

    Layout (nifly BSTriShape::Sync / NiSkinPartition::Sync):
    position (16 B full precision) | UV half2 | normal bytes + bitangent Y |
    tangent bytes + bitangent Z | colour RGBA | weights half4 + bone idx ubyte4 |
    eye data | triangles (3 x uint16).
    """
    # Vertex flags live in bits 44-59; bits 2-43 hold the per-attribute offsets.
    flags = (desc >> 44) & 0xFFFFFF
    has_verts = bool(flags & 0x001)
    has_uvs = bool(flags & 0x002)
    has_normals = bool(flags & 0x008)
    has_tangents = bool(flags & 0x010)
    has_colors = bool(flags & 0x020)
    is_skinned = bool(flags & 0x040)
    has_eye = bool(flags & 0x100)
    vertex_main_size = ((desc & 0xFF00) >> 8) * 4

    verts = np.zeros((num_vertices, 3), np.float32)
    norms = np.zeros((num_vertices, 3), np.float32)
    uvs = np.zeros((num_vertices, 2), np.float32)
    colors = np.zeros((num_vertices, 4), np.uint8) if has_colors else None
    weights = np.zeros((num_vertices, 4), np.float32) if is_skinned else None
    bones = np.zeros((num_vertices, 4), np.uint8) if is_skinned else None

    for i in range(num_vertices):
        if has_verts:
            if vertex_main_size <= 16:
                verts[i] = struct.unpack("<3f", r._take(12))
                r.f32()                    # bitangent X
            else:
                verts[i] = struct.unpack("<3f", r._take(12))
                for _ in range((vertex_main_size - 16) // 4):
                    r.f32()
                r.f32()
        if has_uvs:
            uvs[i] = (r.f16(), r.f16())
        if has_normals:
            nx, ny, nz = r.u8(), r.u8(), r.u8()
            r.u8()                         # bitangent Y
            norms[i] = (nx / 127.5 - 1.0, ny / 127.5 - 1.0, nz / 127.5 - 1.0)
            if has_tangents:
                r._take(4)
        if has_colors:
            colors[i] = np.frombuffer(r._take(4), np.uint8)
        if is_skinned:
            weights[i] = r.f16s(4)
            bones[i] = np.frombuffer(r._take(4), np.uint8)
        if has_eye:
            r.f32()

    tris = np.frombuffer(r._take(2 * 3 * num_triangles), dtype="<u2").reshape(-1, 3).astype(np.int32)
    if tris.size and int(tris.max()) >= max(num_vertices, 1):
        raise NifError(f"triangle index {int(tris.max())} >= vertex count {num_vertices}")
    return verts, norms, uvs, colors, weights, bones, tris


def _read_shape(r: Reader, ctx: _Ctx, index: int, block_type: str) -> Shape:
    name, extras, controller, t, flags, collision = _read_av_object(r, ctx)
    r.vec3()                    # bounding sphere center
    r.f32()                     # bounding sphere radius
    # (boundMinMax exists only for stream version > 139)
    skin_ref = r.u32()
    shader_ref = r.u32()
    alpha_ref = r.u32()
    desc = r.u64()
    num_triangles = r.u16() if ctx.header["stream_version"] < 130 else r.u32()
    num_vertices = r.u16()
    data_size = r.u32()

    if data_size == 0:
        # Skinned SSE shapes keep their vertex/triangle payload in the
        # NiSkinPartition block instead (see BSDismemberSkinInstance -> data).
        verts = np.zeros((0, 3), np.float32)
        norms = np.zeros((0, 3), np.float32)
        uvs = np.zeros((0, 2), np.float32)
        colors = None
        weights = None
        bones = None
        tris = np.zeros((0, 3), np.int32)
    else:
        verts, norms, uvs, colors, weights, bones, tris = _read_vertex_stream(
            r, desc, num_vertices, num_triangles, ctx.header["stream_version"]
        )

    # Material, alpha and skin data are resolved in parse()'s second pass: those
    # blocks may sit after the shape that references them.
    r.u32()                     # particleDataSize (stream 100 only)
    shape = Shape(
        index=index, name=name, vertices=verts, normals=norms, uvs=uvs, colors=colors,
        weights=weights, bone_indices=bones, triangles=tris,
        shader_type=None, alpha_flags=None, alpha_threshold=None,
        textures=[], bones=[], body_parts=[],
        transform=t, flags=flags,
    )
    shape._skin_ref = skin_ref
    shape._shader_ref = shader_ref
    shape._alpha_ref = alpha_ref
    return shape




def _read_shader(r: Reader, ctx: _Ctx, index: int, block_type: str) -> dict:
    """BSLightingShaderProperty, SSE layout (user 12 / stream 100).

    Order: NiObjectNET carries bslspShaderType *before* the name; BSShaderProperty
    then writes the two fixed shader-flag words plus uv offset/scale; only after
    that come the texture set and the PBR-ish floats.
    """
    shader_type = r.u32()
    name, extras, controller = _read_net_object(r, _Ctx(ctx.header))
    out: dict = {"name": name, "shader_type": shader_type, "textures": []}
    if block_type != "BSLightingShaderProperty":
        return out
    out["shader_flags1"] = r.u32()
    out["shader_flags2"] = r.u32()
    r.f32(), r.f32()                                     # uv offset
    r.f32(), r.f32()                                     # uv scale
    tex_ref = r.u32()
    r.f32() * 1                                          # emissive color r/g/b
    r.f32(); r.f32()
    r.f32()                                              # emissive multiple
    r.u32()                                              # texture clamp mode
    r.f32()                                              # alpha
    r.f32()                                              # refraction strength
    r.f32()                                              # glossiness
    r.vec3()                                             # specular color
    r.f32()                                              # specular strength
    r.f32()                                              # soft lighting
    r.f32()                                              # rimlight power
    st = out["shader_type"]
    if st == 1:
        r.f32()
    elif st == 5:
        r.vec3()
        if ctx.header["stream_version"] >= 130:
            r.f32()
    elif st == 6:
        r.vec3()
    elif st == 7:
        r.f32(); r.f32()
    elif st == 11:
        r.f32(); r.f32(); r.f32(); r.f32()
    elif st == 14:
        r.f32()
    elif st == 16:
        r.f32(); r.vec3(); r.vec3()
    out["tex_ref"] = tex_ref
    return out


def _read_texture_set(r: Reader, ctx: _Ctx) -> list[str]:
    return r.strings(size=4, count_size=4)


def _read_alpha(r: Reader, ctx: _Ctx) -> tuple[int, int]:
    _read_net_object(r, _Ctx(ctx.header))
    flags = r.u16()
    threshold = r.u8()
    return flags, threshold


def _read_skin(r: Reader, ctx: _Ctx, block_type: str):
    """NiSkinInstance + BSDismemberSkinInstance tail.

    NB: NiSkinInstance derives from NiBoneContainer (a bare NiObject), NOT from
    NiObjectNET, so there is no name/extra-data/controller header here.
    """
    data_ref = r.u32()
    partition_ref = r.u32()
    r.u32()                                       # target ref
    num_bones = r.u32()
    bone_refs = [r.u32() for _ in range(num_bones)]
    parts: list[int] = []
    if block_type == "BSDismemberSkinInstance":
        n = r.u32()
        for _ in range(n):
            r.u16()                               # flags
            parts.append(r.u16())                 # body part id
    return bone_refs, parts, data_ref, partition_ref


def _read_skin_partition(r: Reader, ctx: _Ctx) -> dict:
    """NiSkinPartition for SSE (user 12 / stream 100) - the geometry lives here."""
    num_partitions = r.u32()
    data_size = r.u32()
    vertex_size = r.u32()
    desc = r.u64()
    verts = norms = uvs = colors = weights = bones = None
    num_vertices = 0
    if data_size > 0:
        if vertex_size == 0:
            raise NifError("skin partition: vertex size 0")
        num_vertices = data_size // vertex_size
        before = r.pos
        verts, norms, uvs, colors, weights, bones, _ = _read_vertex_stream(
            r, desc, num_vertices, 0, ctx.header["stream_version"]
        )
        consumed = r.pos - before
        if consumed < data_size:                    # unknown trailing per-vertex data
            r._take(data_size - consumed)
    tris_parts = []
    part_info = []
    for _ in range(num_partitions):
        nv = r.u16()
        nt = r.u16()
        n_bones = r.u16()
        n_strips = r.u16()
        r.u16()                                     # weights per vertex
        pbones = list(struct.unpack(f"<{n_bones}H", r._take(2 * n_bones))) if n_bones else []
        has_vertex_map = r.u8()
        if has_vertex_map:
            r._take(2 * nv)
        has_weights = r.u8()
        if has_weights:
            r._take(16 * nv)        # VertexWeight = 4 floats (nifly)
        strip_lengths = list(struct.unpack(f"<{n_strips}H", r._take(2 * n_strips))) if n_strips else []
        has_faces = r.u8()
        if has_faces and n_strips:
            for length in strip_lengths:
                r._take(2 * length)
        if n_strips == 0 and has_faces:
            tris_parts.append(np.frombuffer(r._take(6 * nt), dtype="<u2").reshape(-1, 3).astype(np.int32))
        has_bone_indices = r.u8()
        if has_bone_indices:
            r._take(4 * nv)
        r.u8()                                      # lod level
        r.u8()                                      # global VB
        part_desc = r.u64()
        r._take(6 * nt)                             # trueTriangles
        part_info.append({"num_vertices": nv, "num_triangles": nt, "bones": pbones,
                          "vertex_desc": part_desc})
    tris = np.concatenate(tris_parts) if tris_parts else np.zeros((0, 3), np.int32)
    return {"num_partitions": num_partitions, "vertices": verts, "normals": norms,
            "uvs": uvs, "colors": colors, "weights": weights, "bone_indices": bones,
            "triangles": tris, "num_vertices": num_vertices, "partitions": part_info,
            "vertex_desc": desc}


def parse(data: bytes, path: str = "<bytes>") -> NifFile:
    r = Reader(data)
    header = _read_header(r)
    if header["version"] != "20.2.0.7":
        raise NifError(f"{path}: unsupported NIF version {header['version']}")
    ctx = _Ctx(header)
    ctx.shaders = {}
    ctx.alphas = {}
    ctx.texture_sets = {}
    ctx.skins = {}

    types = [header["types"][i] for i in header["type_indices"]]
    sizes = header["sizes"]
    warnings: list[str] = []

    # pass 1: block table with offsets; parse only what we can, skip the rest
    starts: list[int] = []
    blocks: dict[int, object] = {}
    for i, btype in enumerate(types):
        starts.append(r.pos)
        size = sizes[i]
        if btype in SHAPE_TYPES:
            try:
                blocks[i] = ("shape", _read_shape(r, ctx, i, btype))
            except Exception as exc:
                warnings.append(f"block {i} {btype}: {type(exc).__name__}: {exc}")
                blocks[i] = ("bad_shape", str(exc))
        elif btype in LEGACY_SHAPE_TYPES:
            try:
                blocks[i] = ("shape", _read_legacy_shape(r, ctx, i, btype))
            except Exception as exc:
                warnings.append(f"block {i} {btype}: {type(exc).__name__}: {exc}")
                blocks[i] = ("bad_shape", str(exc))
        elif btype == "NiTriShapeData":
            try:
                blocks[i] = ("geomdata", _read_geometry_data(r, ctx, btype))
            except Exception as exc:
                warnings.append(f"block {i} {btype}: {type(exc).__name__}: {exc}")
                blocks[i] = ("bad_geomdata", str(exc))
        elif btype in NODE_TYPES:
            name, extras, controller, t, flags, collision = _read_av_object(r, ctx)
            n_children = r.u32()
            children = [r.u32() for _ in range(n_children)]
            n_effects = r.u32()
            [r.u32() for _ in range(n_effects)]
            blocks[i] = ("node", Node(index=i, name=name, transform=t, children=children))
        elif btype in SKIN_TYPES:
            try:
                refs, parts, data_ref, part_ref = _read_skin(r, ctx, btype)
                blocks[i] = ("skin", (refs, parts, data_ref, part_ref))
            except Exception as exc:
                warnings.append(f"block {i} {btype}: {type(exc).__name__}: {exc}")
                blocks[i] = ("bad_skin", str(exc))
        elif btype == "BSLightingShaderProperty":
            try:
                blocks[i] = ("shader", _read_shader(r, ctx, i, btype))
            except Exception as exc:
                warnings.append(f"block {i} {btype}: {type(exc).__name__}: {exc}")
                blocks[i] = ("bad_shader", str(exc))
        elif btype == "BSShaderTextureSet":
            blocks[i] = ("textures", _read_texture_set(r, ctx))
        elif btype == "NiSkinPartition":
            try:
                blocks[i] = ("partition", _read_skin_partition(r, ctx))
            except Exception as exc:
                warnings.append(f"block {i} {btype}: {type(exc).__name__}: {exc}")
                blocks[i] = ("bad_partition", str(exc))
        elif btype == "NiAlphaProperty":
            blocks[i] = ("alpha", _read_alpha(r, ctx))
        elif btype.startswith("bhk") or btype.startswith("BSBound"):
            blocks[i] = ("collision", btype)
        elif btype in ("BSInvMarker", "BSXFlags", "NiStringExtraData", "NiIntegerExtraData"):
            blocks[i] = ("extra", btype)
        else:
            blocks[i] = ("skipped", btype)
        consumed = r.pos - starts[-1]
        if size and consumed != size:
            warnings.append(f"block {i} {btype}: consumed {consumed} of {size} bytes")
        r.pos = starts[-1] + size
    # footer
    try:
        n_roots = r.u32()
        roots = [r.u32() for _ in range(n_roots)]
    except NifError:
        roots = [0]

    # pass 2: resolve references (shader/alpha/skin may follow their users)
    nodes: dict[int, Node] = {}
    for i, (kind, value) in blocks.items():
        if kind == "node":
            nodes[i] = value
    parents: dict[int, int] = {}
    for i, node in nodes.items():
        for child in node.children:
            parents[child] = i
            if child in nodes:
                nodes[child].parent = i
    shapes: list[Shape] = []
    for i, (kind, value) in blocks.items():
        if kind == "textures":
            ctx.texture_sets[i] = value
        elif kind == "alpha":
            ctx.alphas[i] = value
        elif kind == "skin":
            refs, parts, data_ref, part_ref = value
            ctx.skins[i] = ([nodes[x].name if x in nodes else f"<{x}>" for x in refs], parts,
                            data_ref, part_ref)
    for i, (kind, value) in blocks.items():
        if kind == "shader":
            tex_ref = value.get("tex_ref", 0xFFFFFFFF)
            textures = list(ctx.texture_sets.get(tex_ref, [])) if tex_ref != 0xFFFFFFFF else []
            ctx.shaders[i] = (textures, value["shader_type"])
    # second pass over shapes now that the tables are full
    for i, (kind, value) in blocks.items():
        if kind != "shape":
            continue
        s: Shape = value
        if s._shader_ref != 0xFFFFFFFF:
            info = ctx.shaders.get(s._shader_ref)
            if info:
                s.textures, s.shader_type = list(info[0]), info[1]
        if s._alpha_ref != 0xFFFFFFFF:
            alpha = ctx.alphas.get(s._alpha_ref)
            if alpha:
                s.alpha_flags, s.alpha_threshold = alpha
        data_ref = getattr(s, "_data_ref", 0xFFFFFFFF)
        if s.num_vertices == 0 and data_ref != 0xFFFFFFFF:
            geo = blocks.get(data_ref)
            if geo and geo[0] == "geomdata":
                s.vertices = geo[1]["vertices"]
                s.normals = geo[1]["normals"]
                s.uvs = geo[1]["uvs"]
                s.colors = geo[1]["colors"]
                s.triangles = geo[1]["triangles"]
        if s._skin_ref != 0xFFFFFFFF:
            skin = ctx.skins.get(s._skin_ref)
            if skin:
                s.bones, s.body_parts = list(skin[0]), list(skin[1])
                if s.num_vertices == 0 and skin[3] != 0xFFFFFFFF:
                    part = blocks.get(skin[3])
                    if part and part[0] == "partition":
                        data = part[1]
                        s.vertices = data["vertices"] if data["vertices"] is not None else s.vertices
                        s.normals = data["normals"] if data["normals"] is not None else s.normals
                        s.uvs = data["uvs"] if data["uvs"] is not None else s.uvs
                        s.colors = data["colors"]
                        s.weights = data["weights"]
                        s.bone_indices = data["bone_indices"]
                        s.triangles = data["triangles"]
        shapes.append(s)

    extra: dict[str, int] = {}
    for kind, value in blocks.values():
        if kind == "extra":
            extra[value] = extra.get(value, 0) + 1
    collision = [value for kind, value in blocks.values() if kind == "collision"]

    return NifFile(
        path=path,
        version=header["version"],
        user_version=header["user_version"],
        stream_version=header["stream_version"],
        creator=header["creator"],
        block_types=types,
        nodes=nodes,
        shapes=shapes,
        extra_data=extra,
        collision_blocks=collision,
        roots=roots,
        warnings=warnings,
        parents=parents,
    )
