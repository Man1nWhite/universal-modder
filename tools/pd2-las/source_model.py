"""Source-engine studio model reader (.mdl + .vvd + .dx90.vtx), MDL 44-49.

Struct layouts follow Valve's `src/public/studio.h` and `src/public/optimize.h`
(source-sdk-2013): the VTX namespace is `#pragma pack(1)`, and every
`sznameindex` is a **struct-relative** byte offset, not a file offset.

Verified against two archives of different origin: `l4d2_miranda_lawson_1.zip`
(MDL 48, VVD 4, VTX 7) and the Geralt GMod workshop addon (MDL 49, ValveBiped,
55,793 verts / 49,760 tris). `SUPPORTED_MDL_VERSIONS` explains why the gate is
44-49 and not 48-49. This is a clean-room reader written from the SDK headers;
it parses only what the conversion needs: bones, materials, and skinned
triangles.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MDL_MAGIC = b"IDST"
#: MDL versions this reader understands. Everything it touches is identical
#: across 44-49: `studiohdr_t`'s count/offset pairs, the 216-byte
#: `mstudiobone_t`, and `mstudiomodel_t` addressed with `vertexindex / 48`.
#: Source-faithful parsers branch only at 36, 44, 53 and 2531 (SourceIO's
#: `ModelV36Plus` / `Bone.from_buffer`), so 44 is the real floor — which matters
#: because a Garry's Mod ragdoll is as likely to be HL2-era v44 as L4D2-era v49.
SUPPORTED_MDL_VERSIONS = (44, 45, 46, 47, 48, 49)
VVD_MAGIC = b"IDSV"
VTX_VERSION = 7
MAX_NUM_BONES_PER_VERT = 3
MAX_NUM_LODS = 8

BONE_STRIDE = 216
TEXTURE_STRIDE = 64
BODYPART_STRIDE = 16
MODEL_FIXED = 96  # up to and including numvertices/vertexindex/tangentsindex
MESH_STRIDE = 116
VERTEX_STRIDE_VVD = 48  # mstudiovertex_t
VTX_VERTEX_STRIDE = 9  # Vertex_t under pack(1)
VTX_STRIP_STRIDE = 27  # StripHeader_t under pack(1)
VTX_SGROUP_STRIDE = 25  # StripGroupHeader_t under pack(1)


class SourceModelError(ValueError):
    pass


def _cstr(buf: bytes, off: int) -> str:
    if off < 0 or off >= len(buf):
        raise SourceModelError(f"string offset out of range: {off}")
    return buf[off : buf.index(b"\x00", off)].decode("latin1")


@dataclass(frozen=True)
class Bone:
    name: str
    parent: int
    pos: tuple[float, float, float]
    quat: tuple[float, float, float, float]


@dataclass(frozen=True)
class SkinVertex:
    """One VVD vertex: up to 3 weighted bone influences."""

    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]
    weights: tuple[tuple[int, float], ...]  # (bone_index, weight)


@dataclass(frozen=True)
class SubMesh:
    """One material group of a model: triangles over the model's vertex range."""

    material: str
    triangle_indices: tuple[int, int, ...]  # 3 per triangle, into ModelData.vertices


@dataclass
class ModelData:
    name: str
    bones: list[Bone] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    vertices: list[SkinVertex] = field(default_factory=list)
    meshes: list[SubMesh] = field(default_factory=list)
    #: Bodygroup models beyond the first of their bodypart. They are alternate
    #: states (hat/hair/variant) of geometry that is already represented by the
    #: default state this reader returns, so they are counted, not parsed.
    skipped_bodygroup_models: int = 0

    @property
    def triangle_count(self) -> int:
        return sum(len(m.triangle_indices) // 3 for m in self.meshes)


def _read_bones(mdl: bytes, count: int, offset: int) -> list[Bone]:
    bones = []
    for i in range(count):
        base = offset + i * BONE_STRIDE
        if base + BONE_STRIDE > len(mdl):
            raise SourceModelError("bone table truncated")
        name_off, parent = struct.unpack_from("<ii", mdl, base)
        pos = struct.unpack_from("<fff", mdl, base + 32)
        quat = struct.unpack_from("<ffff", mdl, base + 44)
        bones.append(
            Bone(
                name=_cstr(mdl, base + name_off),
                parent=parent,
                pos=pos,
                quat=quat,
            )
        )
    return bones


def _read_textures(mdl: bytes, count: int, offset: int) -> list[str]:
    out = []
    for i in range(count):
        base = offset + i * TEXTURE_STRIDE
        (name_off,) = struct.unpack_from("<i", mdl, base)
        out.append(_cstr(mdl, base + name_off))
    return out


def _read_vvd(vvd: bytes, model_numverts: int) -> list[SkinVertex]:
    if vvd[:4] != VVD_MAGIC:
        raise SourceModelError(f"bad VVD magic: {vvd[:4]!r}")
    version, checksum = struct.unpack_from("<ii", vvd, 4)
    if version not in (4,):
        raise SourceModelError(f"unsupported VVD version {version}")
    num_lods, = struct.unpack_from("<i", vvd, 12)
    if not 0 < num_lods <= MAX_NUM_LODS:
        raise SourceModelError(f"bad VVD numLODs: {num_lods}")
    num_fixups, fixup_start, vertex_start, tangent_start = struct.unpack_from(
        "<iiii", vvd, 16 + MAX_NUM_LODS * 4
    )
    lod0_count, = struct.unpack_from("<i", vvd, 16)
    if lod0_count != model_numverts:
        raise SourceModelError(
            f"VVD LOD0 vertex count {lod0_count} != model numvertices {model_numverts}"
        )

    def raw_vertex(idx: int) -> SkinVertex:
        base = vertex_start + idx * VERTEX_STRIDE_VVD
        w = struct.unpack_from("<fff", vvd, base)
        b = struct.unpack_from("<BBB", vvd, base + 12)
        (num_bones,) = struct.unpack_from("<B", vvd, base + 15)
        pos = struct.unpack_from("<fff", vvd, base + 16)
        normal = struct.unpack_from("<fff", vvd, base + 28)
        uv = struct.unpack_from("<ff", vvd, base + 40)
        n = min(int(num_bones), MAX_NUM_BONES_PER_VERT)
        weights = tuple((b[j], w[j]) for j in range(n) if w[j] > 0.0)
        return SkinVertex(pos=pos, normal=normal, uv=uv, weights=weights)

    if num_fixups == 0:
        return [raw_vertex(i) for i in range(lod0_count)]

    out: list[SkinVertex] = []
    for i in range(num_fixups):
        lod, src_id, num_v = struct.unpack_from("<iii", vvd, fixup_start + i * 12)
        if lod >= 0:
            for k in range(num_v):
                out.append(raw_vertex(src_id + k))
    if len(out) != lod0_count:
        raise SourceModelError(
            f"VVD fixups produced {len(out)} LOD0 vertices, expected {lod0_count}"
        )
    return out


def _read_vtx_meshes(
    vtx: bytes, meshes_out: list[tuple[int, list[tuple[int, int, int]]]]
) -> None:
    """Walk the VTX bodypart/model/lod/mesh tree into per-mesh triangle lists.

    Appends ``(mdl_mesh_index, triangles)`` where each triangle is three
    origMeshVertID values (mesh-local; the MDL mesh vertexoffset rebases them
    into model-space VVD indices in :func:`load_model`).
    """
    if len(vtx) < 36:
        raise SourceModelError("VTX truncated")
    version, = struct.unpack_from("<i", vtx, 0)
    if version != VTX_VERSION:
        raise SourceModelError(f"unsupported VTX version {version}")
    checksum, num_lods, mat_repl_off, num_bodyparts, bodypart_off = struct.unpack_from(
        "<iiiii", vtx, 16
    )
    mesh_index = 0
    for bi in range(num_bodyparts):
        bp = bodypart_off + bi * 8
        num_models, model_off = struct.unpack_from("<ii", vtx, bp)
        # Only model 0 of a bodypart: that is the state the MDL's own mesh table
        # describes, and the default choice in game. Walking the alternates too
        # is what made a playermodel with a single hat fail with
        # "VTX has N meshes, MDL has M" — the mesh counts could never agree.
        for mi in range(min(1, num_models)):
            mo = bp + model_off + mi * 8
            num_lods_m, lod_off = struct.unpack_from("<ii", vtx, mo)
            for li in range(min(1, num_lods_m)):
                lo = mo + lod_off + li * 12
                num_meshes, mesh_off, _switch = struct.unpack_from("<iif", vtx, lo)
                for mesh_i in range(num_meshes):
                    me = lo + mesh_off + mesh_i * 9
                    num_groups, group_off, _flags = struct.unpack_from("<iiB", vtx, me)
                    triangles: list[tuple[int, int, int]] = []
                    seen: set[tuple[int, int, int]] = set()
                    for gi in range(num_groups):
                        go = me + group_off + gi * VTX_SGROUP_STRIDE
                        num_verts, vert_off, num_indices, index_off, num_strips, strip_off = (
                            struct.unpack_from("<iiiiii", vtx, go)
                        )
                        if vert_off + num_verts * VTX_VERTEX_STRIDE > len(vtx):
                            raise SourceModelError("VTX vertex array out of range")
                        orig_ids = []
                        for vi in range(num_verts):
                            vbase = go + vert_off + vi * VTX_VERTEX_STRIDE
                            (orig,) = struct.unpack_from("<H", vtx, vbase + 4)
                            orig_ids.append(orig)
                        if index_off + num_indices * 2 > len(vtx):
                            raise SourceModelError("VTX index array out of range")
                        indices = struct.unpack_from(f"<{num_indices}H", vtx, go + index_off)

                        def add_tri(a: int, b: int, c: int) -> None:
                            key = tuple(sorted((a, b, c)))
                            if key in seen:
                                return  # flexed/non-flexed groups repeat shared triangles
                            seen.add(key)
                            triangles.append((a, b, c))

                        for si in range(num_strips):
                            so = go + strip_off + si * VTX_STRIP_STRIDE
                            s_ni, s_ioff, s_nv, s_voff, _s_nb, s_flags = struct.unpack_from(
                                "<iiiiHB", vtx, so
                            )
                            if s_flags & 0x02:  # STRIP_IS_TRISTRIP
                                strip_idx = indices[s_ioff : s_ioff + s_ni]
                                for k in range(2, len(strip_idx)):
                                    a = orig_ids[strip_idx[k - 2]]
                                    b = orig_ids[strip_idx[k - 1]]
                                    c = orig_ids[strip_idx[k]]
                                    if k % 2:  # restore winding
                                        a, b = b, a
                                    if a != b and b != c and a != c:
                                        add_tri(a, b, c)
                            else:  # STRIP_IS_TRILIST
                                if s_ni % 3:
                                    raise SourceModelError("trilist strip index count not %3")
                                for t in range(0, s_ni, 3):
                                    tri = tuple(
                                        orig_ids[indices[s_ioff + t + k]] for k in range(3)
                                    )
                                    add_tri(*tri)
                    meshes_out.append((mesh_index, triangles))
                    mesh_index += 1


def load_model(mdl: bytes, vvd: bytes, vtx: bytes) -> ModelData:
    """Parse a studio model triple into bones, vertices and material meshes."""
    if mdl[:4] != MDL_MAGIC:
        raise SourceModelError(f"bad MDL magic: {mdl[:4]!r}")
    version, checksum = struct.unpack_from("<ii", mdl, 4)
    if version not in SUPPORTED_MDL_VERSIONS:
        raise SourceModelError(
            f"unsupported MDL version {version} "
            f"(readable: {SUPPORTED_MDL_VERSIONS[0]}-{SUPPORTED_MDL_VERSIONS[-1]})"
        )
    name = _cstr(mdl, 12)

    # studiohdr_t count/offset pairs (source-sdk-2013 studio.h layout).
    base = 76  # past id, version, checksum, name[64]
    base += 4  # length
    base += 12 * 6  # eyeposition, illumposition, hull_min, hull_max, view_bbmin, view_bbmax
    flags, = struct.unpack_from("<i", mdl, base)
    base += 4
    bone_count, bone_off = struct.unpack_from("<ii", mdl, base)
    base += 8
    base += 8  # bonecontroller
    base += 8  # hitbox
    base += 8  # localanim
    base += 8  # localseq
    base += 8  # activitylistversion, eventsindexed
    texture_count, texture_off = struct.unpack_from("<ii", mdl, base)
    base += 8
    base += 8  # texturedir
    base += 12  # skinref / skinrfamily
    bodypart_count, bodypart_off = struct.unpack_from("<ii", mdl, base)

    if not 0 < bone_count < 10000 or not 0 < bodypart_count < 1000:
        raise SourceModelError("implausible bone/bodypart counts")

    bones = _read_bones(mdl, bone_count, bone_off)
    materials = _read_textures(mdl, texture_count, texture_off)

    # bodypart -> model (first model only; L4D2 survivors use one model per part)
    model_numverts = 0
    mesh_specs: list[tuple[int, int]] = []  # (material_index, vertexoffset)
    model_name = name
    skipped_bodygroups = 0
    for bi in range(bodypart_count):
        bp = bodypart_off + bi * BODYPART_STRIDE
        _bp_name_off, num_models, _b, model_index = struct.unpack_from("<iiii", mdl, bp)
        if num_models < 1:
            raise SourceModelError("bodypart without models")
        skipped_bodygroups += num_models - 1
        mo = bp + model_index
        if bi == 0:
            model_name = _cstr(mdl, mo)
        num_meshes, mesh_index, num_vertices, vertex_index = struct.unpack_from(
            "<iiii", mdl, mo + 64 + 8
        )
        model_voff = vertex_index // VERTEX_STRIDE_VVD
        model_numverts += num_vertices
        for mesh_i in range(num_meshes):
            me = mo + mesh_index + mesh_i * MESH_STRIDE
            material, _modelindex, _numverts, vertexoffset = struct.unpack_from("<iiii", mdl, me)
            if not 0 <= material < len(materials):
                raise SourceModelError(f"mesh material index {material} out of range")
            mesh_specs.append((material, model_voff + vertexoffset))

    vertices = _read_vvd(vvd, model_numverts)

    vtx_meshes: list[tuple[int, list[tuple[int, int, int]]]] = []
    _read_vtx_meshes(vtx, vtx_meshes)
    if len(vtx_meshes) != len(mesh_specs):
        raise SourceModelError(
            f"VTX has {len(vtx_meshes)} meshes, MDL has {len(mesh_specs)}"
        )

    out = ModelData(
        name=model_name,
        bones=bones,
        materials=materials,
        vertices=vertices,
        skipped_bodygroup_models=skipped_bodygroups,
    )
    nverts = len(vertices)
    for (material_index, voff), (_mi, triangles) in zip(mesh_specs, vtx_meshes):
        flat: list[int] = []
        for tri in triangles:
            for idx in tri:
                # origMeshVertID is mesh-local; rebase with the mesh's
                # mstudiomesh_t.vertexoffset into the global VVD vertex list.
                gidx = voff + idx
                if not 0 <= gidx < nverts:
                    raise SourceModelError(f"vertex index {gidx} out of range (0..{nverts})")
                flat.append(gidx)
        out.meshes.append(
            SubMesh(material=materials[material_index], triangle_indices=tuple(flat))
        )
    return out

# ---------------------------------------------------------------------------
# every bodygroup model of a studio MDL (not just each bodypart's first);
# moved verbatim from tools/pd2-las/build_christie_las.py when that file was
# deleted on 2026-11-14 - the parser is source-model machinery, not builder code.
# ---------------------------------------------------------------------------
MODEL_STRIDE = 148  # sizeof(mstudiomodel_t) for this MDL 48 build

# ---------------------------------------------------------------------------
# source loading (all bodygroup models, not just each bodypart's first)
# ---------------------------------------------------------------------------
def _read_vtx_meshes_all_models(vtx: bytes) -> list[tuple[int, list[tuple[int, int, int]]]]:
    """Like source_model._read_vtx_meshes but walks EVERY model of every
    bodypart (DOA5 ships body/glasses/bra/head variants this way), matching
    the MDL bodypart->model->mesh order."""
    out: list[tuple[int, list[tuple[int, int, int]]]] = []
    version, = struct.unpack_from("<i", vtx, 0)
    if version != VTX_VERSION:
        raise SourceModelError(f"unsupported VTX version {version}")
    _checksum, _num_lods, _mat_repl_off, num_bodyparts, bodypart_off = (
        struct.unpack_from("<iiiii", vtx, 16))
    mesh_index = 0
    for bi in range(num_bodyparts):
        bp = bodypart_off + bi * 8
        num_models, model_off = struct.unpack_from("<ii", vtx, bp)
        for mi in range(num_models):
            mo = bp + model_off + mi * 8
            num_lods_m, lod_off = struct.unpack_from("<ii", vtx, mo)
            for li in range(min(1, num_lods_m)):
                lo = mo + lod_off + li * 12
                num_meshes, mesh_off, _switch = struct.unpack_from("<iif", vtx, lo)
                for mesh_i in range(num_meshes):
                    me = lo + mesh_off + mesh_i * 9
                    num_groups, group_off, _flags = struct.unpack_from("<iiB", vtx, me)
                    triangles: list[tuple[int, int, int]] = []
                    seen: set[tuple[int, int, int]] = set()
                    for gi in range(num_groups):
                        go = me + group_off + gi * VTX_SGROUP_STRIDE
                        (num_verts, vert_off, num_indices, index_off,
                         num_strips, strip_off) = struct.unpack_from("<iiiiii", vtx, go)
                        orig_ids = []
                        for vi in range(num_verts):
                            vbase = go + vert_off + vi * VTX_VERTEX_STRIDE
                            (orig,) = struct.unpack_from("<H", vtx, vbase + 4)
                            orig_ids.append(orig)
                        indices = struct.unpack_from(f"<{num_indices}H", vtx, go + index_off)

                        def add_tri(a, b, c):
                            key = tuple(sorted((a, b, c)))
                            if key in seen:
                                return
                            seen.add(key)
                            triangles.append((a, b, c))

                        for si in range(num_strips):
                            so = go + strip_off + si * VTX_STRIP_STRIDE
                            s_ni, s_ioff, s_nv, s_voff, _s_nb, s_flags = struct.unpack_from(
                                "<iiiiHB", vtx, so)
                            if s_flags & 0x02:
                                strip_idx = indices[s_ioff:s_ioff + s_ni]
                                for k in range(2, len(strip_idx)):
                                    a, b, c = (orig_ids[strip_idx[k - 2]],
                                               orig_ids[strip_idx[k - 1]],
                                               orig_ids[strip_idx[k]])
                                    if k % 2:
                                        a, b = b, a
                                    if a != b and b != c and a != c:
                                        add_tri(a, b, c)
                            else:
                                for t in range(0, s_ni, 3):
                                    add_tri(*(orig_ids[indices[s_ioff + t + k]]
                                              for k in range(3)))
                    out.append((mesh_index, triangles))
                    mesh_index += 1
    return out


def load_all_bodygroups(mdl: bytes, vvd: bytes, vtx: bytes) -> ModelData:
    """The MDL/VVD/VTX triple, including EVERY bodygroup model of every bodypart.

    DOA5 ships body/glasses/bra/head variants as per-bodypart model variants, so
    ``load_model`` (each bodypart's first model only) cannot parse this triple - its
    VVD LOD0 count then disagrees. Used by ``render_mesh_skeleton.py --source`` on
    ``references/Christie.zip``.
    """
    if mdl[:4] != MDL_MAGIC:
        raise SourceModelError("bad MDL magic")
    version, _checksum = struct.unpack_from("<ii", mdl, 4)
    if version not in SUPPORTED_MDL_VERSIONS:
        raise SourceModelError(f"unsupported MDL version {version}")

    base = 76
    base += 4            # length
    base += 12 * 6       # eye/illum/hull/view boxes
    base += 4            # flags
    bone_count, bone_off = struct.unpack_from("<ii", mdl, base); base += 8
    base += 8 * 5        # bonecontroller, hitbox, localanim, localseq, activity/events
    texture_count, texture_off = struct.unpack_from("<ii", mdl, base); base += 8
    base += 8            # texturedir
    base += 12           # skinref/skinfamily
    bodypart_count, bodypart_off = struct.unpack_from("<ii", mdl, base)

    bones = _read_bones(mdl, bone_count, bone_off)
    materials = _read_textures(mdl, texture_count, texture_off)

    mesh_specs: list[tuple[int, int]] = []  # (material_index, model vertex offset)
    model_numverts = 0
    model_name = _cstr(mdl, 12)
    for bi in range(bodypart_count):
        bp = bodypart_off + bi * BODYPART_STRIDE
        _n, num_models, _b, model_index = struct.unpack_from("<iiii", mdl, bp)
        for mi in range(num_models):
            mo = bp + model_index + mi * MODEL_STRIDE
            if mi == 0 and bi == 0:
                model_name = _cstr(mdl, mo)
            num_meshes, mesh_index, num_vertices, vertex_index = struct.unpack_from(
                "<iiii", mdl, mo + 72)
            voff = vertex_index // VERTEX_STRIDE_VVD
            model_numverts += num_vertices
            for mesh_i in range(num_meshes):
                me = mo + mesh_index + mesh_i * MESH_STRIDE
                material, _mi, _nv, vertexoffset = struct.unpack_from("<iiii", mdl, me)
                mesh_specs.append((material, voff + vertexoffset))

    vertices = _read_vvd(vvd, model_numverts)
    vtx_meshes = _read_vtx_meshes_all_models(vtx)
    if len(vtx_meshes) != len(mesh_specs):
        raise SourceModelError(
            f"VTX has {len(vtx_meshes)} meshes, MDL has {len(mesh_specs)}")

    out = ModelData(name=model_name, bones=bones, materials=materials,
                       vertices=vertices)
    nverts = len(vertices)
    for (material_index, voff), (_mi, triangles) in zip(mesh_specs, vtx_meshes):
        flat: list[int] = []
        for tri in triangles:
            for idx in tri:
                gidx = voff + idx
                if not 0 <= gidx < nverts:
                    raise SourceModelError(f"vertex index {gidx} out of range")
                flat.append(gidx)
        out.meshes.append(SubMesh(material=materials[material_index],
                                     triangle_indices=tuple(flat)))
    return out


