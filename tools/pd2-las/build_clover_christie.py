#!/usr/bin/env python3
"""Experimental Christie BODY_ONLY LAS pack from Clover-Christie.zip.

Consumes only the four named Christie mesh primitives and their embedded PNGs;
never copies the other Clover mesh data. Requires `make -sC tools/pd2-las env`.
The bind pose, materials and glove join need in-game verification.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'pd2-port'))

import numpy as np
from PIL import Image
import build_models as bm
import clover_christie_glb as source
import dds_encode
import determinism
import diesel_model as dm
import las_outfit_pack as lop
import preview_textured as preview
import tmc_las
from build_honoko2_dae import _full_mip_levels

PACK = 'Christie_Clover_LAS'
ITEM = 'clover_christie'
UNIT = f'units/{ITEM}/skins/{ITEM}'
GUI = f'guis/dlcs/{ITEM}/armor_skins'
SLOTS = {name: f'{ITEM}_{i}' for i, name in enumerate(source.MATERIALS)}


def geometry(glb, template):
    doc = glb.doc
    node = next(n for n in doc['nodes'] if 'mesh' in n and doc['meshes'][n['mesh']].get('name') == source.MESH)
    if any(k in node for k in ('matrix', 'translation', 'rotation', 'scale')):
        raise ValueError('mesh node transform needs explicit handling')
    skin = doc['skins'][node['skin']]
    mapping = {str(dm.hash64(name)): name for name in template.name_id}
    names = [mapping.get(doc['nodes'][i]['name']) for i in skin['joints']]
    ibm = glb.accessor(skin['inverseBindMatrices'])
    # The GLB is already bound to the Payday skeleton. Refuse other rigs: a
    # full retarget would be required instead of silently accepting them.
    basis = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1.]])
    errors = {}
    for i, name in enumerate(names):
        if name is None:
            continue
        world = basis @ np.linalg.inv(ibm[i].reshape((4, 4), order='F')) @ basis.T
        point = world[:3, 3] * 100
        dst = np.array(template.worlds[template.name_id[name]][12:15])
        errors[name] = float(np.linalg.norm(point - dst))
    if max(errors.values(), default=float('inf')) > 5:
        raise ValueError('source bind joints differ by more than 5 cm from LAS template; needs retarget')
    group = bm.Group(name='clover_christie_body')
    used = set()
    primitives = doc['meshes'][node['mesh']]['primitives']
    for p in primitives:
        mat = doc['materials'][p['material']]['name']
        a = p['attributes']
        pos = glb.accessor(a['POSITION'])
        normal = glb.accessor(a['NORMAL'])
        uv = glb.accessor(a['TEXCOORD_0'])
        joints = glb.accessor(a['JOINTS_0'])
        weights = glb.accessor(a['WEIGHTS_0'])
        indices = glb.accessor(p['indices']).reshape(-1, 3)
        start = len(group.verts)
        for xyz, n, tex, js, ws in zip(pos, normal, uv, joints, weights):
            group.verts.append((float(xyz[0]*100), float(-xyz[2]*100), float(xyz[1]*100)))
            group.normals.append((float(n[0]), float(-n[2]), float(n[1])))
            group.uvs.append((float(tex[0]), float(1-tex[1])))
            infl = sorted(((names[int(j)], float(w)) for j, w in zip(js, ws) if w > 1e-6), key=lambda v: -v[1])[:3]
            if not infl or any(name is None for name, _ in infl):
                raise ValueError('unmapped weighted joint')
            total = sum(w for _, w in infl)
            infl = [(name, w / total) for name, w in infl]
            used.update(name for name, _ in infl)
            group.weights.append(infl)
        group.faces.extend(tuple(start + int(i) for i in tri) for tri in indices)
        group.slices.append((mat, start, (len(group.faces) - len(indices)) * 3, len(indices), len(pos)))
        group.mat_slots.append(SLOTS[mat])
    group.palette = sorted(used, key=lambda n: template.name_id[n])
    if len(group.palette) > 64:
        raise ValueError('more than 64 weighted bones')
    lookup = {name: i for i, name in enumerate(group.palette)}
    group.weights = [[(lookup[n], w) for n, w in infl] for infl in group.weights]
    cut = tmc_las.cut_group_at_wrists(group, bm.ARM_JOINTS)
    shadow = copy.deepcopy(group)
    shadow.name = 'clover_christie_shadow'
    shadow.mat_slots = ['shadow_caster'] * len(shadow.slices)
    return group, shadow, {'wrist_cut': cut, 'max_joint_distance_cm': max(errors.values())}


def textures(glb):
    doc = glb.doc
    result = {}
    for mat in doc['materials']:
        if mat.get('name') not in SLOTS:
            continue
        slot = SLOTS[mat['name']]
        for kind, ref in [('df', mat['pbrMetallicRoughness']['baseColorTexture']), ('nm', mat['normalTexture'])]:
            image = doc['images'][doc['textures'][ref['index']]['source']]
            im = Image.open(io.BytesIO(glb.view(image['bufferView']))).convert('RGBA')
            if im.width != im.height or im.width & (im.width - 1):
                raise ValueError('expected square power-of-two textures')
            arr = np.array(im, dtype=np.uint8)
            if kind == 'df':
                if mat.get('alphaMode') == 'BLEND':
                    # Diesel uses alpha for both cutout and gloss: 20 is above
                    # alpha_ref=0.05 but avoids an excessively shiny surface.
                    arr[..., 3] = np.where(arr[..., 3] >= 128, 20, 0).astype(np.uint8)
                else:
                    arr[..., 3] = 20
            else:
                arr = np.stack((np.full(arr.shape[:2], 255, np.uint8), 255-arr[..., 1],
                                np.zeros(arr.shape[:2], np.uint8), arr[..., 0]), axis=-1)
            result[f'{slot}_{kind}.texture'] = dds_encode.bc3_dds_from_levels(_full_mip_levels(arr, colour=kind == 'df'))
    return result


def material_config():
    lines = [f'<materials version="3" group="{ITEM}">']
    for name, slot in SLOTS.items():
        masked = name == 'cri_02_05_base'
        shader = ('generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_3WEIGHTS'
                  if masked else 'generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS')
        lines += [f'<material name="{slot}" unique="true" version="2" render_template="{shader}">',
                  f'<diffuse_texture file="{UNIT}/{slot}_df"/>', f'<bump_normal_texture file="{UNIT}/{slot}_nm"/>']
        if masked:
            lines.append('<variable value="0.05" type="scalar" name="alpha_ref"/>')
        else:
            lines += ['<variable value="1 1 1" type="vector3" name="contour_color"/>',
                      '<variable value="0" type="scalar" name="contour_opacity"/>']
        lines.append('</material>')
    lines += ['<material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>', '</materials>']
    return '\n'.join(lines) + '\n'


def build(src: Path, template_path: Path, output: Path):
    determinism.enter(__file__)
    intake = source.inspect(src, template_path)
    with zipfile.ZipFile(src) as z:
        glb = source.Glb(z.read(source.MEMBER))
    template = bm.load_template(template_path)
    body, shadow, fit = geometry(glb, template)
    model = bm.assemble_model(template, {'body': body, 'shadow': shadow},
                              {'g_body': 'body', 'g_body_lod1': 'body', 's_body': 'shadow'},
                              drop_drawables=('g_head', 'g_head_lod1')).write()
    maps = textures(glb)
    with tempfile.TemporaryDirectory(prefix='clover-christie-') as tmp:
        path = Path(tmp) / 'model.model'
        path.write_bytes(model)
        problems = bm.audit_model(path)
        if problems:
            raise ValueError(f'model audit failed: {problems}')
        meshes = preview.material_meshes(path)
        tex = {slot: np.asarray(Image.open(io.BytesIO(maps[f'{slot}_df.texture'])).convert('RGBA'), dtype=np.float32) / 255 for slot in SLOTS.values()}
        sheet = Image.new('RGB', (1024, 256))
        for i, view in enumerate(('front', 'side', 'back', 'threequarter')):
            sheet.paste(preview.render(meshes, tex, view, 256, 1.18, np.array([0., 2., 97.]), flip_v=True, cull=True), (i * 256, 0))
        buf = io.BytesIO()
        sheet.save(buf, format='PNG')
        icon = lop.build_icon(buf.getvalue())
    reg = lop.Registration(item_id=ITEM, display_name='Christie (Clover)',
                           description='Christie outfit, without head or hands. Experimental; not tested in game.',
                           unit=f'{UNIT}/{ITEM}', flags=lop.BODY_ONLY, glove_adapter=True,
                           pairs=tuple(f'{UNIT}/{slot}' for slot in SLOTS.values()))
    files = {
        'main.xml': lop.main_xml(reg).encode(), f'hooks/{ITEM}_las.lua': lop.hook_lua(reg).encode(),
        f'hooks/{ITEM}_glove_adapter.lua': lop.render_glove_adapter_lua(ITEM, PACK).encode(),
        'localization/english.txt': lop.localization(reg).encode(), f'assets/{GUI}/{ITEM}.texture': icon,
        f'assets/{UNIT}/{ITEM}.model': model,
        f'assets/{UNIT}/{ITEM}.unit': lop.render_unit_xml(f'{UNIT}/{ITEM}').encode(),
        f'assets/{UNIT}/{ITEM}.object': lop.render_object_xml(f'{UNIT}/{ITEM}', lop.model_drawables(model)).encode(),
        f'assets/{UNIT}/{ITEM}.material_config': material_config().encode(),
        **{f'assets/{UNIT}/{name}': data for name, data in maps.items()},
    }
    info = {'pack': PACK, 'source_glb_sha256': intake['glb_sha256'], 'source_mesh': source.MESH,
            'runtime_verified': False, 'fps_available': False, 'fit': fit,
            'payload_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['BUILD_INFO.json'] = (json.dumps(info, indent=2, sort_keys=True) + '\n').encode()
    archive = lop.zip_bytes((f'{PACK}/{name}', data) for name, data in sorted(files.items()))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(archive)
    try:
        rel = output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        rel = output.name
    output.with_name(output.name + '.sha256').write_text(f'{hashlib.sha256(archive).hexdigest()}  {rel}\n')
    print(f'wrote {output} ({len(archive)} bytes); not tested in game')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=source.SOURCE)
    parser.add_argument('--template', type=Path, default=source.TEMPLATE)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist/Christie/Christie_Clover_LAS.zip')
    args = parser.parse_args()
    build(args.source, args.template, args.out)


if __name__ == '__main__':
    main()
