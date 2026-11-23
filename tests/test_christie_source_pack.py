"""Contracts of the actual rebuilt Christie LAS ZIP, not a synthetic pack."""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools/pd2-las'), str(ROOT / 'tools/pd2-port')]
import build_models as bm  # noqa: E402
import dds as pd2_dds  # noqa: E402
import diesel_model as dm  # noqa: E402
from extract_2b import MISSING  # noqa: E402
import test_pd2_las_invariants as invariant  # noqa: E402

ZIP = ROOT / 'dist/Christie/Christie_LAS.zip'
BASE = 'Christie_LAS/'


def test_package_registration_textures_and_payload():
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        info = json.loads(z.read(BASE + 'BUILD_INFO.json'))
        assert info['headless'] is True
        assert info['hands'] == 'glove_adapter'
        assert info['runtime_verified'] is False
        assert info['source_zip_sha256'] == hashlib.sha256((ROOT / 'references/Christie.zip').read_bytes()).hexdigest()
        assert all(hashlib.sha256(z.read(BASE + name)).hexdigest() == digest
                   for name, digest in info['payload_sha256'].items())
        hook = z.read(BASE + 'hooks/christie_las.lua').decode()
        adapter = z.read(BASE + 'hooks/christie_glove_adapter.lua').decode()
        main = ET.fromstring(z.read(BASE + 'main.xml'))
        assert 'replace_body = true' in hook and 'replace_all' not in hook
        assert 'fps_replace_body = true' in hook and 'fps_christie' in hook
        assert 'ps.glove_adapter = {}' in adapter
        assert 'ps.body_replacement.hands = false' in adapter
        assert any(e.attrib.get('file') == 'christie_glove_adapter.lua'
                   and e.attrib.get('source_file') == 'lib/tweak_data/blackmarkettweakdata'
                   for e in main.iter('hook'))
        maps = [n for n in z.namelist() if n.endswith(('_df.texture', '_nm.texture'))]
        prefix = BASE + 'assets/units/christie/skins/christie/'
        assert set(maps) == {prefix + f'christie_{role}_{kind}.texture'
                             for role in ('body', 'c02_01', 'c02_02', 'c02_05')
                             for kind in ('df', 'nm')}
        for name in maps:
            data = z.read(name)
            assert not pd2_dds.validate_dxt5_texture(data), name
            size = int.from_bytes(data[16:20], 'little')
            assert int.from_bytes(data[28:32], 'little') == size.bit_length(), name
        for stem in ('christie', 'fps_christie'):
            path = BASE + f'assets/units/christie/skins/christie/{stem}.material_config'
            ET.fromstring(z.read(path))


@pytest.mark.parametrize('stem', ['christie', 'fps_christie'])
def test_visible_lod_and_shadow_have_no_hand_or_distal_wrist(stem):
    model = invariant._model('Christie_LAS', stem)
    assert not {'g_head', 'g_head_lod1'} & model.drawables.keys()
    for name in ('g_body', 'g_body_lod1', 's_body'):
        d = model.drawables[name]
        allowed = {'shadow_caster'} if name == 's_body' else {'mtr_body', 'mtr_c02_01', 'mtr_c02_02', 'mtr_c02_05'}
        assert set(d.materials) <= {dm.hash64(slot) for slot in allowed}
        assert len(d.verts) and len(d.faces)
        weights = np.column_stack((d.weights, 1 - d.weights.sum(axis=1)))
        hand = np.array(['Hand' in name for name in d.palette])
        assert ((weights * hand[d.indices]).sum(axis=1) < 0.5).all(), name
        for side in (-1, 1):
            wrist, elbow = (np.array(p) for p in bm.ARM_JOINTS[side])
            axis = wrist - elbow
            axis /= np.linalg.norm(axis)
            rel = d.verts - wrist
            along = rel @ axis
            radial = np.linalg.norm(rel - np.outer(along, axis), axis=1)
            assert not ((along > 0.001) & (radial < 28)).any(), (name, side)
    # The body material also covers the chest, so scope the bare-skin test to
    # forearm-weighted vertices in the last 6 cm of the wrist axis.
    for name in ('g_body', 'g_body_lod1'):
        drawable = model.drawables[name]
        weights = np.column_stack((drawable.weights, 1 - drawable.weights.sum(axis=1)))
        for atom in drawable.atoms:
            if drawable.materials[atom['material_id']] != dm.hash64('mtr_body'):
                continue
            start = atom['base_index'] // 3
            used = np.unique(drawable.faces[start:start + atom['tri_count']])
            for side, bone in ((-1, 'LeftForeArm'), (1, 'RightForeArm')):
                wrist, elbow = (np.array(p) for p in bm.ARM_JOINTS[side])
                axis = elbow - wrist
                axis /= np.linalg.norm(axis)
                rel = drawable.verts[used] - wrist
                axial = rel @ axis
                radial = np.linalg.norm(rel - np.outer(axial, axis), axis=1)
                influence = (weights[used] * (np.asarray(drawable.palette)[drawable.indices[used]] == bone)).sum(axis=1)
                assert not ((axial >= -0.999) & (axial < 5.999) & (radial < 9.999) & (influence >= 0.251)).any()
    visible, shadow = model.drawables['g_body'], model.drawables['s_body']
    np.testing.assert_allclose(visible.verts, shadow.verts, atol=0)
    np.testing.assert_array_equal(visible.faces, shadow.faces)


def test_real_pack_hooks_with_las_loader():
    harness = pytest.importorskip('test_glove_behavior_lua')
    lua = harness._runtime()
    lua.execute(harness.LUA_HOST)
    lua.execute('register_beardlib_init_gloves()')
    with zipfile.ZipFile(ZIP) as z:
        lua.execute(z.read(BASE + 'hooks/christie_las.lua').decode())
        lua.execute(harness.FIXTURE.read_text())
        lua.execute(z.read(BASE + 'hooks/christie_glove_adapter.lua').decode())
    lua.execute('bm = build_blackmarket(); Hooks:run_init(bm)')
    for local in ('true', 'false'):
        for gloves in ('default', 'bonemittens'):
            state = lua.eval(f"simulate_visual_state('las_christie', '{gloves}', {local}, 'female_1')")
            assert state['char_gloves'] == (harness.HEIST_UNIT if gloves == 'default' else harness.BONE_UNIT)
            assert state['char_glove_adapter'] == harness.ADAPTER_UNIT
            assert state['var_hands_replace'] == 1
        lua.execute("bm.player_styles['las_christie'].default_glove_id = false")
        state = lua.eval(f"simulate_visual_state('las_christie', 'default', {local}, 'female_1')")
        assert state['var_hands_replace'] == 0
        lua.execute("bm.player_styles['las_christie'].default_glove_id = 'heist_default'")


@pytest.mark.parametrize('degrees', [22, 45, 70])
def test_elbow_pose_sweep_has_bounded_edge_growth(degrees):
    # A numeric smoke test, not a visual or in-game clearance test.
    if not all((bm.DEFAULT_TEMPLATES / name).is_file() for name in ('2b.model', 'fps_2b.model')):
        pytest.skip(MISSING)
    import test_render_mesh_skeleton as posing
    rms, tpl, geo, skin = posing._fixtures()
    initial = np.array(geo['verts'])
    faces = np.array(geo['faces'], dtype=int)
    edges = np.linalg.norm(initial[faces] - initial[np.roll(faces, 1, axis=1)], axis=2)
    pose = {side + 'ForeArm': (rms.BEND_AXIS, -degrees) for side in ('Left', 'Right')}
    vertices = rms.skin_verts(geo, skin, rms.posed_worlds(tpl, pose))
    posed_edges = np.linalg.norm(vertices[faces] - vertices[np.roll(faces, 1, axis=1)], axis=2)
    assert np.isfinite(vertices).all()
    assert (posed_edges - edges).max() < 4.0
    assert posed_edges.max() < 15.0
