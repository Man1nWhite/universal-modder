#!/usr/bin/env python3
"""Diesel .model reader — Python port of the core of diesel-modding/payday2-model-tool.

Reads legacy and Diesel 3 ("DODB") containers. Used by the Clover->Lawson port.
Writer helpers live in build_model.py. Formats per Research Notes/format_documentation.md
in that repo and the C# sources (ModelReader.cs, Sections/*.cs, Hash64.cs).
"""
import struct, sys, json, math
from pathlib import Path

# ---------- idstring hash (port of Hash64.cs, Jenkins lookup3 variant) ----------
M64 = 0xFFFFFFFFFFFFFFFF

def _mix(a, b, c):
    a = (a - b) & M64; a = (a - c) & M64; a = (a ^ (c >> 43)) & M64
    b = (b - c) & M64; b = (b - a) & M64; b = (b ^ ((a << 9) & M64)) & M64
    c = (c - a) & M64; c = (c - b) & M64; c = (c ^ (b >> 8)) & M64
    a = (a - b) & M64; a = (a - c) & M64; a = (a ^ (c >> 38)) & M64
    b = (b - c) & M64; b = (b - a) & M64; b = (b ^ ((a << 23) & M64)) & M64
    c = (c - a) & M64; c = (c - b) & M64; c = (c ^ (b >> 5)) & M64
    a = (a - b) & M64; a = (a - c) & M64; a = (a ^ (c >> 35)) & M64
    b = (b - c) & M64; b = (b - a) & M64; b = (b ^ ((a << 49) & M64)) & M64
    c = (c - a) & M64; c = (c - b) & M64; c = (c ^ (b >> 11)) & M64
    a = (a - b) & M64; a = (a - c) & M64; a = (a ^ (c >> 12)) & M64
    b = (b - c) & M64; b = (b - a) & M64; b = (b ^ ((a << 18) & M64)) & M64
    c = (c - a) & M64; c = (c - b) & M64; c = (c ^ (b >> 22)) & M64
    return a, b, c

def hash64(k: bytes, level=0) -> int:
    a = b = level
    c = 0x9E3779B97F4A7C13
    ln = len(k); i = 0
    while ln - i >= 24:
        a = (a + int.from_bytes(k[i:i+8], 'little')) & M64
        b = (b + int.from_bytes(k[i+8:i+16], 'little')) & M64
        c = (c + int.from_bytes(k[i+16:i+24], 'little')) & M64
        a, b, c = _mix(a, b, c)
        i += 24
    tail = k[i:]
    c = (c + len(k)) & M64
    # tail switch: bytes 16..22 -> c (shift 8*(i-15); c's LSB holds length),
    # 8..15 -> b, 0..7 -> a
    for idx in range(min(len(tail), 23) - 1, -1, -1):
        byte = tail[idx]
        if idx >= 16:   c = (c + (byte << (8 * (idx - 15)))) & M64
        elif idx >= 8:  b = (b + (byte << (8 * (idx - 8)))) & M64
        else:           a = (a + (byte << (8 * idx))) & M64
    a, b, c = _mix(a, b, c)
    return c

def hash_str(s: str) -> int:
    return hash64(s.encode('utf-8'))

class Hashlist:
    def __init__(self, *paths):
        self.by_hash = {}
        for p in paths:
            p = Path(p)
            if not p.exists():
                continue
            for line in p.read_text(errors='replace').splitlines():
                line = line.strip()
                if line:
                    self.by_hash[hash_str(line)] = line
    def name(self, h):
        return self.by_hash.get(h, f"#{h:016x}")

# ---------- little-endian binary reader ----------
class BR:
    def __init__(self, data: bytes):
        self.d = data; self.p = 0
    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]; self.p += 4; return v
    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v
    def u64(self):
        v = struct.unpack_from('<Q', self.d, self.p)[0]; self.p += 8; return v
    def u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]; self.p += 2; return v
    def f32(self):
        v = struct.unpack_from('<f', self.d, self.p)[0]; self.p += 4; return v
    def matrix(self):
        return [self.f32() for _ in range(16)]  # rows of System.Numerics M11..M44
    def vec3(self):
        return (self.f32(), self.f32(), self.f32())
    def bytes(self, n):
        v = self.d[self.p:self.p+n]; self.p += n; return v

# ---------- tags (Utils.cs) ----------
TAGS = {
    0x5DC011B8: 'animation_data', 0x7623C465: 'author', 0x29276B1D: 'material_group',
    0x3C54609C: 'material', 0x0FFCD100: 'object3D', 0x62212D88: 'model_data',
    0x7AB072D3: 'geometry', 0x4C507A13: 'topology', 0xE3A3B1CA: 'passthroughGP',
    0x03B634BD: 'topologyIP', 0x648A206C: 'quatLinearRotCtrl', 0x197345A5: 'quatBezRotCtrl',
    0x65CC1825: 'skinbones', 0x0EB43C77: 'bones', 0xFFA13B80: 'light', 0x33552583: 'lightSet',
    0x26A5128C: 'linearVector3Ctrl', 0x76BF5B66: 'linearFloatCtrl', 0x46BF31A7: 'camera',
    0x7C7844FD: 'custom_hashlist',
}
TAGS_INV = {v: k for k, v in TAGS.items()}

class Section:
    def __init__(self, type_, sid, size, offset):
        self.type, self.id, self.size, self.offset = type_, sid, size, offset
        self.start = offset + 12
        self.end = self.start + size
        self.tag = TAGS.get(type_, f'unknown_{type_:08x}')
        self.obj = None

def read_container(data: bytes):
    br = BR(data)
    magic = br.u32()
    legacy = True; version = None
    if magic == 0x42444F44:          # "DODB" Diesel 3
        legacy = False
        version = br.u32(); filesize = br.u32(); count = br.u32()
    else:
        filesize = br.u32()
        count = br.u32() if magic == 0xFFFFFFFF else magic
    sections = []
    for _ in range(count):
        off = br.p
        t, sid, size = br.u32(), br.u32(), br.u32()
        sec = Section(t, sid, size, off)
        sections.append(sec)
        br.p = sec.end
    return sections, legacy, version, filesize

# ---------- section payloads ----------
class Object3D:
    def parse(self, br: BR, sec: Section, hl: Hashlist, read_remaining=True):
        self.name_hash = br.u64()
        self.name = hl.name(self.name_hash)
        n = br.u32()
        self.anim_ids = [(br.u32(), br.u64()) for _ in range(n)]
        self.matrix = br.matrix()          # 16 floats (System.Numerics rows)
        self.pos = br.vec3()               # overwrites M41..M43 (position)
        self.parent_id = br.u32()
        if read_remaining:
            self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class Model(Object3D):
    def parse(self, br, sec, hl):
        Object3D.parse(self, br, sec, hl, read_remaining=False)
        self.version = br.u32()
        self.render_atoms = []
        if self.version == 6:
            self.bounds_min = br.vec3(); self.bounds_max = br.vec3()
            self.dist_radius = br.f32(); self.dist_int = br.u32()
        else:
            self.passthrough_id = br.u32(); self.topologyip_id = br.u32()
            for _ in range(br.u32()):
                self.render_atoms.append(dict(zip(
                    ('base_vertex','tri_count','base_index','geo_len','material_id'),
                    (br.u32(), br.u32(), br.u32(), br.u32(), br.u32()))))
            self.matgroup_id = br.u32(); self.lightset_id = br.u32()
            self.properties = br.u32()
            self.bounds_min = br.vec3(); self.bounds_max = br.vec3()
            self.bounding_radius = br.f32(); self.bounding_int = br.u32()
            self.skinbones_id = br.u32()
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class Topology:
    def parse(self, br, sec, hl):
        self.primitive = br.u32()
        n_idx = br.u32()
        self.faces = [struct.unpack_from('<3H', br.bytes(6)) for _ in range(n_idx // 3)]
        c2 = br.u32(); self.items2 = br.bytes(c2)
        self.name_hash = br.u64()
        self.name = hl.name(self.name_hash)
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class Material:
    def parse(self, br, sec, hl):
        self.name_hash = br.u64()
        self.name = hl.name(self.name_hash)
        self.skipped = br.bytes(48)
        self.items = [(br.u32(), br.u32()) for _ in range(br.u32())]
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class MaterialGroup:
    def parse(self, br, sec, hl):
        self.items = [br.u32() for _ in range(br.u32())]
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class SkinBones:
    def parse(self, br, sec, hl):
        n_maps = br.u32()
        self.bone_mappings = [[br.u32() for _ in range(br.u32())] for _ in range(n_maps)]
        self.root_bone_id = br.u32()
        self.count = br.u32()
        self.object_ids = [br.u32() for _ in range(self.count)]
        self.rotations = [br.matrix() for _ in range(self.count)]
        self.global_skin_transform = br.matrix()
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class Bones:
    def parse(self, br, sec, hl):
        n_maps = br.u32()
        self.bone_mappings = [[br.u32() for _ in range(br.u32())] for _ in range(n_maps)]
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

class DieselGeometry:
    PAYDAY_SIZES = [0, 4, 8, 12, 16, 4, 4, 8, 4, 4]
    RAID_SIZES = [0, 4, 8, 12, 16, 4, 4, 8, 12, 8]

    def parse(self, br: BR, sec: Section, hl: Hashlist):
        self.vert_count = br.u32()
        hc = br.u32()
        self.headers = [(br.u32(), br.u32()) for _ in range(hc)]  # (item_size, item_type)
        fmt, sizes = 'payday', self.PAYDAY_SIZES
        if any(h[0] == 9 for h in self.headers):
            pay = sum(self.PAYDAY_SIZES[h[0]] for h in self.headers) * self.vert_count + 8
            raid = sum(self.RAID_SIZES[h[0]] for h in self.headers) * self.vert_count + 8
            if (sec.end - br.p) == raid:
                fmt, sizes = 'raid', self.RAID_SIZES
        self.format = fmt
        self.positions, self.normals, self.uvs, self.joints = [], [], [], []
        self.weights3, self.fourth = [], []
        self.packed_vu = []
        n = self.vert_count
        for item_size, item_type in self.headers:
            isz = sizes[item_size]
            if item_type == 1:  # POSITION0
                for _ in range(n): self.positions.append(br.vec3())
            elif item_type in (2, 22, 23, 24, 25):  # NORMAL0, UV dirs
                for _ in range(n):
                    if isz == 12:
                        v = br.vec3()
                    else:  # packed 4 bytes: z,y,x,pad as signed bytes
                        b = br.bytes(4)
                        f = [((x / 255.0) * 2.0 - 1.0) for x in (b[2], b[1], b[0])]
                        v = (f[0], f[1], f[2])
                    if item_type == 2: self.normals.append(v)
                    elif item_type in (22, 24): self.packed_vu.append(v)
            elif item_type in (5, 6):  # COLOR
                for _ in range(n): br.bytes(4)
            elif 7 <= item_type <= 16:  # TEXCOORD 0..9
                uvl = []
                for _ in range(n):
                    if item_size == 9 and fmt != 'raid':
                        u = struct.unpack('<e', br.bytes(2))[0]
                        v = struct.unpack('<e', br.bytes(2))[0]
                    else:
                        u, v = br.f32(), br.f32()
                    uvl.append((u, -v))
                if item_type == 7: self.uvs = uvl
            elif item_type in (17, 18):  # BLENDINDICES
                for _ in range(n):
                    self.joints.append(struct.unpack('<4H', br.bytes(8)))
            elif item_type == 19:  # BLENDWEIGHT0
                for _ in range(n):
                    w = [br.f32() for _ in range(item_size)]
                    if item_size == 4:
                        self.fourth.append(w[3]); w = w[:3]
                    self.weights3.append(tuple(w))
            elif item_type == 20:  # BLENDWEIGHT1 (Vector4)
                for _ in range(n): br.bytes(16)
            elif item_type == 21:  # POINTSIZE0
                for _ in range(n): br.bytes(isz)
        self.name_hash = br.u64()
        self.name = hl.name(self.name_hash)
        self.remaining = br.bytes(sec.end - br.p) if sec.end > br.p else b''

    def weights4(self, i):
        w = list(self.weights3[i])
        if self.fourth: w.append(self.fourth[i])
        s = sum(x for x in w if x == x) or 1.0
        return [max(0.0, min(1.0, (x if x == x else 0.0) / s)) for x in (w + [0, 0, 0, 0])[:4]]

class PassthroughGP:
    def parse(self, br, sec, hl):
        self.geometry_id = br.u32(); self.topology_id = br.u32()

class TopologyIP:
    def parse(self, br, sec, hl):
        self.topology_id = br.u32()

PARSERS = {'object3D': Object3D, 'model_data': Model, 'topology': Topology,
           'material': Material, 'material_group': MaterialGroup,
           'skinbones': SkinBones, 'bones': Bones, 'geometry': DieselGeometry,
           'passthroughGP': PassthroughGP, 'topologyIP': TopologyIP}

class DieselModel:
    def __init__(self, path, hashlist=None):
        self._load(Path(path).read_bytes(), hashlist)

    @classmethod
    def from_bytes(cls, data: bytes, hashlist=None):
        """Same reader, but from memory (a model inside a pack)."""
        self = cls.__new__(cls)
        self._load(data, hashlist)
        return self

    def _load(self, data: bytes, hashlist=None) -> None:
        self.data = data
        self.sections, self.legacy, self.version, self.filesize = read_container(self.data)
        hl = hashlist or Hashlist()
        self.hl = hl
        self.by_id = {}
        for sec in self.sections:
            cls = PARSERS.get(sec.tag)
            if cls:
                br = BR(self.data); br.p = sec.start
                obj = cls(); obj.parse(br, sec, hl); sec.obj = obj
            else:
                sec.obj = None
            self.by_id[sec.id] = sec

    def objects(self):
        return [s for s in self.sections if s.tag in ('object3D', 'model_data')]

    def find_by_name(self, name):
        h = hash_str(name)
        return [s for s in self.objects() if s.obj and s.obj.name_hash == h]

    def world_rows(self):
        """row-vector System.Numerics-style world matrices (translation in cm)."""
        worlds = {}
        kids, roots = {}, []
        objs = self.objects()
        ids = {s.id for s in objs}
        for s in objs:
            p = s.obj.parent_id
            if p in ids and p != s.id:
                kids.setdefault(p, []).append(s)
            else:
                roots.append(s)
        def walk(s, parentM):
            o = s.obj
            M = [list(o.matrix[i*4:(i+1)*4]) for i in range(4)]
            M[3] = [o.pos[0], o.pos[1], o.pos[2], M[3][3]]
            W = mmul(M, parentM) if parentM else M
            worlds[s.id] = W
            for k in kids.get(s.id, []):
                walk(k, W)
        for r in roots:
            walk(r, None)
        return worlds

def mmul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def minv(m):
    """4x4 inverse (row-major)."""
    import copy
    n = [row[:] + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(m)]
    for col in range(4):
        piv = max(range(col, 4), key=lambda r: abs(n[r][col]))
        n[col], n[piv] = n[piv], n[col]
        d = n[col][col] or 1e-12
        n[col] = [x / d for x in n[col]]
        for r in range(4):
            if r != col and n[r][col]:
                f = n[r][col]
                n[r] = [x - f*y for x, y in zip(n[r], n[col])]
    return [row[4:] for row in n]

if __name__ == '__main__':
    model_path = sys.argv[1]
    hl_path = sys.argv[2] if len(sys.argv) > 2 else None
    hl = Hashlist(hl_path) if hl_path else Hashlist()
    m = DieselModel(model_path, hl)
    print(f"container: {'legacy' if m.legacy else f'Diesel3 v{m.version}'}  "
          f"filesize={m.filesize}  sections={len(m.sections)}")
    counts = {}
    for s in m.sections:
        counts[s.tag] = counts.get(s.tag, 0) + 1
    print("section inventory:", ', '.join(f'{k}×{v}' for k, v in sorted(counts.items())))
    for s, depth in m.hierarchy() if hasattr(m, 'hierarchy') else []:
        pass
