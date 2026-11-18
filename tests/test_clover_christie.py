"""Intake and pack invariants for the Clover-Christie GLB LAS builder."""
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/pd2-las'))
import clover_christie_glb as source  # noqa: E402
import build_clover_christie as builder  # noqa: E402
import build_models as bm  # noqa: E402
from extract_2b import MISSING  # noqa: E402


@pytest.mark.skipif(not source.TEMPLATE.is_file(), reason=MISSING)
def test_intake_selects_only_christie_and_resolves_weighted_bones():
    report = source.inspect(source.SOURCE, source.TEMPLATE)
    assert report['mesh'] == source.MESH
    assert {p['material'] for p in report['primitives']} == set(source.MATERIALS)
    assert all(not p['unmapped_weighted_joints'] for p in report['primitives'])
    assert all(p['vertices'] and p['triangles'] for p in report['primitives'])


def test_glb_rejects_truncation_and_accessor_overrun():
    with zipfile.ZipFile(source.SOURCE) as z:
        raw = z.read(source.MEMBER)
    with pytest.raises(ValueError, match='length'):
        source.Glb(raw[:-1])
    glb = source.Glb(raw)
    glb.doc['accessors'][0]['byteOffset'] = 10**9
    with pytest.raises(ValueError, match='bounds'):
        glb.accessor(0)


def test_glb_interleaved_and_normalized_accessor():
    doc = {'buffers': [{'byteLength': 8}], 'bufferViews': [{'buffer': 0, 'byteLength': 8, 'byteStride': 4}],
           'accessors': [{'bufferView': 0, 'componentType': 5121, 'count': 2, 'type': 'VEC2', 'normalized': True}]}
    js = json.dumps(doc).encode()
    js += b' ' * (-len(js) % 4)
    bin_data = bytes([0, 255, 7, 7, 128, 64, 7, 7])
    data = (struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(bin_data))
            + struct.pack('<I4s', len(js), b'JSON') + js
            + struct.pack('<I4s', len(bin_data), b'BIN\0') + bin_data)
    assert np.allclose(source.Glb(data).accessor(0), [[0, 1], [128 / 255, 64 / 255]])


@pytest.mark.skipif(not source.TEMPLATE.is_file(), reason=MISSING)
def test_geometry_uses_only_christie_materials_and_three_weights():
    with zipfile.ZipFile(source.SOURCE) as z:
        glb = source.Glb(z.read(source.MEMBER))
    group, shadow, fit = builder.geometry(glb, bm.load_template(source.TEMPLATE))
    assert set(group.mat_slots) == set(builder.SLOTS.values())
    assert set(shadow.mat_slots) == {'shadow_caster'}
    assert 0 < fit['max_joint_distance_cm'] < 5
    assert all(len(weights) <= 3 and abs(sum(w for _, w in weights) - 1) < 1e-6 for weights in group.weights)
    assert bm.winding_agreement(group.verts, group.faces, group.normals) > 0.9


def test_pack_registration_and_hashes():
    path = ROOT / 'dist/Christie/Christie_Clover_LAS.zip'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == path.with_name(path.name + '.sha256').read_text().split()[0]
    with zipfile.ZipFile(path) as z:
        prefix = builder.PACK + '/'
        info = json.loads(z.read(prefix + 'BUILD_INFO.json'))
        assert not info['runtime_verified'] and not info['fps_available']
        assert info['source_mesh'] == source.MESH
        for name, digest in info['payload_sha256'].items():
            assert hashlib.sha256(z.read(prefix + name)).hexdigest() == digest
        main = z.read(prefix + 'main.xml').decode()
        hook = z.read(prefix + f'hooks/{builder.ITEM}_las.lua').decode()
        assert 'replace_body = true' in hook and 'replace_all' not in hook and 'fps_unit' not in hook
        for slot in builder.SLOTS.values():
            assert f'{builder.UNIT}/{slot}' in main
        xml = z.read(prefix + f'assets/{builder.UNIT}/{builder.ITEM}.material_config').decode()
        assert 'ALPHA_MASKED' in xml and 'alpha_ref' in xml
