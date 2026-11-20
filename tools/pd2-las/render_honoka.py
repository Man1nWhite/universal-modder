#!/usr/bin/env python3
"""Render multi-stage inspection sheets for Honoka ("Secret Report") across formats.

By default writes to `build/honoka-renders/` (gitignored scratch). Pass `--unified` to
emit into `docs/renders/honoka/<ext>/` per `docs/renders/README.md`:
  - `tmc/`: `honoka_tmc_full_sheet.png`, `honoka_tmc_parts_sheet.png`
  - `dds/`: `honoka_dds_contact_sheet.png`
  - `glb/`: `honoka_glb_sheet.png`

These are the source assets (`.TMC`, the packed `.dds` set, the rigged `.glb`); the
built `Honoko2` pack is rendered by `tools/render_mod_previews.py`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import tmc as tmc_mod  # noqa: E402
from build_honoko2_dae import MAT_TEXTURE_SOURCES, PACKS  # noqa: E402

FONT_BOLD_15 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
FONT_BOLD_12 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
FONT_REG_12 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
FONT_REG_11 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)

TMC_ZIP = REPO / "references" / "Outfit for Honoka-109-1-1-1628020933.zip"
TMC_NAME = "Honoka_DOAXVV_Secret_Report.TMC"
TEX_DIR = REPO / "references" / "Honoka"
GLB_PATH = REPO / "references" / "Honoka" / "Honoka_DOAXVV_Secret_Report.rigged.glb"

# Use the same material and variant mapping that the packs actually build.
ALT_DIFFUSES = {name: f"{spec.pack_dir}: {kind} diffuse override"
                for spec in PACKS for kind, name in spec.tex_override.items()}
DDS_ROLE_NOTES = {
    name: f"{PACKS[0].pack_dir}: {kind} {role}"
    for kind, sources in MAT_TEXTURE_SOURCES.items()
    for name, role in zip(sources, ("diffuse", "normal"))
} | ALT_DIFFUSES


def _load_rasterizer():
    spec = importlib.util.spec_from_file_location(
        "render_mod_previews", REPO / "tools" / "render_mod_previews.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _solid_tex(rgb: tuple[int, int, int]) -> np.ndarray:
    return np.full((16, 16, 4), [*rgb, 255], dtype=np.uint8)


def _tmc_yup_to_diesel_front(pos: np.ndarray, nrm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Map TMC/GLB Y-up cm (front=+Z) -> Z-up cm (front=+Y), det=+1."""
    p = np.stack([-pos[:, 0], pos[:, 2], pos[:, 1]], axis=1).astype(np.float32)
    n = np.stack([-nrm[:, 0], nrm[:, 2], nrm[:, 1]], axis=1).astype(np.float32)
    return p, n


def _header(canvas: Image.Image, title: str, subtitle: str) -> None:
    d = ImageDraw.Draw(canvas)
    W, _ = canvas.size
    d.rectangle([0, 0, W, 56], fill=(16, 19, 26))
    d.line([(0, 56), (W, 56)], fill=(65, 130, 210), width=2)
    d.text((16, 10), title, fill=(245, 248, 255), font=FONT_BOLD_15)
    d.text((16, 33), subtitle, fill=(165, 180, 205), font=FONT_REG_12)


def _label_tile(im: Image.Image, text: str) -> Image.Image:
    d = ImageDraw.Draw(im)
    w, h = im.size
    tw = min(w - 16, max(150, len(text) * 7 + 20))
    d.rectangle([8, h - 30, 8 + tw, h - 8], fill=(14, 17, 24))
    d.text((14, h - 26), text, fill=(232, 238, 248), font=FONT_REG_12)
    return im


def _load_tmc_meshes():
    with zipfile.ZipFile(TMC_ZIP) as zf:
        raw = zf.read(TMC_NAME)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / TMC_NAME
        p.write_bytes(raw)
        return tmc_mod.TmcFile(str(p)).load_meshes()


def render_tmc_sheets(rp, out_dir: Path) -> None:
    meshes = _load_tmc_meshes()
    tex_body = np.asarray(Image.open(TEX_DIR / "L_3.dds").convert("RGBA"))
    tex_jacket = np.asarray(Image.open(TEX_DIR / "L_7.dds").convert("RGBA"))
    tex_skirt = np.asarray(Image.open(TEX_DIR / "L_9.dds").convert("RGBA"))
    tex_map = {
        "WGT_new_aya_body_decl0": tex_body,
        "WGT_cap2": tex_jacket,
        "WGT_headdress2": tex_skirt,
    }

    full_parts = []
    clay_colors = {
        "WGT_new_aya_body_decl0": (205, 178, 162),
        "WGT_cap2": (105, 118, 175),
        "WGT_headdress2": (68, 72, 86),
        "WGT_body_feather": (225, 175, 82),
        "WGT_sweat_chest": (235, 92, 92),
        "WGT_new_aya_body_decl1": (130, 195, 145),
    }

    by_group = {}
    for m in meshes:
        pos, nrm = _tmc_yup_to_diesel_front(
            np.asarray(m.positions, np.float32),
            np.asarray(m.normals, np.float32),
        )
        tris = np.asarray(m.indices, np.int32).reshape(-1, 3)
        uv = np.asarray(m.uvs, np.float32)
        by_group[m.source_id] = (pos, nrm, tris, uv, len(m.positions), len(tris))
        if m.source_id in tex_map:
            # TMC UVs store top-down v directly (pre-transfer_group)
            full_parts.append((pos, nrm, tris, uv, tex_map[m.source_id], False, False))

    # 1. Full TMC textured 4-view sheet (front, 3/4, back, side)
    W_col, H_row = 360, 520
    canvas = Image.new("RGB", (W_col * 4, H_row + 56), (18, 22, 30))
    for i, (deg, lbl) in enumerate([
        (0.0, "TMC Front (0°) — raw hands intact"),
        (34.0, "TMC 3/4 View (34°)"),
        (180.0, "TMC Back (180°)"),
        (90.0, "TMC Side (90°)"),
    ]):
        im = rp.rasterize_parts(full_parts, W_col, H_row, deg, -20.0, 2.95)
        canvas.paste(_label_tile(im, lbl), (i * W_col, 56))
    _header(
        canvas,
        "Honoka Source .TMC — In-Scope Meshes (Textured with L_3 / L_7 / L_9 DDS)",
        f"Source: {TMC_ZIP.name} :: {TMC_NAME} | Y-up m -> Z-up cm; pre-retarget / pre-wrist-cut",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "honoka_tmc_full_sheet.png"
    canvas.save(p1)
    print(f"Saved {p1}")

    # 2. TMC parts breakdown (6 decoded mesh groups in 3x2 grid)
    order = [
        ("WGT_new_aya_body_decl0", "In-scope body"),
        ("WGT_cap2", "In-scope suit jacket"),
        ("WGT_headdress2", "In-scope skirt"),
        ("WGT_body_feather", "Excluded sash slivers"),
        ("WGT_sweat_chest", "Excluded chest emblem"),
        ("WGT_new_aya_body_decl1", "Excluded slab"),
    ]
    W_p, H_p = 420, 440
    parts_sheet = Image.new("RGB", (W_p * 3, H_p * 2 + 56), (18, 22, 30))
    for idx, (gname, note) in enumerate(order):
        pos, nrm, tris, uv, nv, nt = by_group[gname]
        # Flip triangles too if needed: rasterize_parts culls denom <= 0; draw clay single part
        part = [(pos, nrm, tris, uv, _solid_tex(clay_colors[gname]), False, False)]
        z_mid = float((pos[:, 2].min() + pos[:, 2].max()) * 0.5)
        span_z = max(25.0, float(pos[:, 2].max() - pos[:, 2].min()))
        span_x = max(25.0, float(pos[:, 0].max() - pos[:, 0].min()))
        scale = min((H_p - 90) / span_z, (W_p - 60) / span_x, 8.0)
        im = rp.rasterize_parts(part, W_p, H_p, 26.0, z_mid, scale)
        lbl = f"{gname} ({nv}v / {nt}t) — {note}"
        row_i, col_i = divmod(idx, 3)
        parts_sheet.paste(_label_tile(im, lbl), (col_i * W_p, 56 + row_i * H_p))
    _header(
        parts_sheet,
        "Honoka Source .TMC — Decoded Mesh Groups (tmc.py)",
        "All 6 non-placeholder TMC mesh groups with vertex/triangle counts and LAS build scope",
    )
    p2 = out_dir / "honoka_tmc_parts_sheet.png"
    parts_sheet.save(p2)
    print(f"Saved {p2}")


def render_dds_sheet(out_dir: Path) -> None:
    dds_files = sorted(TEX_DIR.glob("L_*.dds"), key=lambda p: int(p.stem.split("_")[1]))
    dds_files += [TEX_DIR / name for name in ALT_DIFFUSES]
    cols, rows = 6, (len(dds_files) + 5) // 6
    tile_w, tile_h = 240, 278
    canvas = Image.new("RGB", (cols * tile_w, rows * tile_h + 56), (18, 22, 30))
    d = ImageDraw.Draw(canvas)

    for idx, path in enumerate(dds_files):
        r, c = divmod(idx, cols)
        x0, y0 = c * tile_w, 56 + r * tile_h
        im = Image.open(path)
        w, h = im.size
        thumb = im.convert("RGB")
        thumb.thumbnail((tile_w - 20, tile_w - 20), Image.Resampling.LANCZOS)
        tx = x0 + (tile_w - thumb.width) // 2
        ty = y0 + 10 + (tile_w - 20 - thumb.height) // 2
        role = DDS_ROLE_NOTES.get(path.name)
        border = (75, 175, 255) if role else (52, 58, 72)
        d.rectangle([x0 + 6, y0 + 6, x0 + tile_w - 6, y0 + tile_h - 6], fill=(24, 28, 38), outline=border, width=2 if role else 1)
        canvas.paste(thumb, (tx, ty))
        d.text((x0 + 12, y0 + tile_w - 4), f"{path.name} ({w}x{h})", fill=(235, 240, 250), font=FONT_BOLD_12)
        d.text(
            (x0 + 12, y0 + tile_w + 15),
            role if role else "unmapped source DDS",
            fill=(115, 210, 255) if role else (140, 150, 170),
            font=FONT_REG_11,
        )

    _header(
        canvas,
        "Honoka Source .DDS Textures — L_0–L_26 and Variant Diffuses",
        f"Source: references/Honoka/ ({len(dds_files)} DXT5 DDS files) | Highlighted tiles are used by the Honoko builds",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "honoka_dds_contact_sheet.png"
    canvas.save(out_path)
    print(f"Saved {out_path}")


def _read_glb_meshes(glb_path: Path) -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray]]:
    raw = glb_path.read_bytes()
    clen, _ = struct.unpack_from("<2I", raw, 12)
    gltf = json.loads(raw[20 : 20 + clen])
    bin_start = 20 + clen + 8
    bin_len, _ = struct.unpack_from("<2I", raw, bin_start - 8)
    buf = raw[bin_start : bin_start + bin_len]

    def read_acc(acc_idx: int) -> np.ndarray:
        acc = gltf["accessors"][acc_idx]
        bv = gltf["bufferViews"][acc["bufferView"]]
        off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        ctype = acc["componentType"]
        dtype = {5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "|u1"}[ctype]
        ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
        stride = bv.get("byteStride")
        count = acc["count"]
        item_bytes = np.dtype(dtype).itemsize * ncomp
        if stride and stride != item_bytes:
            arr = np.frombuffer(buf[off : off + count * stride], dtype=np.uint8).reshape(count, stride)
            return np.frombuffer(arr[:, :item_bytes].tobytes(), dtype=dtype).reshape(count, ncomp)
        data = np.frombuffer(buf[off : off + count * item_bytes], dtype=dtype)
        return data.reshape(count, ncomp) if ncomp > 1 else data

    out = []
    for m in gltf["meshes"]:
        prim = m["primitives"][0]
        pos = read_acc(prim["attributes"]["POSITION"]).astype(np.float32) * np.float32(100.0)
        nrm = read_acc(prim["attributes"]["NORMAL"]).astype(np.float32)
        idx = read_acc(prim["indices"]).astype(np.int32).reshape(-1, 3)
        out.append((m["name"], pos, nrm, idx))
    return out


def render_glb_sheet(rp, out_dir: Path) -> None:
    colors = {
        "TMC_WGT_new_aya_body_decl0": (205, 178, 162),
        "TMC_WGT_cap2": (96, 114, 178),
        "TMC_WGT_headdress2": (56, 62, 78),
        "TMC_WGT_body_feather__unweighted_placeholder": (225, 175, 82),
        "TMC_WGT_sweat_chest": (235, 92, 92),
        "TMC_WGT_new_aya_body_decl1": (130, 195, 145),
    }
    parts = []
    for name, pos_m, nrm_m, tris in _read_glb_meshes(GLB_PATH):
        if "decl1" in name:
            continue  # debug uniform-weight box slab
        pos, nrm = _tmc_yup_to_diesel_front(pos_m, nrm_m)
        uv = np.zeros((len(pos), 2), dtype=np.float32)
        parts.append((pos, nrm, tris, uv, _solid_tex(colors.get(name, (180, 180, 180))), False, False))

    W_col, H_row = 360, 520
    canvas = Image.new("RGB", (W_col * 4, H_row + 56), (18, 22, 30))
    for i, (deg, lbl) in enumerate([
        (0.0, "GLB Front (0°)"),
        (34.0, "GLB 3/4 View (34°)"),
        (180.0, "GLB Back (180°)"),
        (90.0, "GLB Side (90°)"),
    ]):
        im = rp.rasterize_parts(parts, W_col, H_row, deg, -20.0, 2.95)
        canvas.paste(_label_tile(im, lbl), (i * W_col, 56))
    _header(
        canvas,
        "Honoka Rigged .GLB — Exported Mesh Geometry (Color-Coded by Group)",
        f"Source: {GLB_PATH.relative_to(REPO)} | Body (tan), jacket (indigo), skirt (slate), feather (gold)",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "honoka_glb_sheet.png"
    canvas.save(out_path)
    print(f"Saved {out_path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None,
                    help="output root (default: build/honoka-renders, or docs/renders/honoka with --unified)")
    ap.add_argument("--unified", action="store_true",
                    help="write into docs/renders/honoka/<ext>/ per docs/renders/README.md")
    args = ap.parse_args(argv)
    root = args.out or (REPO / "docs" / "renders" / "honoka" if args.unified else REPO / "build" / "honoka-renders")
    root.mkdir(parents=True, exist_ok=True)

    rp = _load_rasterizer()
    render_tmc_sheets(rp, root / "tmc")
    render_dds_sheet(root / "dds")
    render_glb_sheet(rp, root / "glb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
