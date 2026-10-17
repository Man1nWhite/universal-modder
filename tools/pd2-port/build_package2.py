#!/usr/bin/env python3
"""Build mod_overrides packages for the Lawson character swaps.

Usage: build_package2.py clover|bonnie|sydney|all

Per character: DXT5 .texture files (shared lawson path), material_configs with
ADDED lawson_* blocks (vanilla blocks untouched), and the rebuilt .model pair.
"""
import os, re, shutil, struct, sys
import numpy as np
from PIL import Image

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
def _rgb565(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def _expand565(v):
    r = ((v >> 11) & 31) * 255 // 31
    g = ((v >> 5) & 63) * 255 // 63
    b = (v & 31) * 255 // 31
    return np.stack([r, g, b], axis=-1).astype(np.int32)

def encode_dxt5(img):
    h, w = img.shape[:2]
    a = img[..., 3].astype(np.int32)
    rgb = img[..., :3].astype(np.int32)
    out = np.zeros((h // 4, w // 4, 16), dtype=np.uint8)
    for by in range(h // 4):
        for bx in range(w // 4):
            pa = a[by*4:by*4+4, bx*4:bx*4+4].reshape(-1)
            pc = rgb[by*4:by*4+4, bx*4:bx*4+4].reshape(-1, 3)
            a0 = int(pa.max()); a1 = int(pa.min())
            if a0 == a1:
                ab = bytes([a0, a1]) + b'\x00' * 6
            else:
                pal = np.array([a0, a1,
                                (6*a0+a1)//7, (5*a0+2*a1)//7, (4*a0+3*a1)//7, (3*a0+4*a1)//7,
                                (2*a0+5*a1)//7, (a0+6*a1)//7], dtype=np.int32)
                idx = np.abs(pa[:, None] - pal[None, :]).argmin(axis=1)
                bits = 0
                for i, ix in enumerate(idx):
                    bits |= int(ix) << (3 * i)
                ab = bytes([a0, a1]) + bits.to_bytes(6, 'little')
            s = pc.sum(axis=1)
            c0 = pc[s.argmax()]; c1 = pc[s.argmin()]
            e0 = int(_rgb565(c0.reshape(1, 1, 3))[0, 0]); e1 = int(_rgb565(c1.reshape(1, 1, 3))[0, 0])
            if e0 == e1:
                cb = struct.pack('<HH', e0, e1) + b'\x00' * 4
            else:
                e0c = _expand565(np.array([e0]))[0]
                e1c = _expand565(np.array([e1]))[0]
                pal = np.stack([e0c, e1c, (2*e0c+e1c)//3, (e0c+2*e1c)//3])
                d = pc[:, None, :] - pal[None, :, :]
                idx = (d * d).sum(axis=2).argmin(axis=1)
                bits = 0
                for i, ix in enumerate(idx):
                    bits |= int(ix) << (2 * i)
                cb = struct.pack('<HH', e0, e1) + bits.to_bytes(4, 'little')
            out[by, bx, :8] = np.frombuffer(ab, dtype=np.uint8)
            out[by, bx, 8:] = np.frombuffer(cb, dtype=np.uint8)
    data = out.tobytes()
    header = struct.pack('<4sI', b'DDS ', 124)
    header += struct.pack('<I', 0x00081007)
    header += struct.pack('<2I', h, w)
    header += struct.pack('<I', len(data))
    header += struct.pack('<2I', 0, 0)
    header += b'\x00' * 44
    header += struct.pack('<I', 32)
    header += struct.pack('<I', 0x4)
    header += struct.pack('<I', 0x35545844)
    header += struct.pack('<5I', 0, 0, 0, 0, 0)
    header += struct.pack('<5I', 0x1000, 0, 0, 0, 0)
    assert len(header) == 128
    return header + data

def png_to_dds(png_path, dds_path):
    im = Image.open(png_path).convert('RGBA')
    s = 1
    while s < max(im.size):
        s <<= 1
    if im.size != (s, s):
        canvas = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        canvas.paste(im, (0, 0))
        im = canvas
    with open(dds_path, 'wb') as f:
        f.write(encode_dxt5(np.array(im)))
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
