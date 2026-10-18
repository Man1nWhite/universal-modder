"""Diesel .model container codec (PAYDAY 2 / Legendary Armor Suit outfits).

Ground truth: diesel-modding/payday2-model-tool (p2mt) C# sources, cross-probed
against 2b.model / fps_2b.model (reference LAS pack). This module mirrors the
on-disk LEGACY container exactly (magic 0xFFFFFFFF), which is what 2b.model and
every vanilla PD2 unit use.

Key format facts encoded here (see docs/audits/2026-10-18-route-change-audit.md):
- container: u32 0xFFFFFFFF, u32 filesize, u32 section_count, then
  {u32 type, u32 id, u32 size, payload[size]} per section. DODB variant exists
  (magic 0x42444F44 "DODB") but is not used for game units.
- legacy geometry channel types are shifted -2 above TEXCOORD7 on disk
  (p2mt: `if (legacy && itemType > TEXCOORD7) itemType += 2` on read).
- BLENDINDICES0 (enum 17, disk 15) = 4x u16 palette indices per vertex.
  BLENDWEIGHT0 (enum 19, disk 17) = 3x f32 weights (ItemSize 3).
- SkinBones.Rotations[i] = inverse(bone.WorldTransform) at bind pose;
  Global_skin_transform = Hips world; drawables parented to Hips with
  Transform = inverse(Hips world) -> drawable world = identity, geometry
  vertices in world-at-bind space (z-up, cm, feet at z=0).
- Object3D matrix translation lives in m[12..14]; World = Transform ∘ Parent
  (row-vector convention, MultDiesel = System.Numerics `a * b`).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# ---------------------------------------------------------------- hash names

_MASK = 0xFFFFFFFFFFFFFFFF


def _u64(x: int) -> int:
    return x & _MASK


def _mix64(a: int, b: int, c: int):
    a = _u64(a - b); a = _u64(a - c); a ^= (c >> 43)
    b = _u64(b - c); b = _u64(b - a); b ^= _u64(a << 9)
    c = _u64(c - a); c = _u64(c - b); c ^= (b >> 8)
    a = _u64(a - b); a = _u64(a - c); a ^= (c >> 38)
    b = _u64(b - c); b = _u64(b - a); b ^= _u64(a << 23)
    c = _u64(c - a); c = _u64(c - b); c ^= (b >> 5)
    a = _u64(a - b); a = _u64(a - c); a ^= (c >> 35)
    b = _u64(b - c); b = _u64(b - a); b ^= _u64(a << 49)
    c = _u64(c - a); c = _u64(c - b); c ^= (b >> 11)
    a = _u64(a - b); a = _u64(a - c); a ^= (c >> 12)
    b = _u64(b - c); b = _u64(b - a); b ^= _u64(a << 18)
    c = _u64(c - a); c = _u64(c - b); c ^= (b >> 22)
    return a, b, c


def hash64(data: bytes | str, level: int = 0) -> int:
    """Diesel idstring hash64 (Jenkins lookup3 64-bit variant, p2mt Hash64.cs)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    a = b = level
    c = 0x9E3779B97F4A7C13
    length = len(data)
    ln = length
    off = 0
    while ln >= 24:
        a = _u64(a + int.from_bytes(data[off:off + 8], "little"))
        b = _u64(b + int.from_bytes(data[off + 8:off + 16], "little"))
        c = _u64(c + int.from_bytes(data[off + 16:off + 24], "little"))
        a, b, c = _mix64(a, b, c)
        off += 24
        ln -= 24
    c = _u64(c + length)
    tail = data[off:]
    if ln >= 23: c = _u64(c + (tail[22] << 56))
    if ln >= 22: c = _u64(c + (tail[21] << 48))
    if ln >= 21: c = _u64(c + (tail[20] << 40))
    if ln >= 20: c = _u64(c + (tail[19] << 32))
    if ln >= 19: c = _u64(c + (tail[18] << 24))
    if ln >= 18: c = _u64(c + (tail[17] << 16))
    if ln >= 17: c = _u64(c + (tail[16] << 8))
    if ln >= 16: b = _u64(b + (tail[15] << 56))
    if ln >= 15: b = _u64(b + (tail[14] << 48))
    if ln >= 14: b = _u64(b + (tail[13] << 40))
    if ln >= 13: b = _u64(b + (tail[12] << 32))
    if ln >= 12: b = _u64(b + (tail[11] << 24))
    if ln >= 11: b = _u64(b + (tail[10] << 16))
    if ln >= 10: b = _u64(b + (tail[9] << 8))
    if ln >= 9: b = _u64(b + tail[8])
    if ln >= 8: a = _u64(a + (tail[7] << 56))
    if ln >= 7: a = _u64(a + (tail[6] << 48))
    if ln >= 6: a = _u64(a + (tail[5] << 40))
    if ln >= 5: a = _u64(a + (tail[4] << 32))
    if ln >= 4: a = _u64(a + (tail[3] << 24))
    if ln >= 3: a = _u64(a + (tail[2] << 16))
    if ln >= 2: a = _u64(a + (tail[1] << 8))
    if ln >= 1: a = _u64(a + tail[0])
    a, b, c = _mix64(a, b, c)
    return c


# ------------------------------------------------------------------- tags

ANIMATION_DATA = 0x5DC011B8
AUTHOR = 0x7623C465
MATERIAL_GROUP = 0x29276B1D
MATERIAL = 0x3C54609C
OBJECT3D = 0x0FFCD100
MODEL_DATA = 0x62212D88
GEOMETRY = 0x7AB072D3
TOPOLOGY = 0x4C507A13
PASSTHROUGH_GP = 0xE3A3B1CA
TOPOLOGY_IP = 0x03B634BD
SKINBONES = 0x65CC1825
BONES = 0x0EB43C77
CUSTOM_HASHLIST = 0x7C7844FD

TAG_NAMES = {
    ANIMATION_DATA: "animation_data",
    AUTHOR: "author",
    MATERIAL_GROUP: "material_group",
    MATERIAL: "material",
    OBJECT3D: "object3D",
    MODEL_DATA: "model_data",
    GEOMETRY: "geometry",
    TOPOLOGY: "topology",
    PASSTHROUGH_GP: "passthroughGP",
    TOPOLOGY_IP: "topologyIP",
    SKINBONES: "skinbones",
    BONES: "bones",
    CUSTOM_HASHLIST: "custom_hashlist",
}

# legacy disk type -> enum type (p2mt adds +2 above TEXCOORD7 on read)
LEGACY_TYPE_SHIFT_ABOVE = 14  # enum value; disk = enum-2 when enum > 14


def to_disk_type(enum_type: int) -> int:
    return enum_type - 2 if enum_type > LEGACY_TYPE_SHIFT_ABOVE else enum_type


def to_enum_type(disk_type: int) -> int:
    return disk_type + 2 if disk_type > LEGACY_TYPE_SHIFT_ABOVE else disk_type


# geometry channel enum (p2mt GeometryChannelTypes)
POSITION0 = 1
NORMAL0 = 2
COLOR0 = 5
TEXCOORD0 = 7
BLENDINDICES0 = 17
BLENDWEIGHT0 = 19
UV_DIRECTION_V0 = 22
UV_DIRECTION_U0 = 23

# ItemSize index -> bytes per item (p2mt PaydayItemSizes)
PAYDAY_ITEM_SIZES = [0, 4, 8, 12, 16, 4, 4, 8, 4, 4]


# ------------------------------------------------------------------- mats

Mat = tuple  # 16 floats, row-major; translation at [12..14]

IDENTITY: Mat = (1.0, 0.0, 0.0, 0.0,
                 0.0, 1.0, 0.0, 0.0,
                 0.0, 0.0, 1.0, 0.0,
                 0.0, 0.0, 0.0, 1.0)


def mat_mul(a: Mat, b: Mat) -> Mat:
    """System.Numerics `a * b` (row-vector convention: v * (a*b) == (v*a) * b)."""
    out = [0.0] * 16
    for i in range(4):
        for j in range(4):
            out[i * 4 + j] = (a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j]
                              + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j])
    return tuple(out)


def mat_inv(m: Mat) -> Mat:
    """General 4x4 inverse."""
    a = [list(m[0:4]), list(m[4:8]), list(m[8:12]), list(m[12:16])]
    inv = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    for col in range(4):
        piv = max(range(col, 4), key=lambda r: abs(a[r][col]))
        a[col], a[piv] = a[piv], a[col]
        inv[col], inv[piv] = inv[piv], inv[col]
        d = a[col][col]
        if d == 0:
            raise ValueError("singular matrix")
        a[col] = [x / d for x in a[col]]
        inv[col] = [x / d for x in inv[col]]
        for r in range(4):
            if r != col and a[r][col] != 0.0:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
                inv[r] = [x - f * y for x, y in zip(inv[r], inv[col])]
    return tuple(x for row in inv for x in row)


def mat_apply_point(m: Mat, p):
    x, y, z = p
    return (x * m[0] + y * m[4] + z * m[8] + m[12],
            x * m[1] + y * m[5] + z * m[9] + m[13],
            x * m[2] + y * m[6] + z * m[10] + m[14])


def mat_apply_vec(m: Mat, v):
    """Apply only the 3x3 part (rotation/scale) — for normals/directions."""
    x, y, z = v
    return (x * m[0] + y * m[4] + z * m[8],
            x * m[1] + y * m[5] + z * m[9],
            x * m[2] + y * m[6] + z * m[10])


def mat_from_pos_rot_rows(rows3, pos) -> Mat:
    """Build a matrix from three 3-float rows plus translation."""
    return (rows3[0][0], rows3[0][1], rows3[0][2], 0.0,
            rows3[1][0], rows3[1][1], rows3[1][2], 0.0,
            rows3[2][0], rows3[2][1], rows3[2][2], 0.0,
            pos[0], pos[1], pos[2], 1.0)


# ---------------------------------------------------------------- sections

@dataclass
class Section:
    type: int
    id: int
    payload: bytes
    legacy: bool = True


class ModelFile:
    """A legacy-container .model file: ordered sections with u32 ids."""

    def __init__(self, sections: list[Section] | None = None):
        self.sections = list(sections or [])

    # -- container --
    @classmethod
    def read(cls, data: bytes) -> "ModelFile":
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic == 0x42444F44:
            raise ValueError("DODB container not supported (game units are legacy)")
        if magic == 0xFFFFFFFF:
            filesize, count = struct.unpack_from("<II", data, 4)
            off = 12
        else:
            filesize = magic
            count = struct.unpack_from("<I", data, 4)[0]
            off = 8
        if filesize != len(data):
            raise ValueError(f"file size mismatch: header {filesize} actual {len(data)}")
        sections = []
        for _ in range(count):
            typ, sid, sz = struct.unpack_from("<III", data, off)
            off += 12
            sections.append(Section(typ, sid, data[off:off + sz]))
            off += sz
        return cls(sections)

    @classmethod
    def read_path(cls, path) -> "ModelFile":
        return cls.read(open(path, "rb").read())

    def write(self) -> bytes:
        body = bytearray()
        for s in self.sections:
            body += struct.pack("<III", s.type, s.id, len(s.payload))
            body += s.payload
        head = struct.pack("<III", 0xFFFFFFFF, 12 + len(body), len(self.sections))
        return head + bytes(body)

    def by_type(self, typ: int) -> list[Section]:
        return [s for s in self.sections if s.type == typ]

    def by_id(self, sid: int) -> Section:
        for s in self.sections:
            if s.id == sid:
                return s
        raise KeyError(sid)


# ------------------------------------------------------------ payload codecs

def decode_object3d(payload: bytes):
    """Object3D / Model-data common header.

    Returns dict: name_hash, anims [(id, u64)], matrix (16f), pos (3f),
    parent, tail_off (offset where Object3D data ends).
    """
    h, = struct.unpack_from("<Q", payload, 0)
    ac, = struct.unpack_from("<I", payload, 8)
    off = 12
    anims = []
    for _ in range(ac):
        aid, zero = struct.unpack_from("<IQ", payload, off)
        anims.append((aid, zero))
        off += 12
    matrix = struct.unpack_from("<16f", payload, off)
    off += 64
    pos = struct.unpack_from("<fff", payload, off)
    off += 12
    parent, = struct.unpack_from("<I", payload, off)
    off += 4
    return {"name_hash": h, "anims": anims, "matrix": matrix, "pos": pos,
            "parent": parent, "tail_off": off}


def encode_object3d(obj: dict) -> bytes:
    out = bytearray()
    out += struct.pack("<Q", obj["name_hash"])
    out += struct.pack("<I", len(obj.get("anims", [])))
    for aid, zero in obj.get("anims", []):
        out += struct.pack("<IQ", aid, zero)
    out += struct.pack("<16f", *obj["matrix"])
    out += struct.pack("<fff", *obj["pos"])
    out += struct.pack("<I", obj["parent"])
    return bytes(out)


def decode_model_data(payload: bytes) -> dict:
    obj = decode_object3d(payload)
    off = obj["tail_off"]
    ver, = struct.unpack_from("<I", payload, off)
    off += 4
    out = dict(obj)
    out["version"] = ver
    if ver == 6:
        out["bounds_min"] = struct.unpack_from("<fff", payload, off); off += 12
        out["bounds_max"] = struct.unpack_from("<fff", payload, off); off += 12
        out["distance_radius"], out["distance_int"] = struct.unpack_from("<fI", payload, off)
        off += 8
    else:
        (out["passthroughgp"], out["topologyip"]) = struct.unpack_from("<II", payload, off)
        off += 8
        nra, = struct.unpack_from("<I", payload, off)
        off += 4
        out["atoms"] = []
        for _ in range(nra):
            bv, tc, bi, gsl, mid = struct.unpack_from("<5I", payload, off)
            out["atoms"].append({"base_vertex": bv, "tri_count": tc, "base_index": bi,
                                 "slice_len": gsl, "material_id": mid})
            off += 20
        (out["matgroup"], out["lightset"], out["props"]) = struct.unpack_from("<III", payload, off)
        off += 12
        out["bounds_min"] = struct.unpack_from("<fff", payload, off); off += 12
        out["bounds_max"] = struct.unpack_from("<fff", payload, off); off += 12
        out["bounding_radius"], out["bounding_int"] = struct.unpack_from("<fI", payload, off)
        off += 8
        out["skinbones"] = struct.unpack_from("<I", payload, off)[0]
        off += 4
    out["remaining"] = payload[off:]
    return out


def encode_model_data(md: dict) -> bytes:
    out = bytearray(encode_object3d(md))
    out += struct.pack("<I", md["version"])
    if md["version"] == 6:
        out += struct.pack("<fff", *md["bounds_min"])
        out += struct.pack("<fff", *md["bounds_max"])
        out += struct.pack("<fI", md["distance_radius"], md["distance_int"])
    else:
        out += struct.pack("<II", md["passthroughgp"], md["topologyip"])
        out += struct.pack("<I", len(md["atoms"]))
        for a in md["atoms"]:
            out += struct.pack("<5I", a["base_vertex"], a["tri_count"], a["base_index"],
                               a["slice_len"], a["material_id"])
        out += struct.pack("<III", md["matgroup"], md["lightset"], md["props"])
        out += struct.pack("<fff", *md["bounds_min"])
        out += struct.pack("<fff", *md["bounds_max"])
        out += struct.pack("<fI", md["bounding_radius"], md["bounding_int"])
        out += struct.pack("<I", md["skinbones"])
    out += md.get("remaining", b"")
    return bytes(out)


def decode_skinbones(payload: bytes) -> dict:
    off = 0
    n_maps, = struct.unpack_from("<I", payload, off)
    off += 4
    maps = []
    for _ in range(n_maps):
        bc, = struct.unpack_from("<I", payload, off)
        off += 4
        maps.append(list(struct.unpack_from(f"<{bc}I", payload, off)))
        off += 4 * bc
    root, = struct.unpack_from("<I", payload, off)
    off += 4
    n_obj, = struct.unpack_from("<I", payload, off)
    off += 4
    objects = list(struct.unpack_from(f"<{n_obj}I", payload, off))
    off += 4 * n_obj
    rotations = []
    for _ in range(n_obj):
        rotations.append(struct.unpack_from("<16f", payload, off))
        off += 64
    global_mat = struct.unpack_from("<16f", payload, off)
    off += 64
    return {"maps": maps, "root": root, "objects": objects,
            "rotations": rotations, "global": global_mat,
            "remaining": payload[off:]}


def encode_skinbones(sb: dict) -> bytes:
    out = bytearray()
    out += struct.pack("<I", len(sb["maps"]))
    for mp in sb["maps"]:
        out += struct.pack("<I", len(mp))
        out += struct.pack(f"<{len(mp)}I", *mp)
    out += struct.pack("<I", sb["root"])
    out += struct.pack("<I", len(sb["objects"]))
    out += struct.pack(f"<{len(sb['objects'])}I", *sb["objects"])
    for rot in sb["rotations"]:
        out += struct.pack("<16f", *rot)
    out += struct.pack("<16f", *sb["global"])
    out += sb.get("remaining", b"")
    return bytes(out)


def decode_geometry(payload: bytes) -> dict:
    vert_count, header_count = struct.unpack_from("<II", payload, 0)
    off = 8
    headers = []
    for _ in range(header_count):
        item_size, disk_type = struct.unpack_from("<II", payload, off)
        off += 8
        headers.append({"item_size": item_size, "enum_type": to_enum_type(disk_type)})
    chan = {"verts": [], "normals": [], "uv0": [], "blendindices": [],
            "blendweights": [], "uvdir_v": [], "uvdir_u": []}
    for head in headers:
        et = head["enum_type"]
        isz = head["item_size"]
        if et == POSITION0:
            for _ in range(vert_count):
                chan["verts"].append(struct.unpack_from("<fff", payload, off)); off += 12
        elif et == NORMAL0:
            for _ in range(vert_count):
                chan["normals"].append(struct.unpack_from("<fff", payload, off)); off += 12
        elif et == TEXCOORD0:
            for _ in range(vert_count):
                u, v = struct.unpack_from("<ff", payload, off); off += 8
                chan["uv0"].append((u, -v))  # internal V = -disk V (p2mt)
        elif et == UV_DIRECTION_V0:
            for _ in range(vert_count):
                chan["uvdir_v"].append(struct.unpack_from("<fff", payload, off)); off += 12
        elif et == UV_DIRECTION_U0:
            for _ in range(vert_count):
                chan["uvdir_u"].append(struct.unpack_from("<fff", payload, off)); off += 12
        elif et == BLENDINDICES0:
            for _ in range(vert_count):
                chan["blendindices"].append(struct.unpack_from("<4H", payload, off)); off += 8
        elif et == BLENDWEIGHT0:
            n = {2: 2, 3: 3, 4: 4}[isz]
            for _ in range(vert_count):
                w = struct.unpack_from(f"<{n}f", payload, off); off += 4 * n
                w = tuple(w) + (0.0,) * (3 - n) if n < 3 else w[:3]
                chan["blendweights"].append(w)
        else:
            raise ValueError(f"unsupported geometry channel {et} (item size {isz})")
    name_hash, = struct.unpack_from("<Q", payload, off)
    off += 8
    return {"vert_count": vert_count, "headers": headers, "name_hash": name_hash,
            "remaining": payload[off:], **chan}


def encode_geometry(g: dict) -> bytes:
    """Write a legacy geometry section (channel types shifted as p2mt expects)."""
    vert_count = g["vert_count"]
    out = bytearray()
    out += struct.pack("<II", vert_count, len(g["headers"]))
    for head in g["headers"]:
        out += struct.pack("<II", head["item_size"], to_disk_type(head["enum_type"]))
    for head in g["headers"]:
        et = head["enum_type"]
        isz = head["item_size"]
        if et == POSITION0:
            for v in g["verts"]:
                out += struct.pack("<fff", *v)
        elif et == NORMAL0:
            for v in g["normals"]:
                out += struct.pack("<fff", *v)
        elif et == TEXCOORD0:
            for u, v in g["uv0"]:
                out += struct.pack("<ff", u, -v)
        elif et == UV_DIRECTION_V0:
            for v in g["uvdir_v"]:
                out += struct.pack("<fff", *v)
        elif et == UV_DIRECTION_U0:
            for v in g["uvdir_u"]:
                out += struct.pack("<fff", *v)
        elif et == BLENDINDICES0:
            for v in g["blendindices"]:
                out += struct.pack("<4H", *v)
        elif et == BLENDWEIGHT0:
            n = {2: 2, 3: 3, 4: 4}[isz]
            for w in g["blendweights"]:
                out += struct.pack(f"<{n}f", *w[:n])
        else:
            raise ValueError(f"unsupported geometry channel {et}")
    out += struct.pack("<Q", g["name_hash"])
    out += g.get("remaining", b"")
    return bytes(out)


def decode_topology(payload: bytes) -> dict:
    prim, count1 = struct.unpack_from("<II", payload, 0)
    off = 8
    faces = list(struct.unpack_from(f"<{count1}H", payload, off))
    off += 2 * count1
    count2, = struct.unpack_from("<I", payload, off)
    off += 4
    items2 = payload[off:off + count2]
    off += count2
    name_hash, = struct.unpack_from("<Q", payload, off)
    off += 8
    return {"primitive": prim, "indices": faces, "items2": items2,
            "name_hash": name_hash, "remaining": payload[off:]}


def encode_topology(t: dict) -> bytes:
    out = bytearray()
    out += struct.pack("<II", t["primitive"], len(t["indices"]))
    out += struct.pack(f"<{len(t['indices'])}H", *t["indices"])
    out += struct.pack("<I", len(t["items2"]))
    out += t["items2"]
    out += struct.pack("<Q", t["name_hash"])
    out += t.get("remaining", b"")
    return bytes(out)


def decode_material(payload: bytes) -> dict:
    name_hash, = struct.unpack_from("<Q", payload, 0)
    skipped = payload[8:56]
    count, = struct.unpack_from("<I", payload, 56)
    off = 60
    items = []
    for _ in range(count):
        items.append(struct.unpack_from("<II", payload, off))
        off += 8
    return {"name_hash": name_hash, "skipped": skipped, "items": items,
            "remaining": payload[off:]}


def encode_material(m: dict) -> bytes:
    out = bytearray()
    out += struct.pack("<Q", m["name_hash"])
    out += m["skipped"]
    out += struct.pack("<I", len(m["items"]))
    for a, b in m["items"]:
        out += struct.pack("<II", a, b)
    out += m.get("remaining", b"")
    return bytes(out)


def decode_material_group(payload: bytes) -> dict:
    count, = struct.unpack_from("<I", payload, 0)
    ids = list(struct.unpack_from(f"<{count}I", payload, 4))
    return {"material_ids": ids, "remaining": payload[4 + 4 * count:]}


def encode_material_group(g: dict) -> bytes:
    out = bytearray()
    out += struct.pack("<I", len(g["material_ids"]))
    out += struct.pack(f"<{len(g['material_ids'])}I", *g["material_ids"])
    out += g.get("remaining", b"")
    return bytes(out)


def decode_custom_hashlist(payload: bytes) -> dict:
    off = 2  # u16 version marker
    count, = struct.unpack_from("<I", payload, off)
    off += 4
    names = []
    for _ in range(count):
        ln, = struct.unpack_from("<H", payload, off)
        off += 2
        names.append(payload[off:off + ln].decode("utf-8"))
        off += ln
    return {"names": names, "remaining": payload[off:]}


def encode_custom_hashlist(h: dict) -> bytes:
    out = bytearray()
    out += struct.pack("<H", 1)
    out += struct.pack("<I", len(h["names"]))
    for n in h["names"]:
        b = n.encode("utf-8")
        out += struct.pack("<H", len(b))
        out += b
    out += h.get("remaining", b"")
    return bytes(out)


def decode_passthroughgp(payload: bytes) -> dict:
    geo, topo = struct.unpack_from("<II", payload, 0)
    return {"geometry": geo, "topology": topo, "remaining": payload[8:]}


def encode_passthroughgp(p: dict) -> bytes:
    return (struct.pack("<II", p["geometry"], p["topology"])
            + p.get("remaining", b""))


def decode_topologyip(payload: bytes) -> dict:
    topo, = struct.unpack_from("<I", payload, 0)
    return {"topology": topo, "remaining": payload[4:]}


def encode_topologyip(t: dict) -> bytes:
    return struct.pack("<I", t["topology"]) + t.get("remaining", b"")


# ---------------------------------------------------- uv directions (p2mt)

UV_DET_EPS = 1e-8


def compute_uv_directions(verts, uvs, faces):
    """Port of p2mt DieselGeometry.ComputeUvDirections (accumulate + normalize)."""
    acc_u = [[0.0, 0.0, 0.0] for _ in verts]
    acc_v = [[0.0, 0.0, 0.0] for _ in verts]
    for a, b, c in faces:
        e1 = [verts[b][i] - verts[a][i] for i in range(3)]
        e2 = [verts[c][i] - verts[a][i] for i in range(3)]
        uv1 = (uvs[b][0] - uvs[a][0], uvs[b][1] - uvs[a][1])
        uv2 = (uvs[c][0] - uvs[a][0], uvs[c][1] - uvs[a][1])
        det = uv1[0] * uv2[1] - uv2[0] * uv1[1]
        if not (abs(det) > UV_DET_EPS):
            continue
        inv = 1.0 / det
        face_u = [(e1[i] * uv2[1] - e2[i] * uv1[1]) * inv for i in range(3)]
        face_v = [(e1[i] * uv2[0] - e2[i] * uv1[0]) * inv for i in range(3)]
        for idx in (a, b, c):
            for i in range(3):
                acc_u[idx][i] += face_u[i]
                acc_v[idx][i] += face_v[i]

    def norm(v):
        l = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
        return (0.0, 1.0, 0.0) if l < 1e-12 else (v[0] / l, v[1] / l, v[2] / l)

    return ([norm(v) for v in acc_u], [norm(v) for v in acc_v])
