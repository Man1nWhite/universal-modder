#!/usr/bin/env python3
"""Experimental Christie source retarget and wrist-cut probe; does not build a mod.

Writes two diagnostic Diesel models and fit metrics under build/. The
retarget and cuff/glove fit have not been checked in game. This deliberately does not write to dist/.

Run after `make -sC tools/pd2-las env`:
    .venv/bin/python tools/pd2-las/christie_fit_probe.py
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import build_models as bm
import determinism
import diesel_model as dm
import source_to_obj
import tmc_las

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build' / 'christie-fit-probe'

# Source -> 2B player skeleton, based on the joint names and the prior fit
# study. Head bones inform the torso fit, but head materials are never copied.
BONES = {
    'MOT00_Hips': 'Hips', 'MOT16_Waist': 'Spine', 'MOT02_Chest': 'Spine1',
    'MOT15_Neck': 'Neck', 'MOT01_Head': 'Head',
    'MOT17_LeftShoulder': 'LeftShoulder', 'MOT08_LeftArm': 'LeftArm',
    'MOT04_LeftForeArm': 'LeftForeArm', 'MOT05_LeftHand': 'LeftHand',
    'MOT19_RightShoulder': 'RightShoulder', 'MOT14_RightArm': 'RightArm',
    'MOT10_RightForeArm': 'RightForeArm', 'MOT11_RightHand': 'RightHand',
    'MOT06_LeftUpLeg': 'LeftUpLeg', 'MOT07_LeftLeg': 'LeftLeg',
    'MOT03_LeftFoot': 'LeftFoot', 'MOT18_LeftToe': 'LeftToeBase',
    'MOT12_RightUpLeg': 'RightUpLeg', 'MOT13_RightLeg': 'RightLeg',
    'MOT09_RightFoot': 'RightFoot', 'MOT20_RightToe': 'RightToeBase',
}
for side in ('Left', 'Right'):
    for finger in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'):
        for number in (1, 2, 3):
            BONES[f'OPT_Hand_{side}_{finger}{number}'] = f'{side}Hand{finger}{number}'

SLOTS = dict(zip(source_to_obj.KEEP, ('mtr_body', 'mtr_c02_01', 'mtr_c02_02', 'mtr_c02_05')))
DROP = ('g_head', 'g_head_lod1')


def align_arm_pivots(model, template, skel_map, fits):
    """Translate each arm fit so the source joint lands on the target pivot.

    Preserve the fit's rotation and scale; use the same correction for all
    source helpers resolving to that target, including the finger chain.
    """
    worlds = bm.source_bone_worlds(model)
    corrections = {}
    for side in ('Left', 'Right'):
        for part in ('Arm', 'ForeArm', 'Hand'):
            target = side + part
            idx = next(i for i, bone in enumerate(model.bones)
                       if skel_map['map'].get(bone.name) == target)
            actual = dm.mat_apply_point(fits[idx], worlds[idx][12:15])
            wanted = template.worlds[template.name_id[target]][12:15]
            corrections[target] = tuple(wanted[j] - actual[j] for j in range(3))
    result = dict(fits)
    for idx, matrix in fits.items():
        target = bm._map_source_bone(model, idx, skel_map)
        if target is None:
            continue
        key = target
        if target.startswith(('LeftHand', 'RightHand')):
            key = target[:len('LeftHand')] if target.startswith('LeftHand') else target[:len('RightHand')]
        if key not in corrections:
            continue
        values = list(matrix)
        for j in range(3):
            values[12 + j] += corrections[key][j]
        result[idx] = tuple(values)
    return result


def smooth_elbow_weights(model, skel_map):
    """Blend source upper- and forearm weights around each elbow joint."""
    import numpy as np
    import source_model as sm
    worlds = bm.source_bone_worlds(model)
    indices = {target: i for i, bone in enumerate(model.bones)
               if (target := skel_map['map'].get(bone.name))}
    changed = 0
    for side in ('Left', 'Right'):
        upper, lower = indices[side + 'Arm'], indices[side + 'ForeArm']
        a, b = np.asarray(worlds[upper][12:15]), np.asarray(worlds[lower][12:15])
        axis = b - a
        length = float(np.linalg.norm(axis))
        axis /= length
        for i, vertex in enumerate(model.vertices):
            distance = float(np.dot(np.asarray(vertex.pos) - a, axis)) - length
            if not -4.0 < distance < 3.0:
                continue
            total = sum(weight for bone, weight in vertex.weights if bone in (upper, lower))
            if total < 1e-6:
                continue
            t = (distance + 4.0) / 7.0
            t = t * t * (3 - 2 * t)
            influences = [(bone, weight) for bone, weight in vertex.weights if bone not in (upper, lower)]
            influences.extend(((upper, total * (1 - t)), (lower, total * t)))
            model.vertices[i] = sm.SkinVertex(pos=vertex.pos, normal=vertex.normal, uv=vertex.uv,
                                             weights=tuple(influences))
            changed += 1
    return changed


def remove_hand_weights(group):
    """Remove every triangle touching a vertex dominated by hand bones."""
    import numpy as np
    bad = {v for v, weights in enumerate(group.weights)
           if sum(w for i, w in weights if 'Hand' in group.palette[i]) >= 0.5}
    # Bare wrist skin is owned by the glove/other mod too. The body material
    # also includes torso and chest skin; restrict this cut to vertices driven
    # by the distal forearm near the wrist, never a global x-plane.
    bare_wrist = set()
    for side, target in ((-1, 'LeftForeArm'), (1, 'RightForeArm')):
        wrist, elbow = (np.asarray(p, dtype=float) for p in bm.ARM_JOINTS[side])
        axis = elbow - wrist
        axis /= np.linalg.norm(axis)
        for i, (position, weights) in enumerate(zip(group.verts, group.weights)):
            if sum(w for b, w in weights if group.palette[b] == target) < 0.25:
                continue
            rel = np.asarray(position) - wrist
            axial = float(rel @ axis)
            if -1.0 <= axial < 6.0 and np.linalg.norm(rel - axial * axis) < 10.0:
                bare_wrist.add(i)
    result = bm.Group(name=group.name)
    result.palette = list(group.palette)
    result.rest_worlds = group.rest_worlds
    for slot, (material, base_v, base_i, count, nverts) in zip(group.mat_slots, group.slices):
        faces = [tri for tri in group.faces[base_i // 3:base_i // 3 + count]
                 if not any(v in bad or (material == 'cri_body_base' and v in bare_wrist)
                            for v in tri)]
        if not faces:
            continue
        used = list(dict.fromkeys(v for tri in faces for v in tri))
        if not all(base_v <= v < base_v + nverts for v in used):
            raise ValueError('face escapes its source slice')
        first = len(result.verts)
        remap = {v: first + i for i, v in enumerate(used)}
        result.slices.append((material, first, len(result.faces) * 3, len(faces), len(used)))
        result.mat_slots.append(slot)
        for v in used:
            result.verts.append(group.verts[v])
            result.normals.append(group.normals[v])
            result.uvs.append(group.uvs[v])
            result.weights.append(group.weights[v])
        result.faces.extend(tuple(remap[v] for v in tri) for tri in faces)
    return result


def geometry():
    bm.require_templates(bm.DEFAULT_TEMPLATES, ('2b.model', 'fps_2b.model'))
    model, *_ = source_to_obj.load_source(source_to_obj.DEFAULT_SOURCE, *source_to_obj.MEMBERS)
    template = bm.load_template(bm.DEFAULT_TEMPLATES / '2b.model')
    skel_map = {'map': BONES, 'drop': {'patterns': []}}
    smooth_elbow_weights(model, skel_map)
    fits = align_arm_pivots(model, template, skel_map,
                            bm.retarget_maps(model, skel_map, template))
    spec = {'materials': list(SLOTS), 'out_materials': list(SLOTS.values()), 'mat_slots': SLOTS}
    body = bm.transfer_group(model, spec, skel_map, template, 'body', fits=fits)
    before = len(body.faces)
    cut = tmc_las.cut_group_at_wrists(body, bm.ARM_JOINTS, margin=0.0)
    if not body.faces or not cut['tris_dropped']:
        raise RuntimeError('wrist cut removed no triangles or the whole body')
    body = remove_hand_weights(body)
    # Verify hand-dominated vertices too: a plane alone is not proof that the
    # retargeted fingers lie beyond it. It does not prove a visually clean rim.
    hand = {i for i, n in enumerate(body.palette) if 'Hand' in n}
    hand_dominant = sum(sum(w for i, w in weights if i in hand) >= 0.5 for weights in body.weights)
    if hand_dominant:
        raise RuntimeError(f'{hand_dominant} hand-dominated vertices survived the cut')
    shadow = copy.deepcopy(body)
    shadow.name = 'shadow'
    shadow.mat_slots = ['shadow_caster'] * len(shadow.slices)
    report = {'source_vertices': len(model.vertices), 'source_triangles': model.triangle_count,
              'body_triangles_before_cut': before, 'cut': cut,
              'hand_dominated_vertices': hand_dominant, 'runtime_verified': False, 'models': {}}
    fps_template = bm.load_template(bm.DEFAULT_TEMPLATES / 'fps_2b.model')
    arms = bm.extract_bones(body, bm.is_fps_arm_bone, 'arms')
    arms_shadow = bm.extract_bones(shadow, bm.is_fps_arm_bone, 'shadow')
    return template, fps_template, body, shadow, arms, arms_shadow, report


def build():
    determinism.enter(__file__)
    template, fps_template, body, shadow, arms, arms_shadow, report = geometry()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, tpl, groups, mapping in (
        ('christie', template, {'body': body, 'shadow': shadow},
         {'g_body': 'body', 'g_body_lod1': 'body', 's_body': 'shadow'}),
        ('fps_christie', fps_template, {'arms': arms, 'shadow': arms_shadow},
         {'g_body': 'arms', 'g_body_lod1': 'arms', 's_body': 'shadow'}),
    ):
        path = OUT / (name + '.model')
        path.write_bytes(bm.assemble_model(tpl, groups, mapping, drop_drawables=DROP).write())
        problems = bm.audit_model(path)
        if problems:
            raise RuntimeError('\n'.join(problems))
        report['models'][name] = bm.segment_fit_report(path, tpl)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Experimental models and measurements: {OUT}')


if __name__ == '__main__':
    build()
