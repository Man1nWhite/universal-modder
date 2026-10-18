#!/usr/bin/env python3
"""Build mod_overrides packages for the Lawson character swaps.

Usage: build_package2.py clover|bonnie|sydney|all

Per character: DXT5 .texture files (shared lawson path) with full vanilla
mipmap pyramids (see dds.py), material_configs with ADDED lawson_* blocks
(vanilla blocks untouched), and the rebuilt .model pair.
"""
import os, re, shutil, sys
from PIL import Image
from pathlib import Path

import dds
from package_metadata import write_metadata

SRC = '/home/user/pd2-work/clover-lawson'
LAW = os.path.join(SRC, 'lawson')
PKG = os.path.join(SRC, 'pkgs')

# lawson material -> (diffuse png, bump png or None)
TEX = {
    'lawson_outfit': ('Vixen_d.png',           'Vixen_n.png'),
    'lawson_swim':   ('Cri_swimmers_base.png', 'Cri_swimmers_nrm.png'),
    'lawson_under':  ('underwear_d.png',       'underwear_n.png'),
    'lawson_hair':   ('Miranda_hair_d.png',    'Miranda_hair_n.png'),
    'lawson_lashes': ('HMF_HED_PROMiranda_Lashes.png', None),
    'lawson_eyes':   ('Miranda_eye_d.png',     'eye_iris_norm.png'),
    'lawson_limbs':  ('miranda limbs d.png',   'miranda limbs n.png'),
    'lawson_body':   ('miranda body d.png',    'miranda body n.png'),
    'lawson_face':   ('Miranda_face_d.png',    'hmf_hed_promiranda_face_norm.png'),
    'lawson_scalp':  ('Miranda_scalp_d.png',   'hmf_hed_promiranda_scalp_norm.png'),
}
# config-block template material per lawson material
TMPL = {
    'lawson_face': 'mtr_head', 'lawson_scalp': 'mtr_head',
    'lawson_lashes': 'mtr_head', 'lawson_eyes': 'mtr_head',
    'lawson_hair': 'mtr_hair',
    'lawson_body': 'mtr_suite_body', 'lawson_limbs': 'mtr_suite_body',
    'lawson_outfit': 'mtr_suite_body', 'lawson_under': 'mtr_suite_body',
    'lawson_swim': 'mtr_suite_body',
}
CHARS = {
    'clover': dict(
        model='npc_criminal_female_1.model', menu='npc_criminal_female_1_menu.model',
        cfgs=('mtr_fem1.material_config', 'mtr_fem1_cc.material_config'),
        cfg_dir='units/payday2/characters/npc_criminal_female_1'),
    'bonnie': dict(
        model='npc_criminal_bonnie.model', menu='npc_criminal_bonnie_menu.model',
        cfgs=('mtr_bonnie.material_config', 'mtr_bonnie_cc.material_config'),
        cfg_dir='units/pd2_dlc_bonnie/characters/npc_criminal_bonnie'),
    'sydney': dict(
        model='npc_criminal_sydney.model', menu='npc_criminal_sydney_menu.model',
        cfgs=('mtr_criminal_sydney.material_config', 'mtr_criminal_sydney_cc.material_config'),
        cfg_dir='units/pd2_dlc_opera/characters/npc_criminals_fem_3'),
}
# per-character template source folder for the ORIGINAL configs
CFG_SRC_DIR = {'clover': 'clover', 'bonnie': 'Bonie', 'sydney': 'Sydney'}
TEXDIR = 'units/payday2/characters/shared_textures/lawson'

def dds_name(png):
    return re.sub(r'[^A-Za-z0-9_]+', '_', os.path.splitext(png)[0].strip()).strip('_').lower()

# ---------------- DXT5 ----------------
def png_to_dds(png_path, dds_path):
    im = Image.open(png_path).convert('RGBA')
    s = 1
    while s < max(im.size):
        s <<= 1
    if im.size != (s, s):
        canvas = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        canvas.paste(im, (0, 0))
        im = canvas
    payloads = dds.mip_payloads_from_image(im)
    with open(dds_path, 'wb') as f:
        f.write(dds.pack_dds(payloads, s))
    return im.size

# ---------------- config patch: ADD lawson blocks ----------------
def patch_config(src, dst):
    txt = open(src, encoding='utf-8').read()
    blocks = []
    for lm, (dpng, bpng) in TEX.items():
        tmpl_name = TMPL[lm]
        # for hair the template name differs per game config (mtr_hair vs mtr_hair_1)
        pat = re.compile(r'<material\b[^>]*?name="' + re.escape(tmpl_name) + r'"[^>]*?>.*?</material>', re.S)
        mm = pat.search(txt)
        if not mm and tmpl_name == 'mtr_hair':
            pat = re.compile(r'<material\b[^>]*?name="mtr_hair[^"]*"[^>]*?>.*?</material>', re.S)
            mm = pat.search(txt)
        if not mm:
            print(f"  WARN: template {tmpl_name} not in {os.path.basename(src)}")
            continue
        blk = mm.group(0)
        blk = re.sub(r'(<material\b[^>]*?name=")[^"]*(")', lambda z: z.group(1) + lm + z.group(2), blk, count=1)
        dpath = TEXDIR + '/' + dds_name(dpng)
        blk = re.sub(r'(<diffuse_texture\s+file=")[^"]*(")', lambda z: z.group(1) + dpath + z.group(2), blk)
        if bpng:
            bpath = TEXDIR + '/' + dds_name(bpng)
            blk = re.sub(r'(<bump_normal_texture\s+file=")[^"]*(")', lambda z: z.group(1) + bpath + z.group(2), blk)
        blocks.append(blk)
    txt = txt.replace('</materials>', '\n    ' + '\n    '.join(blocks) + '\n</materials>')
    open(dst, 'w', encoding='utf-8').write(txt)
    return len(blocks)

def build_char(char):
    spec = CHARS[char]
    root = os.path.join(PKG, f'lawson_{char}')
    if os.path.isdir(root):
        shutil.rmtree(root)
    tex_out = os.path.join(root, TEXDIR)
    os.makedirs(tex_out, exist_ok=True)
    for mtr, (dpng, bpng) in TEX.items():
        for png in filter(None, (dpng, bpng)):
            name = dds_name(png) + '.texture'
            if not os.path.exists(os.path.join(tex_out, name)):
                png_to_dds(os.path.join(LAW, png), os.path.join(tex_out, name))
    cfg_out = os.path.join(root, spec['cfg_dir'])
    os.makedirs(cfg_out, exist_ok=True)
    for cfg in spec['cfgs']:
        src = os.path.join(SRC, CFG_SRC_DIR[char], cfg)
        n = patch_config(src, os.path.join(cfg_out, cfg))
        print(f"  {char}/{cfg}: +{n} lawson blocks")
    for f in (spec['model'], spec['menu']):
        shutil.copy2(os.path.join(SRC, f), os.path.join(cfg_out, f))
    write_metadata(Path(root), char)
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(root) for f in fs)
    print(f"{char}: {total/1e6:.1f} MB at {root}")

def main():
    chars = sys.argv[1:] or ['all']
    if chars == ['all']:
        chars = ['clover', 'bonnie', 'sydney']
    if os.path.isdir(PKG):
        pass  # keep other characters' trees
    for c in chars:
        build_char(c)

if __name__ == '__main__':
    main()
