#!/usr/bin/env python3
"""Build a headless, handless Christie LAS outfit from the DOA5 source archive.

Requires the pinned environment and extracted 2B templates (make -sC
 tools/pd2-las env). Replaces only dist/Christie/Christie_LAS.zip by default;
--dist DIR builds in another directory. Not verified in PAYDAY 2.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'pd2-port'))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
import build_models as bm  # noqa: E402
import christie_fit_probe as fit  # noqa: E402
import christie_sleeve_gloss as sleeve_gloss  # noqa: E402
import dds as pd2_dds  # noqa: E402
import dds_encode as enc  # noqa: E402
import determinism  # noqa: E402
import las_outfit_pack as lop  # noqa: E402
import preview_textured as preview  # noqa: E402
from vtf import parse_vtf, to_dds  # noqa: E402

PACK = 'Christie_LAS'
ITEM = 'christie'
UNIT_DIR = 'units/christie/skins/christie'
GUI_DIR = 'guis/dlcs/christie/armor_skins'
MAT_DIR = 'materials/models/plasmid/doa5/christie/c2/'
ROLES = dict(zip(fit.SLOTS, ('body', 'c02_01', 'c02_02', 'c02_05')))
GLOSS = dict(zip(ROLES, ((0.25, 64), (0.20, 56), (0.18, 48), (0.15, 40))))


def full_mips(data: bytes) -> bytes:
    size, _, mip0 = pd2_dds.dds_mip0_slice(data)
    if size != int.from_bytes(data[12:16], 'little'):
        raise ValueError('expected a square Christie texture')
    corrected, _ = pd2_dds.fix_misordered_blocks(bytes(mip0), size)
    pixels = np.asarray(Image.open(io.BytesIO(data)).convert('RGBA'), dtype=np.uint8)
    payloads = [corrected] + pd2_dds._submip_payloads_from_image(pixels)
    result = pd2_dds.pack_dds(payloads, size)
    problems = pd2_dds.validate_dxt5_texture(result)
    if problems:
        raise ValueError('; '.join(problems))
    return result


def texture_reference(vmt: str, key: str) -> str:
    match = re.search(r'"\$' + key + r'"\s+"([^\"]+)"', vmt, re.I)
    if not match:
        raise ValueError(f'missing ${key} in material')
    return 'materials/' + match.group(1).replace('\\', '/').lower() + '.vtf'


def textures():
    result = {}
    with zipfile.ZipFile(fit.source_to_obj.DEFAULT_SOURCE) as zf:
        for material, role in ROLES.items():
            vmt = zf.read(MAT_DIR + material + '.vmt').decode('latin1')
            diffuse = to_dds(parse_vtf(zf.read(texture_reference(vmt, 'basetexture'))))
            normal = to_dds(parse_vtf(zf.read(texture_reference(vmt, 'bumpmap'))))
            diffuse = enc.attenuate_dxt5_alpha_from_normal(diffuse, normal, *GLOSS[material])
            normal = enc.swizzle_standard_normal_dxt5_to_pd2(normal, invert_y=True)
            result[f'{ITEM}_{role}_df.texture'] = full_mips(diffuse)
            result[f'{ITEM}_{role}_nm.texture'] = full_mips(normal)
    return result


def material_config(slots, fps):
    role_by_slot = {fit.SLOTS[material]: role for material, role in ROLES.items()}
    lines = ['<materials version="3" group="christie">']
    for slot in sorted(set(slots)):
        role = role_by_slot[slot]
        shader = ('DEPTH_SCALING' if fps else 'CONTOUR')
        unique = '' if fps else ' unique="true"'
        lines.append(f'  <material name="{slot}"{unique} version="2" '
                     f'render_template="generic:{shader}:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">')
        lines.append(f'    <diffuse_texture file="{UNIT_DIR}/{ITEM}_{role}_df"/>')
        lines.append(f'    <bump_normal_texture file="{UNIT_DIR}/{ITEM}_{role}_nm"/>')
        if not fps:
            lines.extend(('    <variable value="1 1 1" type="vector3" name="contour_color"/>',
                          '    <variable value="0" type="scalar" name="contour_opacity"/>'))
        lines.append('  </material>')
    lines += ['  <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>',
              '</materials>', '']
    return '\n'.join(lines)


def icon(model: Path, maps: dict[str, bytes]) -> bytes:
    meshes = preview.material_meshes(model)
    textures_by_slot = {fit.SLOTS[material]: np.asarray(
        Image.open(io.BytesIO(maps[f'{ITEM}_{role}_df.texture'])).convert('RGBA'), dtype=np.float32) / 255
        for material, role in ROLES.items()}
    size = 256
    sheet = Image.new('RGB', (4 * size, size))
    for i, view in enumerate(('front', 'side', 'back', 'threequarter')):
        image = preview.render(meshes, textures_by_slot, view, size, 1.18,
                               np.array([0.0, 2.0, 97.0]), flip_v=True, cull=True)
        sheet.paste(image, (i * size, 0))
    data = io.BytesIO()
    sheet.save(data, format='PNG')
    return lop.build_icon(data.getvalue(), view=3)


def build(dist: Path):
    determinism.enter(__file__)
    tpp_tpl, fps_tpl, body, shadow, arms, arm_shadow, report = fit.geometry()
    models = {}
    with tempfile.TemporaryDirectory(prefix='christie-build-', dir=ROOT / 'build') as tmp:
        tmp = Path(tmp)
        for stem, tpl, groups, mapping in (
            ('christie', tpp_tpl, {'body': body, 'shadow': shadow},
             {'g_body': 'body', 'g_body_lod1': 'body', 's_body': 'shadow'}),
            ('fps_christie', fps_tpl, {'arms': arms, 'shadow': arm_shadow},
             {'g_body': 'arms', 'g_body_lod1': 'arms', 's_body': 'shadow'}),
        ):
            raw = bm.assemble_model(tpl, groups, mapping, drop_drawables=fit.DROP).write()
            path = tmp / f'{stem}.model'
            path.write_bytes(raw)
            problems = bm.audit_model(path)
            if problems:
                raise ValueError(f'{stem}: {problems}')
            report['models'][stem] = bm.segment_fit_report(path, tpl)
            models[stem] = raw
        maps = textures()
        # The software icon renderer treats alpha as opacity, not specular;
        # render it from the pre-retouch maps so a gloss change does not alter it.
        menu_icon = icon(tmp / 'christie.model', maps)
        sizes = {role: pd2_dds.dds_mip0_slice(maps[f'{ITEM}_{role}_df.texture'])[0]
                 for role in ROLES.values()}
        masks = sleeve_gloss.masks(body, ROLES, sizes)
        report['sleeve_gloss'] = sleeve_gloss.retouch(maps, masks, pd2_dds, ITEM)
        print('Sleeve gloss blocks:', report['sleeve_gloss'])

    registration = lop.Registration(
        item_id=ITEM, display_name='Christie (DOA5)',
        description='Christie outfit without head or hands; use your heister head and gloves.',
        unit=f'{UNIT_DIR}/christie', fps_unit=f'{UNIT_DIR}/fps_christie',
        flags=lop.BODY_ONLY, glove_adapter=True,
        pairs=tuple(f'{UNIT_DIR}/{ITEM}_{role}' for role in ROLES.values()))
    files = {}
    def add(name, data):
        files[name] = data.encode('utf-8') if isinstance(data, str) else data

    add('main.xml', lop.main_xml(registration))
    add('hooks/christie_las.lua', lop.hook_lua(registration))
    add('hooks/christie_glove_adapter.lua', lop.render_glove_adapter_lua(ITEM, PACK))
    add('localization/english.txt', lop.localization(registration))
    add(f'assets/{GUI_DIR}/christie.texture', menu_icon)
    for name, data in maps.items():
        add(f'assets/{UNIT_DIR}/{name}', data)
    for stem, group in (('christie', body), ('fps_christie', arms)):
        base = f'{UNIT_DIR}/{stem}'
        add(f'assets/{base}.model', models[stem])
        add(f'assets/{base}.unit', lop.render_unit_xml(base))
        add(f'assets/{base}.object', lop.render_object_xml(base, lop.model_drawables(models[stem])))
        add(f'assets/{base}.material_config', material_config(group.mat_slots, stem.startswith('fps_')))
    info = {
        'pack': PACK, 'item_id': ITEM, 'headless': True, 'hands': 'glove_adapter',
        'fps_available': True, 'models_present': True, 'runtime_verified': False,
        'source': 'references/Christie.zip (DOA5 christie_c2)',
        'source_zip_sha256': hashlib.sha256(fit.source_to_obj.DEFAULT_SOURCE.read_bytes()).hexdigest(),
        'registration': {'flags': list(lop.BODY_ONLY), 'table': 'LegendaryArmours.christie',
                         'unit': registration.unit, 'fps_unit': registration.fps_unit,
                         'hook_source': lop.HOOK_SOURCE},
        'fit_probe': report,
        'payload_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    add('BUILD_INFO.json', json.dumps(info, indent=2, sort_keys=True) + '\n')
    archive = lop.zip_bytes((f'{PACK}/{name}', data) for name, data in sorted(files.items()))
    dist.mkdir(parents=True, exist_ok=True)
    path = dist / f'{PACK}.zip'
    path.write_bytes(archive)
    rel = os.path.relpath(path.resolve(), ROOT)
    (dist / f'{PACK}.zip.sha256').write_text(f'{hashlib.sha256(archive).hexdigest()}  {rel}\n')
    print(f'Wrote {path} ({len(archive)} bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist' / 'Christie')
    args = parser.parse_args()
    build(args.dist)


if __name__ == '__main__':
    main()
