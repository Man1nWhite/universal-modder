#!/usr/bin/env python3
"""Build the Clover->Lawson mod_overrides package.

1. PNG -> DDS (DXT5) .texture files under shared_textures/lawson/
2. Patch mtr_fem1(_cc).material_config: repoint the 10 used materials to
   lawson diffuse/bump maps
3. Stage mod_overrides tree with the built .model files
"""
import os, re, shutil, struct
import numpy as np
from PIL import Image

SRC = '/home/user/pd2-work/clover-lawson'
LAW = os.path.join(SRC, 'lawson')
PKG = os.path.join(SRC, 'pkg')          # staging: mod_overrides + zip root
MO = os.path.join(PKG, 'mod_overrides')

# material -> (diffuse png, bump png or None)
TEX = {
    'mtr_enforcer_vest': ('Vixen_d.png',            'Vixen_n.png'),
    'mtr_toolbag':       ('Cri_swimmers_base.png',  'Cri_swimmers_nrm.png'),
    'mtr_vest_small':    ('underwear_d.png',        'underwear_n.png'),
    'mtr_hair_1':        ('Miranda_hair_d.png',     'Miranda_hair_n.png'),
    'mtr_hair_2':        ('Miranda_scalp_d.png',    'hmf_hed_promiranda_scalp_norm.png'),
    'mtr_hair_3':        ('HMF_HED_PROMiranda_Lashes.png', None),
    'mtr_head':          ('Miranda_face_d.png',     'hmf_hed_promiranda_face_norm.png'),
    'mtr_arms':          ('miranda limbs d.png',    'miranda limbs n.png'),
    'mtr_suite_body':    ('miranda body d.png',     'miranda body n.png'),
    'mtr_hands':         ('Miranda_eye_d.png',      'eye_iris_norm.png'),
}

def dds_name(png):
    return re.sub(r'[^A-Za-z0-9_]+', '_', os.path.splitext(png)[0].strip()).strip('_').lower()

# ---------------- DXT5 encoder ----------------
def _rgb565(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def _expand565(v):
    r = ((v >> 11) & 31) * 255 // 31
    g = ((v >> 5) & 63) * 255 // 63
    b = (v & 31) * 255 // 31
    return np.stack([r, g, b], axis=-1).astype(np.int32)

def encode_dxt5(img):
    """img: HxWx4 uint8 -> DXT5 bytes"""
    h, w = img.shape[:2]
    a = img[..., 3].astype(np.int32)
    rgb = img[..., :3].astype(np.int32)
    out = np.zeros((h // 4, w // 4, 16), dtype=np.uint8)
    for by in range(h // 4):
        for bx in range(w // 4):
            pa = a[by*4:by*4+4, bx*4:bx*4+4].reshape(-1)
            pc = rgb[by*4:by*4+4, bx*4:bx*4+4].reshape(-1, 3)
            # ---- alpha block ----
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
            # ---- color block ----
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
    # textbook DDS header for DXT5 (no mips)
    header = struct.pack('<4sI', b'DDS ', 124)
    header += struct.pack('<I', 0x00081007)            # flags: CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE
    header += struct.pack('<I', h)                     # height
    header += struct.pack('<I', w)                     # width
    header += struct.pack('<I', len(data))             # pitch or linear size
    header += struct.pack('<2I', 0, 0)                 # depth, mipmap count
    header += b'\x00' * 44                             # reserved1
    header += struct.pack('<I', 32)                    # pf.dwSize
    header += struct.pack('<I', 0x4)                   # pf.dwFlags = DDPF_FOURCC
    header += struct.pack('<I', 0x35545844)            # pf.dwFourCC = 'DXT5'
    header += struct.pack('<5I', 0, 0, 0, 0, 0)        # bitcount + masks
    header += struct.pack('<5I', 0x1000, 0, 0, 0, 0)   # caps..reserved2
    assert len(header) == 128
    return header + data

def png_to_dds(png_path, dds_path):
    im = Image.open(png_path).convert('RGBA')
    if im.size[0] != im.size[1]:
        # DDS square requirement for DXT: pad to square
        s = max(im.size)
        canvas = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        canvas.paste(im, ((s - im.size[0]) // 2, (s - im.size[1]) // 2))
        im = canvas
    if (im.size[0] & (im.size[0] - 1)) != 0:
        s = 1 << (max(im.size).bit_length())
        canvas = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        canvas.paste(im, (0, 0))
        im = canvas
    arr = np.array(im)
    data = encode_dxt5(arr)
    with open(dds_path, 'wb') as f:
        f.write(data)
    return im.size, len(data)

# ---------------- material config patch ----------------
def patch_config(src, dst, texdir):
    txt = open(src, encoding='utf-8').read()
    for mtr, (dpng, bpng) in TEX.items():
        dpath = texdir + '/' + dds_name(dpng)
        # diffuse
        pat = re.compile(r'(<material\b[^>]*name="' + re.escape(mtr) + r'"[^>]*>)(.*?)(</material>)', re.S)
        def rep(mo):
            body = mo.group(2)
            body = re.sub(r'(<diffuse_texture\s+file=")[^"]*(")',
                          lambda z: z.group(1) + dpath + z.group(2), body)
            if bpng:
                bpath = texdir + '/' + dds_name(bpng)
                body = re.sub(r'(<bump_normal_texture\s+file=")[^"]*(")',
                              lambda z: z.group(1) + bpath + z.group(2), body)
            return mo.group(1) + body + mo.group(3)
        txt, n = pat.subn(rep, txt, count=1)
        if n != 1:
            print(f"  WARN: {os.path.basename(src)}: material {mtr} not matched")
    open(dst, 'w', encoding='utf-8').write(txt)

# ---------------- assemble ----------------
def main():
    if os.path.isdir(PKG):
        shutil.rmtree(PKG)
    tex_out = os.path.join(MO, 'units/payday2/characters/shared_textures/lawson')
    os.makedirs(tex_out, exist_ok=True)
    seen = {}
    for mtr, (dpng, bpng) in TEX.items():
        for png in filter(None, (dpng, bpng)):
            if png in seen:
                continue
            name = dds_name(png)
            size, nbytes = png_to_dds(os.path.join(LAW, png), os.path.join(tex_out, name + '.texture'))
            seen[png] = name
            print(f"  tex {name}.texture {size} {nbytes//1024}KB")

    cfg_out = os.path.join(MO, 'units/payday2/characters/npc_criminal_female_1')
    os.makedirs(cfg_out, exist_ok=True)
    texdir = 'units/payday2/characters/shared_textures/lawson'
    for cfg in ('mtr_fem1.material_config', 'mtr_fem1_cc.material_config'):
        src = os.path.join(SRC, 'clover', cfg)
        if os.path.exists(src):
            patch_config(src, os.path.join(cfg_out, cfg), texdir)
            print(f"  patched {cfg}")

    for m in ('npc_criminal_female_1.model', 'npc_criminal_female_1_menu.model'):
        shutil.copy2(os.path.join(SRC, m), os.path.join(cfg_out, m))
        print(f"  model {m}")

    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(MO) for f in fs)
    print(f"package: {total/1e6:.1f} MB at {MO}")

if __name__ == '__main__':
    main()
