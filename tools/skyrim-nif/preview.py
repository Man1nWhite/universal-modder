"""Offline previews for the Skyrim outfit source: material contact sheets and
flat-lit orthographic mesh renders.

Both are PNGs written with Pillow; no GPU or Blender required, so the port can
be reviewed from a clean checkout.

    python tools/skyrim-nif/preview.py textures <zip>... --out DIR
    python tools/skyrim-nif/preview.py meshes <nif>...   --out DIR
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nif  # noqa: E402

SHAPE_COLORS = [
    (232, 196, 170), (196, 96, 88), (92, 128, 196), (214, 176, 84),
    (128, 176, 120), (176, 128, 196), (96, 176, 196), (196, 128, 64),
]


# ---------------------------------------------------------------------------
# textures
# ---------------------------------------------------------------------------
def dds_info(data: bytes) -> dict:
    """Parse the DDS header: size and pixel format (fourcc or bit masks)."""
    import struct

    if data[:4] != b"DDS ":
        return {"width": 0, "height": 0, "mips": 0, "format": "not-a-dds", "bytes": len(data)}
    height, width = struct.unpack_from("<II", data, 12)
    mips = struct.unpack_from("<I", data, 28)[0]
    fourcc = data[84:88]
    return {
        "width": width,
        "height": height,
        "mips": mips,
        "format": fourcc.decode("latin1").strip("\x00") or "uncompressed",
        "bytes": len(data),
    }


def collect_textures(zips: list[Path]) -> dict[str, dict]:
    """Index every .dds inside the archives by normalized virtual path.

    Paths are normalized to ``textures/...`` lowercase so a NIF reference and an
    archive member can be compared regardless of case or folder layout.
    """
    index: dict[str, dict] = {}
    for zpath in zips:
        with zipfile.ZipFile(zpath) as zf:
            for info in zf.infolist():
                if not info.filename.lower().endswith(".dds"):
                    continue
                data = zf.read(info)
                parts = info.filename.replace("\\", "/").split("/")
                # strip a leading numeric variant folder ("3/Glasses_diffA.dds")
                virt = "textures/" + "/".join(parts[-2:]).lower()
                entry = dds_info(data)
                entry.update({"archive": zpath.name, "member": info.filename})
                index.setdefault(virt, entry)
    return index


def normalize_ref(ref: str) -> str:
    ref = ref.replace("\\", "/").lower().strip()
    if ref.startswith("textures/"):
        return ref
    return "textures/" + ref


def texture_contact_sheet(paths: list[tuple[str, bytes]], out: Path, cell: int = 256,
                          cols: int = 4) -> None:
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 18)), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:  # font may be missing in a slim container
        font = ImageFont.load_default()
    for i, (name, data) in enumerate(paths):
        try:
            im = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            # a zero-byte / placeholder member: draw a labelled empty cell
            draw.rectangle([(i % cols) * cell + 8, (i // cols) * (cell + 18) + 8,
                            (i % cols) * cell + cell - 8, (i // cols) * (cell + 18) + cell - 8],
                           outline=(80, 80, 90))
            draw.text(((i % cols) * cell + 4, (i // cols) * (cell + 18) + cell + 3),
                      Path(name).name[:38] + " (empty)", fill=(200, 120, 120), font=font)
            continue
        im.thumbnail((cell, cell), Image.LANCZOS)
        x = (i % cols) * cell + (cell - im.width) // 2
        y = (i // cols) * (cell + 18) + (cell - im.height) // 2
        sheet.paste(im, (x, y))
        draw.text(((i % cols) * cell + 4, (i // cols) * (cell + 18) + cell + 3),
                  Path(name).name[:38], fill=(210, 210, 215), font=font)
    sheet.save(out)


# ---------------------------------------------------------------------------
# meshes
# ---------------------------------------------------------------------------
def _project(points: np.ndarray, view: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (2d points, depth) for an orthographic view. World is Z-up."""
    if view == "front":
        return points[:, [0, 2]], -points[:, 1]
    if view == "back":
        return np.stack([-points[:, 0], points[:, 2]], 1), points[:, 1]
    if view == "side":
        return np.stack([-points[:, 1], points[:, 2]], 1), -points[:, 0]
    # three-quarter: rotate 35 degrees around Z
    a = np.deg2rad(35.0)
    c, s = np.cos(a), np.sin(a)
    x = points[:, 0] * c - points[:, 1] * s
    y = points[:, 0] * s + points[:, 1] * c
    return np.stack([x, points[:, 2]], 1), -y


def render(meshes: list[dict], view: str, size: int, scale: float,
           center: np.ndarray) -> Image.Image:
    """Z-buffered flat-shaded render of the given triangle soups."""
    light = np.array([0.35, -0.55, 0.75])
    light /= np.linalg.norm(light)
    img = np.zeros((size, size, 3), np.float32)
    zbuf = np.full((size, size), 1e9, np.float32)
    for mesh in meshes:
        verts = mesh["vertices"]
        tris = mesh["triangles"]
        if verts.size == 0 or tris.size == 0:
            continue
        pts2, depth = _project(verts, view)
        c2, _ = _project(center[None, :], view)
        pts2 = (pts2 - c2[0]) * scale
        pts2[:, 1] *= -1.0                       # image rows grow downwards
        pts2 += size / 2.0
        tri2 = pts2[tris]
        tri_z = depth[tris]
        # face normals in 3d for shading
        v0 = verts[tris[:, 0]]
        v1 = verts[tris[:, 1]]
        v2 = verts[tris[:, 2]]
        n = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.where(ln == 0, 1, ln)
        shade = np.clip(n @ light, 0, 1) * 0.75 + 0.25
        color = np.array(mesh["color"], np.float32) / 255.0
        for t in range(tri2.shape[0]):
            p = tri2[t]
            x0 = max(int(np.floor(p[:, 0].min())), 0)
            x1 = min(int(np.ceil(p[:, 0].max())) + 1, size)
            y0 = max(int(np.floor(p[:, 1].min())), 0)
            y1 = min(int(np.ceil(p[:, 1].max())) + 1, size)
            if x1 <= x0 or y1 <= y0:
                continue
            xs = np.arange(x0, x1, dtype=np.float32) + 0.5
            ys = np.arange(y0, y1, dtype=np.float32) + 0.5
            gx, gy = np.meshgrid(xs, ys)
            ax, ay = p[0]
            bx, by = p[1]
            cx, cy = p[2]
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
            w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not inside.any():
                continue
            z = w0 * tri_z[t, 0] + w1 * tri_z[t, 1] + w2 * tri_z[t, 2]
            sub_z = zbuf[y0:y1, x0:x1]
            mask = inside & (z < sub_z)
            if not mask.any():
                continue
            sub_z[mask] = z[mask]
            sub_img = img[y0:y1, x0:x1]
            sub_img[mask] = color * shade[t]
    out = np.clip(img ** (1 / 2.2) * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def render_nifs(paths: list[Path], out_dir: Path, size: int = 520,
                separate: bool = True, label: str = "") -> list[Path]:
    """Render front/side/back/3-4 views of every NIF and a combined sheet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in paths:
        f = nif.parse(path.read_bytes(), str(path))
        meshes = []
        for i, s in enumerate(f.shapes):
            if s.num_vertices == 0 or s.num_triangles == 0:
                continue
            meshes.append({
                "name": s.name,
                "vertices": s.vertices.astype(np.float64),
                "triangles": s.triangles,
                "color": SHAPE_COLORS[i % len(SHAPE_COLORS)],
            })
        if not meshes:
            continue
        allv = np.concatenate([m["vertices"] for m in meshes])
        lo, hi = allv.min(0), allv.max(0)
        center = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2])
        w2, _ = _project(allv, "front")
        span_x = float(w2[:, 0].max() - w2[:, 0].min())
        span_z = float(hi[2] - lo[2])
        scale = size * 0.88 / max(span_x, span_z, 1e-6)
        views = ["front", "side", "back", "three_quarter"]
        if separate:
            sheet = Image.new("RGB", (size * len(views), size), (18, 18, 22))
            for v, view in enumerate(views):
                sheet.paste(render(meshes, view, size, scale, center), (v * size, 0))
            target = out_dir / f"{label or path.stem}.png"
            sheet.save(target)
            written.append(target)
    return written
