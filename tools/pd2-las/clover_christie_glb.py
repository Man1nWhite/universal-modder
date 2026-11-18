#!/usr/bin/env python3
"""Inspect the Christie mesh in Clover-Christie.zip without extracting Clover assets.

Intake and validation module consumed by `build_clover_christie.py`. It reads
the embedded glTF buffers, validates the selected skinned primitives, resolves
Diesel-hashed joint names against the LAS template, and emits a JSON report. No
extracted source data or game assets are written to the repository.

    .venv/bin/python tools/pd2-las/clover_christie_glb.py
    .venv/bin/python tools/pd2-las/clover_christie_glb.py --source archive.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import numpy as np
import build_models as bm
import diesel_model as dm
import extract_2b

ROOT = HERE.parents[1]
SOURCE = ROOT / 'references/Clover-Christie.zip'
TEMPLATE = extract_2b.TEMPLATES / '2b.model'
MEMBER = 'PD2/Clover.glb'
MESH = '6021834874957821078'
MATERIALS = ('cri_02_01_base', 'cri_02_02_base', 'cri_body_base', 'cri_02_05_base')
_COMPONENTS = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
_WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class Glb:
    """A deliberately narrow GLB 2 reader for embedded, nonsparse accessors."""
    def __init__(self, data: bytes):
        if len(data) < 20:
            raise ValueError('truncated GLB header')
        magic, version, total = struct.unpack_from('<4sII', data)
        if magic != b'glTF' or version != 2 or total != len(data):
            raise ValueError('invalid GLB 2 header or length')
        chunks = []
        offset = 12
        while offset < total:
            if offset + 8 > total:
                raise ValueError('truncated GLB chunk header')
            length, kind = struct.unpack_from('<I4s', data, offset)
            offset += 8
            if offset + length > total or length % 4:
                raise ValueError('invalid GLB chunk length')
            chunks.append((kind, data[offset:offset + length]))
            offset += length
        if len(chunks) != 2 or chunks[0][0] != b'JSON' or chunks[1][0] != b'BIN\0':
            raise ValueError('expected one JSON chunk followed by one BIN chunk')
        self.doc = json.loads(chunks[0][1])
        self.bin = chunks[1][1]
        buffers = self.doc.get('buffers', [])
        if len(buffers) != 1 or 'uri' in buffers[0] or buffers[0]['byteLength'] > len(self.bin):
            raise ValueError('expected one embedded buffer')
        self.buffer_length = buffers[0]['byteLength']

    def view(self, index: int) -> memoryview:
        view = self.doc['bufferViews'][index]
        if view.get('buffer', 0) != 0:
            raise ValueError('external buffer view')
        start = view.get('byteOffset', 0)
        end = start + view['byteLength']
        if start < 0 or end > self.buffer_length:
            raise ValueError('buffer view out of bounds')
        return memoryview(self.bin)[start:end]

    def accessor(self, index: int) -> np.ndarray:
        a = self.doc['accessors'][index]
        if 'sparse' in a or 'bufferView' not in a:
            raise ValueError('sparse or missing buffer view unsupported')
        dtype = np.dtype(_COMPONENTS[a['componentType']])
        width = _WIDTH[a['type']]
        count = a['count']
        if count < 0:
            raise ValueError('negative accessor count')
        view = self.doc['bufferViews'][a['bufferView']]
        data = self.view(a['bufferView'])
        stride = view.get('byteStride', dtype.itemsize * width)
        offset = a.get('byteOffset', 0)
        if stride < dtype.itemsize * width or offset < 0 or (count and offset + (count - 1) * stride + dtype.itemsize * width > len(data)):
            raise ValueError('accessor out of bounds or invalid stride')
        result = np.ndarray((count, width), dtype=dtype, buffer=data, offset=offset,
                            strides=(stride, dtype.itemsize)).copy()
        if a.get('normalized'):
            if dtype.kind == 'u':
                result = result.astype(np.float64) / np.iinfo(dtype).max
            elif dtype.kind == 'i':
                result = np.maximum(result.astype(np.float64) / np.iinfo(dtype).max, -1.0)
            else:
                raise ValueError('floating accessor cannot be normalized')
        return result


def inspect(source: Path, template_path: Path) -> dict:
    with zipfile.ZipFile(source) as archive:
        data = archive.read(MEMBER)
    glb = Glb(data)
    doc = glb.doc
    nodes = [n for n in doc['nodes'] if 'mesh' in n and doc['meshes'][n['mesh']].get('name') == MESH]
    if len(nodes) != 1 or 'skin' not in nodes[0]:
        raise ValueError('expected exactly one skinned Christie mesh')
    node = nodes[0]
    mesh = doc['meshes'][node['mesh']]
    skin = doc['skins'][node['skin']]
    template = bm.load_template(template_path)
    by_hash = {str(dm.hash64(name)): name for name in template.name_id}
    joints = [doc['nodes'][i].get('name', '') for i in skin['joints']]
    mapping = [by_hash.get(j) for j in joints]
    results = []
    seen = set()
    for primitive in mesh['primitives']:
        if primitive.get('mode', 4) != 4:
            raise ValueError('non-triangle primitive')
        mat = doc['materials'][primitive['material']]
        name = mat['name']
        if name not in MATERIALS or name in seen:
            raise ValueError(f'unexpected or duplicate material: {name}')
        seen.add(name)
        attrs = primitive['attributes']
        arrays = {key: glb.accessor(attrs[key]) for key in ('POSITION', 'NORMAL', 'TEXCOORD_0', 'JOINTS_0', 'WEIGHTS_0')}
        pos, joints_arr, weights = arrays['POSITION'], arrays['JOINTS_0'], arrays['WEIGHTS_0']
        if any(len(a) != len(pos) for a in arrays.values()) or pos.shape[1] != 3 or joints_arr.shape[1] != 4 or weights.shape[1] != 4:
            raise ValueError(f'invalid attributes for {name}')
        if any(not np.isfinite(a).all() for a in arrays.values()) or np.any(weights < 0):
            raise ValueError(f'invalid weights or coordinates for {name}')
        if (joints_arr.dtype.kind != 'u' or np.any(joints_arr >= len(joints))
                or np.any(np.abs(weights.sum(axis=1) - 1) > 0.001)):
            raise ValueError(f'invalid skin for {name}')
        indices = glb.accessor(primitive['indices']).reshape(-1)
        if indices.dtype.kind != 'u' or len(indices) % 3 or len(indices) == 0 or np.any(indices >= len(pos)):
            raise ValueError(f'invalid triangles for {name}')
        unresolved = sorted({int(j) for j, w in zip(joints_arr.flat, weights.flat) if w > 1e-6 and mapping[int(j)] is None})
        textures = {}
        for kind, ref in [('diffuse', mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')), ('normal', mat.get('normalTexture'))]:
            if ref is None:
                raise ValueError(f'{name} missing {kind} texture')
            image = doc['images'][doc['textures'][ref['index']]['source']]
            if image.get('mimeType') != 'image/png' or 'bufferView' not in image:
                raise ValueError('expected embedded PNG texture')
            payload = glb.view(image['bufferView'])
            if bytes(payload[:8]) != b'\x89PNG\r\n\x1a\n':
                raise ValueError('invalid PNG signature')
            textures[kind] = {'name': image.get('name'), 'sha256': hashlib.sha256(payload).hexdigest()}
        results.append({'material': name, 'vertices': len(pos), 'triangles': len(indices) // 3,
                        'bounds_gltf_m': [pos.min(axis=0).tolist(), pos.max(axis=0).tolist()],
                        'unmapped_weighted_joints': [joints[i] for i in unresolved], 'textures': textures})
    if seen != set(MATERIALS):
        raise ValueError('missing Christie material primitives')
    return {'source': str(source), 'glb_sha256': hashlib.sha256(data).hexdigest(),
            'mesh': MESH, 'skin_joints': len(joints), 'mapped_joints': sum(x is not None for x in mapping),
            'joint_mapping': dict(zip(joints, mapping)), 'primitives': results,
            'status': 'intake_validated'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--template', type=Path, default=TEMPLATE)
    args = parser.parse_args()
    print(json.dumps(inspect(args.source, args.template), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
