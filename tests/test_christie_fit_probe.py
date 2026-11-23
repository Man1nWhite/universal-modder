"""Exercise the Christie geometry and diagnostic command against real inputs."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'pd2-las'))
import build_models as bm  # noqa: E402
from extract_2b import MISSING  # noqa: E402
import las_outfit_pack as lop  # noqa: E402
import diesel_model as dm  # noqa: E402


def test_source_probe_cuts_both_models_without_touching_dist():
    assert (ROOT / 'references/Christie.zip').is_file(), 'tracked Christie source is missing'
    if not all(
        (bm.DEFAULT_TEMPLATES / n).is_file() for n in ('2b.model', 'fps_2b.model')
    ):
        pytest.skip(MISSING)
    subprocess.run([sys.executable, str(ROOT / 'tools/pd2-las/christie_fit_probe.py')],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    out = ROOT / 'build/christie-fit-probe'
    report = json.loads((out / 'report.json').read_text())
    assert report['source_vertices'] == 21979
    assert report['source_triangles'] == 36920
    assert report['cut']['tris_dropped'] > 0
    assert report['hand_dominated_vertices'] == 0
    assert report['runtime_verified'] is False
    for name in ('christie', 'fps_christie'):
        model = out / f'{name}.model'
        assert not bm.audit_model(model)
        drawables = set(lop.model_drawables(model.read_bytes()))
        assert {'g_body', 'g_body_lod1', 's_body'} <= drawables
        assert not {'g_head', 'g_head_lod1'} & drawables

        mf = dm.ModelFile.read(model.read_bytes())
        hashes = {dm.hash64(n): n for n in dm.decode_custom_hashlist(
            mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)['names']}
        names = {}
        for section in mf.sections:
            if section.type == dm.OBJECT3D:
                node = dm.decode_object3d(section.payload)
                names[section.id] = hashes.get(node['name_hash'], '')
            elif section.type == dm.MODEL_DATA:
                node = dm.decode_model_data(section.payload)
                names[section.id] = hashes.get(node['name_hash'], '')
        for section in mf.by_type(dm.MODEL_DATA):
            node = dm.decode_model_data(section.payload)
            if node.get('version') != 3:
                continue
            gp = dm.decode_passthroughgp(mf.by_id(node['passthroughgp']).payload)
            geo = dm.decode_geometry(mf.by_id(gp['geometry']).payload)
            if not geo['blendweights']:
                continue
            skin = dm.decode_skinbones(mf.by_id(node['skinbones']).payload)
            palette = [names.get(b, '') for b in skin['objects']]
            weights = np.asarray(geo['blendweights']).reshape(-1, 3)
            weights = np.column_stack((weights, 1 - weights.sum(axis=1)))
            indices = np.asarray(geo['blendindices'], dtype=int).reshape(-1, 4)
            hand = np.array(['Hand' in name for name in palette])
            assert ((weights * hand[indices]).sum(axis=1) < 0.5).all()
