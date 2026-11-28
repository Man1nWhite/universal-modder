#!/usr/bin/env python3
"""Build PAYDAY 2 `mod_overrides` head-replacement mods (3 packs).

The head geometry, atlases and portrait icons these packs share are assembled
from the tracked `Miranda_L4D2_LAS.zip` model; the over Joy/Clover/Bonnie/Sydney
variants the same code used to emit are retired, and so is the ME2 Romance head it
wrote for Hila, once the Romance line went (D83).

1. Hila (`npc_criminals_ecp_female`, from `references/templates/npc_criminals_ecp_female.7z`; no Safe House unit):
   - `dist/Miranda/Miranda_L4D2_over_Hila.zip` (+ `.sha256`)
   This is the one Miranda pack whose eye quadrant is the user's `references/textures/EYE_Diff.png`.
2. Rust (`npc_criminals_punk` + Safe House `npc_criminal_punk_chill`, from `references/characters/Geralt.7z`):
   - `dist/Geralt/Geralt_over_Rust.zip` (+ `.sha256`)
3. Old Hoxton (`npc_criminals_suit_1`, from `references/characters/1581859199_135363.rar` + the game's suit unit):
   - `dist/Arivus/Arivus_over_Hoxton.zip` (+ `.sha256`)

All packages use fixed `2020-01-01 00:00:00` zip timestamps so builds are byte-reproducible.
"""
from __future__ import annotations

import io
import re
import struct
import subprocess
from collections import deque
import sys
import zipfile
from pathlib import Path
import sys as _dist_sys
_dist_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))
from dist_paths import dist_path  # noqa: E402

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
#: Derived archive trees under build/ are reused only while the input archive
#: and all previously extracted files still match their recorded hashes.
EXTRACT_DIR = ROOT / "build" / "head-mods"
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import archive_cache  # noqa: E402
import dds  # noqa: E402
import determinism  # noqa: E402
import diesel_model as dm  # noqa: E402
import las_outfit_pack  # noqa: E402
import me2_dae  # noqa: E402
import source_model as sm  # noqa: E402
from pack_checksum import write_pack_checksum  # noqa: E402
import vtf as vtf_mod  # noqa: E402
import rw_dff as rwd  # noqa: E402


JOY_UNIT_DIR = "units/pd2_dlc_joy/characters/npc_criminals_joy_1"
JOY_ICON_PATH = "guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture"

CLOVER_UNIT_DIR = "units/payday2/characters/npc_criminal_female_1"
CLOVER_TEX_DIR = "units/payday2/characters/shared_textures"
CLOVER_ICON_PATH = "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture"

BONNIE_UNIT_DIR = "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie"
BONNIE_ICON_PATH = "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture"

SYDNEY_UNIT_DIR = "units/pd2_dlc_opera/characters/npc_criminals_fem_3"
SYDNEY_ICON_PATH = "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture"

WILD_UNIT_DIR = "units/pd2_dlc_wild/characters/npc_criminals_wild_1"
WILD_ICON_PATH = "guis/dlcs/wild/textures/pd2/blackmarket/icons/characters/wild.texture"

CHILL_UNIT_DIR = "units/pd2_dlc_chill/characters/shared_character"
FPS_GLOVES_ZIP_PREFIX = "Heister - FPS Gloves in TPS/Heister - FPS Gloves in TPS/"
SUIT_UNIT_DIR = "units/payday2/characters/npc_criminals_suit_1"
SUIT_UNIT_STEM = "npc_criminals_suit_1"
#: the menu model's stem is its own (npc_criminals_suit_menu_1), not <stem>_menu
SUIT_MENU_STEM = "npc_criminals_suit_menu_1"
OLD_HOXTON_ICON_PATH = "guis/textures/pd2/blackmarket/icons/characters/old_hoxton.texture"
OLD_HOXTON_TEX_DIR = "units/payday2/characters/shared_textures"
ARIVUS_ARCHIVE = "1581859199_135363.rar"
# The supplied DDS is an edited Arivus atlas (not vanilla Hoxton UVs).
# The 2026-11-26 retouch `old_hoxton_head_df(1).dds` supersedes the first edit:
# softer brows, one catchlight on the iris instead of two plus the stray wedge,
# and small skin adjustments over the brow, lid, nose and lip rows. Same
# single-level 2048x2048 BC3 layout and the same alpha cutout, so the builder
# still ships its base blocks byte for byte; the earlier bytes stay in git.
ARIVUS_DIFFUSE = ROOT / "references" / "textures" / "old_hoxton_head_df(1).dds"
#: Random4 "Head" bone in the source rig (+x up, +y fwd, +z left), anchored to the
#: PD2 male "Head" bone (Rust/suit rig world). Scale matches crown-to-crown
#: (source head-top 0.8384 -> Rust g_head top z 187.56).
ARIVUS_SCALE = 83.25
ARIVUS_SRC_ANCHOR = (0.5885, 0.0396, -0.0022)
ARIVUS_DST_ANCHOR = (0.0, 5.33, 166.76)

# Hila (the H3H3 collaboration heister, DLC folder `ecp`) is not one of the units in the FPS-gloves
# archive: her heist + menu models, objects and material configs ship in her own reference 7z.
HILA_ARCHIVE = "references/templates/npc_criminals_ecp_female.7z"
HILA_DIR = "npc_criminals_ecp_female"
HILA_UNIT_STEM = "npc_criminal_ecp_female"
HILA_UNIT_DIR = "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female"
HILA_ICON_PATH = "guis/dlcs/ecp/textures/pd2/blackmarket/icons/characters/ecp_female.texture"
#: the supplied eyeball diffuse; magnified about its centre so the iris lands at the radius the
#: synthesized eye uses (r 0.156 of the quadrant in u,v, inside the 0.174 gloss iris disc, an
#: ~11.7 mm iris in a ~30 mm palpebral opening). The factor is measured off the source, not
#: guessed: the 2026-11-15 repaint draws its iris 1.38x larger than the first diffuse, so the
#: factor went 2.8 -> 2.03 to keep the same iris in game (D43).
HILA_EYE_SOURCE = "references/textures/EYE_Diff.png"
HILA_EYE_ZOOM = 2.03


def _ensure_7z(cache: Path, archive: Path, model: Path) -> None:
    if (cache / model).is_file() and archive_cache.current(archive, cache):
        return

    def unpack(path: Path) -> None:
        try:
            import py7zr
        except ImportError:
            subprocess.run(["7z", "x", "-y", f"-o{path}", str(archive)], check=True)
        else:
            with py7zr.SevenZipFile(archive, mode="r") as z:
                z.extractall(path=path)

    archive_cache.refresh(archive, cache, unpack, (model,))


def ensure_ada_reference(tmp_dir: Path) -> Path:
    ada = Path("Ada Wong over Joy")
    _ensure_7z(tmp_dir, ROOT / "references" / "templates" / "Ada Wong over Joy.7z",
               ada / JOY_UNIT_DIR / "npc_criminal_joy_1.model")
    return tmp_dir / ada


def ensure_me2_extracted(tmp_dir: Path) -> Path:
    archive = ROOT / "references" / "characters" / "PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"
    dae = "Miranda Lawson (Romance) - Adjusted Version.dae"
    if (tmp_dir / dae).is_file() and archive_cache.current(archive, tmp_dir):
        return tmp_dir

    def unpack(path: Path) -> None:
        with zipfile.ZipFile(archive) as source:
            source.extractall(path)
        nested = path / "Miranda Lawson (Romance)"
        if nested.is_dir():
            for member in nested.iterdir():
                target = path / member.name
                if not target.exists():
                    member.rename(target)

    archive_cache.refresh(archive, tmp_dir, unpack, (dae,))
    return tmp_dir


def ensure_hila_extracted(tmp_dir: Path) -> Path:
    _ensure_7z(tmp_dir, ROOT / HILA_ARCHIVE, Path(HILA_DIR) / f"{HILA_UNIT_STEM}.model")
    return tmp_dir / HILA_DIR


def ensure_geralt_extracted(tmp_dir: Path) -> Path:
    geralt = Path("1259069870")
    _ensure_7z(tmp_dir, ROOT / "references" / "characters" / "Geralt.7z", geralt / "models/survivors/survivor_gambler.mdl")
    return tmp_dir / geralt


def _ensure_rar(cache: Path, archive: Path, model: Path) -> None:
    if (cache / model).is_file() and archive_cache.current(archive, cache):
        return

    def unpack(path: Path) -> None:
        rwd.extract_rar(archive, path)

    archive_cache.refresh(archive, cache, unpack, (model,))


def ensure_arivus_extracted(tmp_dir: Path) -> Path:
    """Unpack `references/characters/1581859199_135363.rar` (Random4 GTA SA RenderWare ped)."""
    _ensure_rar(tmp_dir, ROOT / "references" / "characters" / ARIVUS_ARCHIVE, Path("Random4.dff"))
    return tmp_dir


def ensure_suit_reference(tmp_dir: Path) -> Path:
    """Unpack the vanilla Old Hoxton suit unit (`npc_criminals_suit_1`).

    The shared suit model carries every suit heister's head as its own drawable
    (`g_head_old_hoxton` among them), so a head replacement needs the vanilla
    `npc_criminals_suit_1.model` / `npc_criminals_suit_1_menu.model`. They are
    game assets: extract `units/payday2/characters/npc_criminals_suit_1/` with
    DieselBundleViewer (open `assets/bundle_db_blb`) and drop the folder (zipped
    or bare) under `references/`. The Hila precedent is
    `references/templates/npc_criminals_ecp_female.7z`.
    """
    want = f"{SUIT_UNIT_STEM}.model"
    for archive in sorted((ROOT / "references").rglob("*")):
        if archive.suffix.lower() not in (".zip", ".7z") or not archive.is_file():
            continue
        try:
            if archive.suffix.lower() == ".zip":
                names = zipfile.ZipFile(archive).namelist()
                unpack_names = names
            else:
                import py7zr

                with py7zr.SevenZipFile(archive, mode="r") as z:
                    unpack_names = z.getnames()
        except Exception:
            continue
        hit = [n for n in unpack_names if n.replace("\\", "/").endswith((f"characters/{SUIT_UNIT_STEM}/{want}", f"{SUIT_UNIT_STEM}/{want}"))]
        if not hit:
            continue
        marker = Path(hit[0])
        if archive.suffix.lower() == ".zip":
            def unpack(path: Path, _archive=archive) -> None:
                with zipfile.ZipFile(_archive) as source:
                    source.extractall(path)
            archive_cache.refresh(archive, tmp_dir, unpack, (marker,))
        else:
            _ensure_7z(tmp_dir, archive, marker)
        found = _find_named(tmp_dir, want)
        if found is not None:
            return found.parent
    raise FileNotFoundError(
        "no archive under references/ contains units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_1.model; "
        "extract that folder from the game with DieselBundleViewer and add it to references/templates/"
    )


def _find_named(root: Path, name: str) -> Path | None:
    hits = sorted(p for p in root.rglob(name) if p.is_file())
    return hits[0] if hits else None


def smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def compute_joy_head_weights(
    verts: np.ndarray, bone_offset: int = 0, jaw_lift: float = 3.0
) -> tuple[list[tuple[int, ...]], list[tuple[float, ...]]]:
    """Compute continuous 3-bone weights on ['Spine2', 'Neck', 'Head'] (+ optional bone_offset).

    - When bone_offset == 0 (Joy): palette is ['Spine2', 'Neck', 'Head'] -> indices (0, 1, 2).
    - When bone_offset == 1 (Clover, Bonnie, Sydney, Rust): palette starts with ['Hips', 'Spine2', 'Neck', 'Head', ...]
      -> active indices are (1, 2, 3).
    """
    z = verts[:, 2]
    y = verts[:, 1]
    # Front chin/jaw transitions to Head earlier so the jaw/beard is 100% rigid with Head.
    y0 = 9.5 if jaw_lift <= 3.0 else 6.5
    z_eff = z + jaw_lift * np.clip((y - y0) / 4.5, 0.0, 1.0)

    u1 = smoothstep((z_eff - 156.0) / 5.5)
    u2 = smoothstep((z_eff - 161.5) / 4.5)

    w_spine2 = 1.0 - u1
    w_neck = u1 * (1.0 - u2)
    w_head = u1 * u2

    W = np.stack([w_spine2, w_neck, w_head], axis=1)
    W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-8)

    pal_idx: list[tuple[int, ...]] = []
    pal_w: list[tuple[float, ...]] = []
    for row in W:
        order = np.argsort(-row)
        i0, i1, i2 = int(order[0]) + bone_offset, int(order[1]) + bone_offset, int(order[2]) + bone_offset
        w0, w1, w2 = float(row[order[0]]), float(row[order[1]]), float(row[order[2]])
        s = w0 + w1 + w2
        if s > 0:
            w0, w1, w2 = w0 / s, w1 / s, w2 / s
        else:
            i0, i1, i2 = 2 + bone_offset, 0, 0
            w0, w1, w2 = 1.0, 0.0, 0.0
        if w1 < 1e-5:
            i1 = 0
            w1 = 0.0
        if w2 < 1e-5:
            i2 = 0
            w2 = 0.0
        pal_idx.append((i0, i1, i2, 0))
        pal_w.append((w0, w1, w2))
    return pal_idx, pal_w


def encode_rgba_dds(arr: np.ndarray) -> bytes:
    """Encode a square (N, N, 4) uint8 RGBA array into a mipmapped DXT5 DDS."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    size = int(arr.shape[0])
    assert arr.shape == (size, size, 4), f"Expected square RGBA array, got {arr.shape}"
    return dds.pack_dds(dds.mip_payloads_from_image(arr), size)


def encode_cutout_head_df_dds(arr: np.ndarray, base_payload: bytes | None = None) -> bytes:
    """Encode a head atlas with coverage-preserving cutout mips.

    A supplied BC3 base level can be preserved verbatim while lower levels are
    built from its decoded pixels, avoiding a lossy second compression.
    """
    cur = np.ascontiguousarray(arr, dtype=np.uint8)
    size = int(cur.shape[0])
    if base_payload is not None and len(base_payload) != ((size + 3) // 4) ** 2 * 16:
        raise ValueError("invalid BC3 base level size")
    w, h = size, size
    payloads: list[bytes] = []
    while True:
        payloads.append(base_payload if not payloads and base_payload is not None else dds._level_payload(cur))
        if w == 1 and h == 1:
            break
        nxt = dds.downsample2x2(cur)
        nh, nw = nxt.shape[0], nxt.shape[1]
        if nh >= 2 and h >= 4:
            nxt[: nh // 2, :, 3] = np.maximum(nxt[: nh // 2, :, 3], 18)
            cur_bot = cur[h // 2 :, :, :].reshape(nh // 2, 2, nw, 2, 4).astype(np.float32)
            w_a = (cur_bot[..., 3:4] > 0).astype(np.float32)
            w_sum = w_a.sum(axis=(1, 3))
            rgb_bot = np.where(
                w_sum > 0,
                (cur_bot[..., :3] * w_a).sum(axis=(1, 3)) / np.maximum(w_sum, 1.0),
                nxt[nh // 2 :, :, :3],
            )
            nxt[nh // 2 :, :, :3] = np.clip(np.round(rgb_bot), 0, 255).astype(np.uint8)
            a_mean = cur_bot[..., 3].mean(axis=(1, 3))
            nxt[nh // 2 :, :, 3] = np.where(a_mean >= 6.0, 24, 0).astype(np.uint8)
        else:
            nxt[:, :, 3] = np.maximum(nxt[:, :, 3], 18)
        cur = nxt
        w, h = nw, nh
    return dds.pack_dds(payloads, size)


def neck_skin_uv_island_mask(uv_img: np.ndarray, tris: np.ndarray | None = None) -> np.ndarray:
    """Select the exact Scalp_Diff neck-skin UV island (u in [0.005, 0.743], v_img in [0.737, 0.995])."""
    if tris is not None and len(tris) > 0:
        rounded = np.round(uv_img * 1000.0).astype(np.int64)
        _, inv = np.unique(rounded, axis=0, return_inverse=True)
        parent = list(range(int(inv.max()) + 1))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b, c in tris:
            ra, rb, rc = find(int(inv[a])), find(int(inv[b])), find(int(inv[c]))
            parent[rb] = ra
            parent[rc] = ra
        roots = np.array([find(int(inv[i])) for i in range(len(uv_img))])
        seed_mask = (uv_img[:, 0] < 0.45) & (uv_img[:, 1] > 0.85)
        seed_roots = set(roots[seed_mask].tolist())
        return np.isin(roots, list(seed_roots))
    return (uv_img[:, 0] < 0.75) & (uv_img[:, 1] > 0.82)


def tuck_hair_for_joy_hood(
    p: np.ndarray, uv_img: np.ndarray | None = None, tris: np.ndarray | None = None
) -> np.ndarray:
    """Smoothly tuck lower hair inside Joy's collar while keeping low front locks behind the throat skin."""
    p = p.copy()
    is_hair = np.ones(len(p), dtype=bool)
    if uv_img is not None:
        is_hair = ~neck_skin_uv_island_mask(uv_img, tris)
    if not is_hair.any():
        return p
    zh, yh, xh = p[is_hair, 2], p[is_hair, 1], p[is_hair, 0]
    wz = np.clip((163.8 - zh) / 7.5, 0.0, 1.0)
    if (wz > 0).any():
        dx, dy = xh - 0.0, yh - 2.0
        r = np.hypot(dx, dy) + 1e-6
        r_target = np.minimum(r, 4.8 + (1.0 - wz) * 2.4)
        scale_r = (r * (1.0 - wz) + r_target * wz) / r
        x_new = dx * scale_r
        y_new = 2.0 + dy * scale_r
        w_front_tuck = np.clip((164.0 - zh) / 2.2, 0.0, 1.0)
        y_max_allowed = 4.2 * (1.0 - 0.3 * wz)
        y_new = y_new * (1.0 - w_front_tuck) + np.minimum(y_new, y_max_allowed) * w_front_tuck
        p[is_hair, 0] = x_new
        p[is_hair, 1] = y_new
    return p


def extend_scalp_neck_skin_into_collar(
    p: np.ndarray,
    uv_img: np.ndarray,
    z_drop: float = 3.8,
    y_push: float = 2.2,
    tris: np.ndarray | None = None,
) -> np.ndarray:
    """Smoothly extend the bottom rim of the Scalp_Diff neck-skin cylinder
    down into Joy's collar channel (z ~ 153cm, y ~ 9.2..10.4cm) so the entire throat is a single
    seamless mesh with zero horizontal seam."""
    p = p.copy()
    is_neck_skin = neck_skin_uv_island_mask(uv_img, tris)
    if not is_neck_skin.any():
        return p
    z = p[is_neck_skin, 2]
    y = p[is_neck_skin, 1]
    x = p[is_neck_skin, 0]

    w_bot = np.clip((161.0 - z) / 4.2, 0.0, 1.0)
    w_front = np.clip((y - 3.5) / 3.0, 0.0, 1.0)

    z_new = z - z_drop * (w_bot ** 1.15)
    y_new = y + y_push * w_bot * w_front

    # Keep lower rim strictly inside Joy's outer collar (y <= 10.6, |x| <= 6.2)
    low = z_new < 156.0
    if low.any():
        t_z = np.clip((156.0 - z_new[low]) / 4.5, 0.0, 1.0)
        y_cap = 10.5 + (1.0 - t_z) * 1.5
        y_new[low] = np.minimum(y_new[low], y_cap)
        x_cap = 6.0 + (1.0 - t_z) * 2.2
        x[low] = np.clip(x[low], -x_cap, x_cap)

    p[is_neck_skin, 0] = x
    p[is_neck_skin, 1] = y_new
    p[is_neck_skin, 2] = z_new
    return p


def shape_neck_and_hair_for_suit_collar(
    p: np.ndarray,
    uv_img: np.ndarray,
    z_drop: float = 5.4,
    y_push: float = 3.0,
    x_flare: float = 0.28,
    tris: np.ndarray | None = None,
) -> np.ndarray:
    """Shape the Scalp_Diff neck-skin cylinder and lower hair for Clover, Bonnie, and Sydney's suit collars."""
    p = p.copy()
    is_neck_skin = neck_skin_uv_island_mask(uv_img, tris)
    if is_neck_skin.any():
        z = p[is_neck_skin, 2]
        y = p[is_neck_skin, 1]
        x = p[is_neck_skin, 0]

        w_bot = np.clip((162.0 - z) / 4.5, 0.0, 1.0)
        w_front = np.clip((y - 1.0) / 4.5, 0.0, 1.0)
        w_side = np.clip((np.abs(x) - 1.5) / 3.5, 0.0, 1.0)

        extra_side_drop = 2.0 * w_side * w_bot
        z_new = z - (z_drop * (w_bot ** 1.1) + extra_side_drop)
        y_new = y + y_push * w_bot * w_front
        x_new = x * (1.0 + x_flare * w_bot)

        low = z_new < 157.0
        if low.any():
            t_z = np.clip((157.0 - z_new[low]) / 5.5, 0.0, 1.0)
            y_cap = 10.8 + (1.0 - t_z) * 1.0
            y_new[low] = np.minimum(y_new[low], y_cap)
            y_new[low] = np.maximum(y_new[low], -1.6 - (1.0 - t_z) * 0.6)
            x_cap = 7.2 + (1.0 - t_z) * 0.8
            x_new[low] = np.clip(x_new[low], -x_cap, x_cap)

        p[is_neck_skin, 0] = x_new
        p[is_neck_skin, 1] = y_new
        p[is_neck_skin, 2] = z_new

    is_hair = ~is_neck_skin
    if is_hair.any():
        zh, yh, xh = p[is_hair, 2], p[is_hair, 1], p[is_hair, 0]
        wz = np.clip((163.8 - zh) / 7.5, 0.0, 1.0)
        dx, dy = xh - 0.0, yh - 2.0
        r = np.hypot(dx, dy) + 1e-6
        r_target = np.minimum(r, 4.6 + (1.0 - wz) * 2.4)
        scale_r = (r * (1.0 - wz) + r_target * wz) / r
        x_new = dx * scale_r
        y_new = 2.0 + dy * scale_r
        w_front_tuck = np.clip((164.0 - zh) / 2.2, 0.0, 1.0)
        y_max_allowed = 4.2 * (1.0 - 0.3 * wz)
        y_new = y_new * (1.0 - w_front_tuck) + np.minimum(y_new, y_max_allowed) * w_front_tuck
        p[is_hair, 0] = x_new
        p[is_hair, 1] = y_new
    return p


NECK_SKIRT_MAX_Z = 156.0   # rim edges below this are the neck sheet's open bottom
NECK_SKIRT_DROP_CM = 6.5   # how far the new ring dives below that rim
NECK_SKIRT_TUCK = 0.88     # radial scale of the new ring about the neck axis
NECK_SKIRT_FORWARD_CM = 0.5  # and this far towards +y, the character's front

# L4D2 Zoey's head stands on an upright neck (recessed eyeball hemisphere centre at y ~ 12.00 cm,
# cornea apex at y ~ 13.58 cm, z ~ 174.72 cm), whereas PAYDAY 2's female heister rig (Joy/Hila)
# leans `Neck -> Head` forward by +22.25° with cornea apex at y = 17.00..17.43 cm behind `a_head`
# eyewear and the face pitched forward by +10.5°. Mapping eyeball centre (12.00, 174.72) to
# (15.70, 173.80) places Miranda's cornea apex at y = 17.29 cm (strictly between Joy 17.00 and
# Hila 17.43) and aligns brow, nose, lips, chin, and throat with Joy/Hila without poking through
# sunglasses/masks. Rational half-angle tan(10.5° / 2) gives exact orthogonal `(cos, sin)` with
# IEEE-754 arithmetic only (no libm sin/cos drift).
L4D2_POSTURE_HALF_TAN = 0.09188709102124269  # tan(5.25 deg) -> +10.5 deg forward pitch
L4D2_SRC_EYE_YZ = (12.00, 174.72)
L4D2_TGT_EYE_YZ = (15.70, 173.80)
L4D2_POSTURE_BLEND_Z = (156.0, 163.2)  # 0 at collar rim/skirt (z<=156.0), 1 on head/seam (z>=163.2)
L4D2_THROAT_ARCH_CM = 0.90
L4D2_HAIR_THROAT_CLEAR_CM = 1.55


def _l4d2_posture_cos_sin(half_tan: float = L4D2_POSTURE_HALF_TAN) -> tuple[float, float]:
    t2 = half_tan * half_tan
    denom = 1.0 + t2
    return (1.0 - t2) / denom, (2.0 * half_tan) / denom


def rigid_l4d2_head_posture(
    positions: np.ndarray,
    normals: np.ndarray,
    *,
    src_eye_yz: tuple[float, float] = L4D2_SRC_EYE_YZ,
    tgt_eye_yz: tuple[float, float] = L4D2_TGT_EYE_YZ,
    half_tan: float = L4D2_POSTURE_HALF_TAN,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the rigid forward pitch + eye-socket alignment from L4D2 bind pose to PD2 female heister posture."""
    c, s = _l4d2_posture_cos_sin(half_tan)
    src_y, src_z = src_eye_yz
    tgt_y, tgt_z = tgt_eye_yz

    p = np.asarray(positions, dtype=np.float64)
    p_out = p.copy()
    dy = p[:, 1] - src_y
    dz = p[:, 2] - src_z
    p_out[:, 1] = tgt_y + dy * c + dz * s
    p_out[:, 2] = tgt_z - dy * s + dz * c

    n = np.asarray(normals, dtype=np.float64)
    n_out = n.copy()
    ny, nz = n[:, 1], n[:, 2]
    n_out[:, 1] = ny * c + nz * s
    n_out[:, 2] = -ny * s + nz * c
    return p_out.astype(np.float32), n_out.astype(np.float32)


def blend_l4d2_scalp_and_neck_posture(
    p_raw: np.ndarray,
    n_raw: np.ndarray,
    p_skirted: np.ndarray,
    n_skirted: np.ndarray,
    is_neck_skin_raw: np.ndarray,
    *,
    blend_z: tuple[float, float] = L4D2_POSTURE_BLEND_Z,
    throat_arch_cm: float = L4D2_THROAT_ARCH_CM,
    hair_throat_clear_cm: float = L4D2_HAIR_THROAT_CLEAR_CM,
) -> tuple[np.ndarray, np.ndarray]:
    """Lean the L4D2 neck cylinder and hair smoothly from the collar socket into the tilted head.

    Vertices at or below ``blend_z[0]`` (156.0 cm, the collar rim and extruded skirt) stay fixed
    inside the body collar, while vertices at or above ``blend_z[1]`` (163.2 cm, below every
    `Face <-> Scalp` seam vertex at z >= 163.49 cm) receive the exact rigid head transform.
    Interpolating directly between the collar-shaped mesh ``p_skirted`` and ``rigid(p_raw)``
    avoids double-shifting the mid-neck and hair tuck zone, while gently keeping lower side
    hair locks tucked behind the forward-leaning throat silhouette.
    """
    p0 = np.asarray(p_raw, dtype=np.float64)
    n0 = np.asarray(n_raw, dtype=np.float64)
    ps = np.asarray(p_skirted, dtype=np.float64)
    ns = np.asarray(n_skirted, dtype=np.float64)
    n_orig = len(p0)

    p_raw_ext = ps.copy()
    p_raw_ext[:n_orig] = p0
    n_raw_ext = ns.copy()
    n_raw_ext[:n_orig] = n0

    p_rig, n_rig = rigid_l4d2_head_posture(p_raw_ext, n_raw_ext)
    p_rig64 = np.asarray(p_rig, dtype=np.float64)
    n_rig64 = np.asarray(n_rig, dtype=np.float64)

    z_lo, z_hi = blend_z
    z_blend = ps[:, 2].copy()
    z_blend[:n_orig] = np.where(p0[:, 2] >= z_hi, p0[:, 2], 0.5 * (ps[:n_orig, 2] + p0[:, 2]))
    z_blend = np.where(ps[:, 2] <= z_lo, ps[:, 2], z_blend)
    w = smoothstep((z_blend - z_lo) / (z_hi - z_lo))

    p_out = ps * (1.0 - w[:, None]) + p_rig64 * w[:, None]

    is_ns_ext = np.zeros(len(ps), dtype=bool)
    is_ns_ext[: len(is_neck_skin_raw)] = is_neck_skin_raw
    u_phys = np.clip((p_out[:, 2] - 156.5) / (z_hi - 156.5), 0.0, 1.0) * np.where((w > 0.0) & (w < 1.0), 1.0, 0.0)
    w_arch = 4.0 * u_phys * (1.0 - u_phys) * (0.75 + 0.50 * u_phys)
    w_throat = np.clip((ps[:, 1] - 1.5) / 5.0, 0.0, 1.0)
    p_out[is_ns_ext, 1] += throat_arch_cm * w_arch[is_ns_ext] * w_throat[is_ns_ext]

    is_hr = ~is_ns_ext
    if is_hr.any() and hair_throat_clear_cm > 0.0:
        w_hr_band = 4.0 * w[is_hr] * (1.0 - w[is_hr])
        p_out[is_hr, 1] -= hair_throat_clear_cm * w_hr_band * smoothstep((p_out[is_hr, 1] - 4.0) / 5.0)

    n_out = ns * (1.0 - w[:, None]) + n_rig64 * w[:, None]
    n_len = np.sqrt(np.sum(n_out * n_out, axis=1, keepdims=True))
    n_out /= np.maximum(n_len, 1e-8)
    return p_out.astype(np.float32), n_out.astype(np.float32)


def extend_neck_skirt(
    p: np.ndarray,
    n: np.ndarray,
    uv: np.ndarray,
    tris: np.ndarray,
    *,
    max_z: float = NECK_SKIRT_MAX_Z,
    drop: float = NECK_SKIRT_DROP_CM,
    tuck: float = NECK_SKIRT_TUCK,
    forward: float = NECK_SKIRT_FORWARD_CM,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Give the neck sheet a skirt so its open rim ends *inside* the body.

    The head models are cut off at the neck: the neck sheet's outer boundary ends
    across the throat, at z 149.5 on the heister rig. Over the bodies measured so
    far that rim is already hidden - on the retired Christie body **0 of its 98-120
    edges** are the front-most surface, from the front or from behind
    (docs/audits/2026-11-07-christie-slim-diagnosis.md §10.2) - but a rim that
    stops exactly where a collar ends is one wider neckline away from being the
    front-most surface, and a sheet's open edge seen edge-on is a hard line no
    texture can hide. That is what this pass is for: insurance, not a fix for an
    observed line. On Christie it changes no pixel.

    It extrudes one ring below the rim - dropped, pulled in towards the neck axis
    and nudged 0.5 cm towards the front (+y is the character's side of this model
    space) - and stitches it to the rim with two triangles per rim edge. The ring
    keeps the rim's UV, so the neck island's last rows stretch over it, and the
    rim's normal; it lands under the body's own surface, so the junction becomes
    the intersection curve the two meshes define instead of a floating edge.

    Only rim edges that sit near the neck axis and below ``max_z`` are used, so
    the scalp's cut (which is part of the same loop) and the hair sheets are
    untouched. Returns the extended ``(p, n, uv, tris)``; indices of the existing
    vertices do not change.
    """
    if len(tris) == 0:
        return p, n, uv, tris
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in tris:
        for u, v in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            if u == v:
                continue
            e = (u, v) if u < v else (v, u)
            counts[e] = counts.get(e, 0) + 1

    rim_edges = []
    for (a, b), cnt in counts.items():
        if cnt != 1:
            continue
        pa, pb = p[a], p[b]
        if pa[2] > max_z or pb[2] > max_z:
            continue
        if max(np.hypot(pa[0], pa[1] - 2.0), np.hypot(pb[0], pb[1] - 2.0)) > 8.5:
            continue
        rim_edges.append((a, b))
    if not rim_edges:
        return p, n, uv, tris

    rim_verts = sorted({v for e in rim_edges for v in e})
    rim_p = np.asarray([p[v] for v in rim_verts], dtype=np.float64)
    cx, cy = float(rim_p[:, 0].mean()), float(rim_p[:, 1].mean())

    new_p = np.empty((len(rim_verts), p.shape[1]), dtype=p.dtype)
    new_n = np.empty((len(rim_verts), n.shape[1]), dtype=n.dtype)
    new_uv = np.empty((len(rim_verts), uv.shape[1]), dtype=uv.dtype)
    new_index: dict[int, int] = {}
    for row, v in enumerate(rim_verts):
        x, y, z = (float(c) for c in p[v])
        new_p[row] = (cx + (x - cx) * tuck, cy + (y - cy) * tuck + forward, z - drop)
        new_n[row] = n[v]
        new_uv[row] = uv[v]
        new_index[v] = len(p) + row

    new_tris = []
    for a, b in rim_edges:
        a2, b2 = new_index[a], new_index[b]
        quad = [(a, b, b2), (a, b2, a2)]
        # keep the sheet's facing: wind the strip the way the rim's own faces run
        tip = np.cross(p[b] - p[a], new_p[a2 - len(p)] - p[a])
        ref = n[a].astype(np.float64) + n[b].astype(np.float64)
        if float(np.dot(tip, ref)) < 0.0:
            quad = [(a, b2, b), (a, a2, b2)]
        new_tris.extend(quad)

    p_out = np.vstack([p, new_p])
    n_out = np.vstack([n, new_n])
    uv_out = np.vstack([uv, new_uv])
    tris_out = np.vstack([tris, np.asarray(new_tris, dtype=tris.dtype)])
    return p_out, n_out, uv_out, tris_out


# ---------------------------------------------------------------- Arivus neck
# The Random4 ped is a low-poly tube: its neck cone is not tall enough to reach
# Old Hoxton's collar, so `build_arivus_hoxton_mod` used to drag the whole cone
# down (up to 4.3 cm at the throat) and push it up again near the collar. That
# squashed the neck into half its height and left its open rim on show as a
# jagged skin line across the collarbones (D79).
#
# The ped is now left where it lands. Its open neck rim is closed by a skirt that
# is tucked in towards the ped's own neck axis and dropped to just above where
# the suit stops surrounding the neck, so the open edge ends inside the suit.
# Measured, not guessed: a ray-parity test against the suit's `g_body` (parity
# along +-x and +-y from each skirt vertex) says **26 of the rim loop's 27**
# vertices are enclosed, the 27th being a degenerate point 0.3 cm off the
# model's z axis. `tests/test_arivus_neck_fit.py` measures the same thing on
# all three shipped models.
NECK_TUCK = 0.35          # skirt radius as a fraction of the rim's own radius
NECK_SKIRT_BOTTOM_Z = 148.0  # z where the suit still surrounds the neck
NECK_RING_MAX_Z = 170.5   # rim edges below this are the neck's own open bottom
NECK_AXIS_TOLERANCE_CM = 11.5  # ... and this close to the neck axis
#: the ped's neck axis in PD2 space (x, y): the cone is centred ~1-3 cm forward
#: of the model's z axis, so tucking towards the origin would swing it sideways.
ARIVUS_NECK_AXIS_XY = (0.0, 1.0)
#: the ped's neck is cut in a V: z 159.4 across the throat, z 164.9 at the back,
#: and the suit's collar rim only reaches z ~159.8-160.5. D72 hid that V by
#: shifting the whole cone 4 cm; that squashed the neck. Instead the rim is
#: dropped to the collar's own height, so the open edge ends under the collar
#: instead of standing above it, and a skirt closes it from below.
NECK_RIM_TARGET_Z = 159.0
#: the rim's back half is pushed down at full weight from |azimuth| > 60 deg,
#: fading to nothing across the throat, so the throat keeps its length.
NECK_RIM_FADE_DEG = 60.0


def neck_skirt_ring(rim: np.ndarray, axis_xy: tuple[float, float],
                    bottom_z: float, tuck: float) -> np.ndarray:
    """The single ring an open neck rim is closed with.

    Every rim vertex moves radially inward about ``axis_xy`` (a fraction
    ``tuck`` of its own radius) and down to ``bottom_z``, so the skirt narrows
    under the collar instead of pushing through it. Returns one point per rim
    vertex, in the same order.
    """
    p = np.asarray(rim, dtype=np.float64)
    ax, ay = axis_xy
    rel = p[:, :2] - np.array([ax, ay])
    return np.column_stack([ax + rel[:, 0] * tuck,
                            ay + rel[:, 1] * tuck,
                            np.full(len(p), bottom_z)])


def push_neck_rim(p: np.ndarray, rim_verts: list[int], *,
                  target_z: float = NECK_RIM_TARGET_Z,
                  fade_deg: float = NECK_RIM_FADE_DEG) -> None:
    """Drop the neck's cut rim to the collar's height, back and sides first.

    The ped's cut is a V: lowest across the throat, ~5.5 cm higher up the back
    of the neck. The suit's collar rim sits at z ~159.8-160.5, so the back of
    the V stands *above* it and the opening lets you see into the neck. This
    lowers rim vertices above ``target_z`` to it, at full weight from
    ``fade_deg`` either side of the back, fading to nothing at the throat, so the
    face, jaw and the front of the neck are untouched.
    """
    for v in rim_verts:
        z = float(p[v, 2])
        if z <= target_z:
            continue
        az = abs(float(np.degrees(np.arctan2(p[v, 0], p[v, 1]))))
        w = min(az / fade_deg, 1.0)
        p[v, 2] = z - w * (z - target_z)


def _neck_rim_loop(p: np.ndarray, rim_edges: list[tuple[int, int]]) -> list[int]:
    """The connected boundary loop that contains the neck's lowest vertex."""
    if not rim_edges:
        return []
    adj: dict[int, set[int]] = {}
    for a, b in rim_edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    lowest = min(adj, key=lambda v: p[v, 2])
    seen = {lowest}
    stack = [lowest]
    while stack:
        cur = stack.pop()
        for nb in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return sorted(seen)


def extend_neck_into_collar(
    p: np.ndarray,
    n: np.ndarray,
    uv: np.ndarray,
    tris: np.ndarray,
    *,
    axis_xy: tuple[float, float] = ARIVUS_NECK_AXIS_XY,
    max_z: float = NECK_RING_MAX_Z,
    tuck: float = NECK_TUCK,
    bottom_z: float = NECK_SKIRT_BOTTOM_Z,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Close the head's open neck rim with a skirt that tucks inside the suit.

    Only the neck's own rim is used. The ped's open edges are a tangle: the cut
    ring, a jaw/ear loop above it and a strip that climbs the back of the head
    to z 186, all reachable from one another. The ring is therefore taken as the
    connected boundary loop owning the neck's lowest vertex, restricted to
    vertices near the neck axis and below z 170, so the jaw, the hair sheet and
    the scalp's cut are left alone. Returns ``(p, n, uv, tris)`` with vertices
    appended; existing indices do not change.
    """
    if len(tris) == 0:
        return p, n, uv, tris
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in tris:
        for u, w in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            if u == w:
                continue
            key = (min(u, w), max(u, w))
            counts[key] = counts.get(key, 0) + 1
    rim_edges = []
    for (a, b), cnt in counts.items():
        if cnt != 1:
            continue
        pa, pb = np.asarray(p[a]), np.asarray(p[b])
        if max(pa[2], pb[2]) > max_z:
            continue
        if max(np.hypot(pa[0], pa[1]), np.hypot(pb[0], pb[1])) > NECK_AXIS_TOLERANCE_CM:
            continue
        rim_edges.append((a, b))
    if not rim_edges:
        return p, n, uv, tris

    # The ped's cut is a V: low across the throat, high up the back of the neck,
    # and a separate jaw/ear loop hangs above it. Take the connected boundary
    # loop that owns the neck's lowest vertex - that is the neck's own rim - and
    # leave every other open edge (jaw, hair sheet) alone.
    rim_verts = _neck_rim_loop(p, rim_edges)
    if not rim_verts:
        return p, n, uv, tris
    # The loop is the neck's cut ring plus a strip running up the back of the
    # head to the crown. Only the ring is both near the neck axis and low: the
    # strip's own vertices climb to z 186 and are left alone.
    rim_verts = [v for v in rim_verts
                 if p[v, 2] < 170.0 and np.hypot(p[v, 0], p[v, 1]) < 9.5]
    if not rim_verts:
        return p, n, uv, tris
    push_neck_rim(p, rim_verts)
    keep_set = set(rim_verts)
    rim_edges = [(a, b) for a, b in rim_edges if a in keep_set and b in keep_set]
    if not rim_edges:
        return p, n, uv, tris

    skirt = neck_skirt_ring(np.asarray([p[v] for v in rim_verts]), axis_xy, bottom_z, tuck)

    new_p = np.empty((len(rim_verts), p.shape[1]), dtype=p.dtype)
    new_n = np.empty((len(rim_verts), n.shape[1]), dtype=n.dtype)
    new_uv = np.empty((len(rim_verts), uv.shape[1]), dtype=uv.dtype)
    new_index: dict[int, int] = {}
    for row, v in enumerate(rim_verts):
        new_p[row] = skirt[row]
        new_uv[row] = uv[v]
        new_index[v] = len(p) + row

    # Normals point in and down: the skirt is the inside of the suit's collar,
    # and must not catch the key light like skin if a pose ever shows it.
    ax, ay = axis_xy
    for row in range(len(rim_verts)):
        d = np.array([ax - new_p[row, 0], ay - new_p[row, 1], 0.0])
        ln = float(np.linalg.norm(d))
        inward = d / ln if ln > 1e-9 else np.array([0.0, -1.0, 0.0])
        nv = inward + np.array([0.0, 0.0, -0.4])
        new_n[row] = nv / max(float(np.linalg.norm(nv)), 1e-9)

    new_tris = []
    for a, b in rim_edges:
        a2, b2 = new_index[a], new_index[b]
        # wind the strip so its front faces away from the neck axis (outward),
        # the way the cone above it already does
        tip = np.cross(np.asarray(p[b], np.float64) - np.asarray(p[a], np.float64),
                       np.asarray(new_p[b2 - len(p)], np.float64) - np.asarray(p[a], np.float64))
        ref = np.asarray(n[a], np.float64) + np.asarray(n[b], np.float64)
        if float(np.dot(tip, np.array([ref[0], ref[1], 0.0]))) < 0.0:
            new_tris += [(a, b2, b), (a, a2, b2)]
        else:
            new_tris += [(a, b, b2), (a, b2, a2)]

    return (np.vstack([p, new_p]), np.vstack([n, new_n]),
            np.vstack([uv, new_uv]),
            np.vstack([tris, np.asarray(new_tris, dtype=tris.dtype)]))


def repair_skin_and_neck_normals(
    face_p: np.ndarray,
    face_n: np.ndarray,
    face_t: np.ndarray,
    scalp_p: np.ndarray,
    scalp_n: np.ndarray,
    scalp_uv_img: np.ndarray,
    scalp_t: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Repair corrupted cheek/mouth-corner boundary normals and recompute smooth normals on extended neck skin."""
    fn_out = np.asarray(face_n, dtype=np.float64).copy()
    sn_out = np.asarray(scalp_n, dtype=np.float64).copy()
    fp = np.asarray(face_p, dtype=np.float64)
    sp = np.asarray(scalp_p, dtype=np.float64)
    ft = np.asarray(face_t, dtype=np.int32)
    st = np.asarray(scalp_t, dtype=np.int32)

    is_ns = neck_skin_uv_island_mask(scalp_uv_img, st)
    ns_tri_mask = is_ns[st[:, 0]] & is_ns[st[:, 1]] & is_ns[st[:, 2]]
    st_ns = st[ns_tri_mask] + len(fp)

    p_all = np.vstack([fp, sp])
    t_skin = np.vstack([ft, st_ns])
    v0, v1, v2 = p_all[t_skin[:, 0]], p_all[t_skin[:, 1]], p_all[t_skin[:, 2]]
    tri_fn = np.cross(v1 - v0, v2 - v0)
    rounded = np.round(p_all * 100.0).astype(np.int64)
    _, inv = np.unique(rounded, axis=0, return_inverse=True)
    gn_u = np.zeros((inv.max() + 1, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(gn_u, inv[t_skin[:, k]], tri_fn)
    gn_u /= np.maximum(np.linalg.norm(gn_u, axis=1, keepdims=True), 1e-8)
    gn_all = gn_u[inv]
    if float(np.sum(fn_out * gn_all[: len(fp)], axis=1).mean()) < 0.0:
        gn_all = -gn_all

    gn_f = gn_all[: len(fp)]
    gn_s = gn_all[len(fp) :]

    bad_f = np.sum(fn_out * gn_f, axis=1) < 0.75
    fn_out[bad_f] = gn_f[bad_f]

    bad_s = is_ns & (np.sum(sn_out * gn_s, axis=1) < 0.75)
    sn_out[bad_s] = gn_s[bad_s]

    # Smoothly update extended lower neck-skin normals to match the flared collar slope
    if is_ns.any():
        w_ext = np.clip((161.5 - sp[is_ns, 2]) / 2.5, 0.0, 1.0)[:, None]
        blended = sn_out[is_ns] * (1.0 - w_ext) + gn_s[is_ns] * w_ext
        blended /= np.maximum(np.linalg.norm(blended, axis=1, keepdims=True), 1e-8)
        sn_out[is_ns] = blended

    # Weld normals across coincident Face <-> Scalp(neck_skin) seam pairs
    map_f: dict[tuple[int, int, int], list[int]] = {}
    for i, p in enumerate(fp):
        k = (int(round(p[0] * 100.0)), int(round(p[1] * 100.0)), int(round(p[2] * 100.0)))
        map_f.setdefault(k, []).append(i)
    for j in np.nonzero(is_ns)[0]:
        p = sp[j]
        k = (int(round(p[0] * 100.0)), int(round(p[1] * 100.0)), int(round(p[2] * 100.0)))
        if k in map_f:
            f_idxs = map_f[k]
            avg_n = sn_out[j].copy()
            for fi in f_idxs:
                avg_n = avg_n + fn_out[fi]
            avg_n /= max(float(np.linalg.norm(avg_n)), 1e-8)
            sn_out[j] = avg_n
            for fi in f_idxs:
                fn_out[fi] = avg_n

    # Keep the repaired source normals around the nostrils. The former broad
    # downward override affected the visible nose wings and produced dark blotches;
    # the diffuse and normal-map cavity treatments remain restricted to the UV pockets.

    return fn_out.astype(np.float32), sn_out.astype(np.float32)


def build_crisp_miranda_eye_texture(me2_dir: Path, size: int = 1024) -> np.ndarray:
    """Synthesize a crisp 1024x1024 radially symmetric deep-sapphire Miranda eye texture."""
    # float64, and a radius made of * + and sqrt: the same on every machine. What goes
    # through sin, cos, exp, arctan2 and powers below is rounded with a margin at the end.
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    u = (xx + 0.5) / size - 0.5
    v = (yy + 0.5) / size - 0.5
    r = np.sqrt(u * u + v * v)
    theta = np.arctan2(v, u)

    iris_outer = 0.28
    iris_inner = 0.25
    pupil_r = 0.115

    f1 = np.sin(theta * 58.0 + 0.35 * np.sin(theta * 7.0))
    f2 = np.cos(theta * 94.0 - 0.40 * np.cos(theta * 11.0))
    f3 = np.sin(theta * 142.0 + r * 28.0)
    fiber_detail = 0.45 * f1 + 0.35 * f2 + 0.20 * f3

    rn = np.clip((r - pupil_r) / max(iris_inner - pupil_r, 1e-4), 0.0, 1.0)
    bump = (rn - 0.28) / 0.14
    collarette = np.exp(-(bump * bump))
    radial = 1.0 - 0.38 * (rn ** 1.35) + 0.12 * collarette + 0.14 * fiber_detail
    radial = np.clip(radial, 0.22, 1.25)

    upper_iris_ao = np.clip(1.0 - 0.12 * np.clip((-v - 0.04) / 0.22, 0.0, 1.0), 0.85, 1.0)
    iris_r = np.clip((38.0 * radial + 8.0 * collarette) * upper_iris_ao, 6.0, 75.0)
    iris_g = np.clip((102.0 * radial + 16.0 * collarette) * upper_iris_ao, 24.0, 148.0)
    iris_b = np.clip((196.0 * radial + 24.0 * collarette) * upper_iris_ao, 72.0, 228.0)

    limbus_t = np.clip((r - (iris_inner - 0.025)) / (iris_outer - (iris_inner - 0.025)), 0.0, 1.0)
    limbus_dark = 1.0 - 0.78 * (limbus_t ** 1.4)
    iris_r *= limbus_dark
    iris_g *= limbus_dark
    iris_b *= limbus_dark

    pupil_mask = np.clip((pupil_r + 0.012 - r) / 0.018, 0.0, 1.0)
    iris_r = iris_r * (1.0 - pupil_mask) + 2.0 * pupil_mask
    iris_g = iris_g * (1.0 - pupil_mask) + 3.0 * pupil_mask
    iris_b = iris_b * (1.0 - pupil_mask) + 5.0 * pupil_mask

    sclera_ao = np.clip(1.0 - 0.32 * np.clip((r - iris_outer) / 0.22, 0.0, 1.0), 0.62, 1.0)
    eyelid_ao = np.clip(1.0 - 0.22 * np.clip((-v - 0.05) / 0.25, 0.0, 1.0), 0.72, 1.0)
    sc_r = 162.0 * sclera_ao * eyelid_ao
    sc_g = 148.0 * sclera_ao * eyelid_ao
    sc_b = 142.0 * sclera_ao * eyelid_ao

    iris_mask = np.clip((iris_outer + 0.012 - r) / 0.022, 0.0, 1.0)
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, 0] = determinism.floor8(sc_r * (1.0 - iris_mask) + iris_r * iris_mask, "the eye of a head pack")
    rgba[:, :, 1] = determinism.floor8(sc_g * (1.0 - iris_mask) + iris_g * iris_mask, "the eye of a head pack")
    rgba[:, :, 2] = determinism.floor8(sc_b * (1.0 - iris_mask) + iris_b * iris_mask, "the eye of a head pack")
    rgba[:, :, 3] = np.where(r < 0.125, 4, np.where(r < 0.28, 10, 8)).astype(np.uint8)
    return rgba


def project_me2_eye_uv_img(positions: np.ndarray) -> np.ndarray:
    """Planar-project eyeball positions into top-down (u_img, v_img) in [0, 1]^2
    centered on the visible eyelid opening (palpebral fissure)."""
    p = np.asarray(positions, dtype=np.float64)
    uv_img = np.full((len(p), 2), 0.5, dtype=np.float32)
    for sign in (-1.0, 1.0):
        mask = (p[:, 0] * sign) > 0.0
        if not mask.any():
            continue
        sub = p[mask]
        cx_bbox = 0.5 * (sub[:, 0].min() + sub[:, 0].max())
        cz_bbox = 0.5 * (sub[:, 2].min() + sub[:, 2].max())
        rx = 0.5 * (sub[:, 0].max() - sub[:, 0].min()) or 1.0
        dx_frac = 0.08 if sign > 0.0 else 0.13
        cx = cx_bbox + sign * dx_frac * rx
        cz = cz_bbox - 0.125 * rx
        scale = 0.45 / rx
        u = np.clip(0.5 - scale * (sub[:, 0] - cx), 0.02, 0.98)
        v_img = np.clip(0.5 - scale * (sub[:, 2] - cz), 0.02, 0.98)
        uv_img[mask, 0] = u.astype(np.float32)
        uv_img[mask, 1] = v_img.astype(np.float32)
    return uv_img


def soften_eyeball_normals(normals: np.ndarray) -> np.ndarray:
    """Soften horizontal and vertical normal tilt across the recessed 1.5cm eyeball sphere."""
    n = np.asarray(normals, dtype=np.float64).copy()
    n[:, 0] *= 0.35
    n[:, 2] *= 0.35
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-8)
    return n.astype(np.float32)


def map_uv_to_quadrant(uv_img: np.ndarray, qx: int, qy: int) -> np.ndarray:
    """Map top-down image UVs (u_img, v_img) in [0, 1]^2 into quadrant (qx, qy) of a 2x2 atlas,
    returning Diesel Geometry uv0 (u_diesel, v_diesel = 1 - v_img_atlas)."""
    u_clamped = np.clip(uv_img[:, 0], 0.002, 0.998)
    v_clamped = np.clip(uv_img[:, 1], 0.002, 0.998)
    u_atlas = 0.5 * qx + 0.5 * u_clamped
    v_img_atlas = 0.5 * qy + 0.5 * v_clamped
    return np.column_stack([u_atlas, 1.0 - v_img_atlas]).astype(np.float32)


def compute_tangents(
    verts: np.ndarray, normals: np.ndarray, uvs: np.ndarray, tris: np.ndarray
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Compute orthonormalized tangent (uvdir_u) and bitangent (uvdir_v) per vertex."""
    n_v = len(verts)
    tan_u = np.zeros((n_v, 3), dtype=np.float64)
    tan_v = np.zeros((n_v, 3), dtype=np.float64)

    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    w0 = uvs[tris[:, 0]]
    w1 = uvs[tris[:, 1]]
    w2 = uvs[tris[:, 2]]

    e1 = v1 - v0
    e2 = v2 - v0
    du1 = w1[:, 0] - w0[:, 0]
    dv1 = w1[:, 1] - w0[:, 1]
    du2 = w2[:, 0] - w0[:, 0]
    dv2 = w2[:, 1] - w0[:, 1]

    denom = du1 * dv2 - du2 * dv1
    valid = np.abs(denom) > 1e-8
    r = np.zeros_like(denom)
    r[valid] = 1.0 / denom[valid]

    sdir = (dv2[:, None] * e1 - dv1[:, None] * e2) * r[:, None]
    # Channel 22 (uvdir_v) stores +dP/dv_img = -dP/dv_diesel (p2mt ComputeUvDirections convention)
    tdir = (du2[:, None] * e1 - du1[:, None] * e2) * r[:, None]

    # Weld by (position, uv) when accumulating tangents so shared vertices across
    # corner-split triangles receive smooth area-weighted tangents.
    weld_key = np.hstack([
        np.round(verts * 1000.0).astype(np.int64),
        np.round(uvs * 10000.0).astype(np.int64),
    ])
    _, inv = np.unique(weld_key, axis=0, return_inverse=True)
    n_u = int(inv.max()) + 1
    tu_u = np.zeros((n_u, 3), dtype=np.float64)
    tv_u = np.zeros((n_u, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(tu_u, inv[tris[:, k]], sdir)
        np.add.at(tv_u, inv[tris[:, k]], tdir)
    tan_u = tu_u[inv]
    tan_v = tv_u[inv]

    nrm = np.asarray(normals, dtype=np.float64)
    n_norm = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.where(n_norm > 1e-8, nrm / np.maximum(n_norm, 1e-8), np.array([0.0, 1.0, 0.0]))

    # Gram-Schmidt orthonormalize tan_u and tan_v against nrm
    dot_nu = np.sum(nrm * tan_u, axis=1, keepdims=True)
    tu = tan_u - nrm * dot_nu
    tu_len = np.linalg.norm(tu, axis=1, keepdims=True)
    fallback_u = np.where(np.abs(nrm[:, :1]) < 0.9, np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    fallback_u = fallback_u - nrm * np.sum(nrm * fallback_u, axis=1, keepdims=True)
    fallback_u /= np.maximum(np.linalg.norm(fallback_u, axis=1, keepdims=True), 1e-8)
    tu = np.where(tu_len > 1e-6, tu / np.maximum(tu_len, 1e-6), fallback_u)

    tv = tan_v - nrm * np.sum(nrm * tan_v, axis=1, keepdims=True)
    tv_len = np.linalg.norm(tv, axis=1, keepdims=True)
    fallback_v = np.cross(nrm, tu)
    tv = np.where(tv_len > 1e-6, tv / np.maximum(tv_len, 1e-6), fallback_v)

    return [tuple(map(float, row)) for row in tu], [tuple(map(float, row)) for row in tv]


def deduplicate_mesh(p: np.ndarray, n: np.ndarray, uv: np.ndarray, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Weld identical (position, normal, uv) vertices to avoid 3x triangle-soup vertex bloat."""
    p_f = np.asarray(p, dtype=np.float32)
    n_f = np.asarray(n, dtype=np.float32)
    uv_f = np.asarray(uv, dtype=np.float32)
    t_i = np.asarray(tris, dtype=np.int32)
    key = np.hstack([
        np.round(p_f * 1e4).astype(np.int64),
        np.round(n_f * 1e4).astype(np.int64),
        np.round(uv_f * 1e5).astype(np.int64),
    ])
    _, first_idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    order = np.argsort(first_idx)
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    keep = first_idx[order]
    new_tris = remap[inv[t_i]].astype(np.int32)
    return p_f[keep], n_f[keep], uv_f[keep], new_tris


def _prepare_combined_head_arrays(
    atom0_mesh: dict[str, np.ndarray],
    atom1_mesh: dict[str, np.ndarray],
    bone_offset: int,
    jaw_lift: float = 3.0,
    single_atom: bool = False,
    double_side_atom1: bool = False,
    orthonormal_tangents: bool = False,
) -> dict:
    """Deduplicate and pack Atom 0 and Atom 1 into Diesel Geometry/Topology/ModelData arrays."""
    v0, n0, uv0, t0 = deduplicate_mesh(
        atom0_mesh["verts"], atom0_mesh["normals"], atom0_mesh["uvs"], atom0_mesh["tris"]
    )
    v1, n1, uv1, t1 = deduplicate_mesh(
        atom1_mesh["verts"], atom1_mesh["normals"], atom1_mesh["uvs"], atom1_mesh["tris"]
    )

    verts_all = np.vstack([v0, v1])
    norms_all = np.vstack([n0, n1])
    n_len = np.linalg.norm(norms_all, axis=1, keepdims=True)
    norms_all = np.where(n_len > 1e-6, norms_all / np.maximum(n_len, 1e-6), np.array([0.0, 1.0, 0.0], dtype=np.float32))
    uvs_all = np.vstack([uv0, uv1])
    tris_primary = np.vstack([t0, t1 + len(v0)])

    pal_idx, pal_w = compute_joy_head_weights(verts_all, bone_offset=bone_offset, jaw_lift=jaw_lift)
    if orthonormal_tangents:
        import tangents

        uvdir_u, uvdir_v = tangents.tangent_frames(verts_all, norms_all, uvs_all, tris_primary)
    else:
        uvdir_u, uvdir_v = compute_tangents(verts_all, norms_all, uvs_all, tris_primary)

    if double_side_atom1:
        t1 = np.vstack([t1, t1[:, [0, 2, 1]]])
    tris_all = np.vstack([t0, t1 + len(v0)])

    verts_list = [tuple(map(float, row)) for row in verts_all]
    norms_list = [tuple(map(float, row)) for row in norms_all]
    uvs_list = [tuple(map(float, row)) for row in uvs_all]
    flat_indices = [int(i) for tri in tris_all for i in tri]

    if single_atom:
        atoms = [
            {
                "base_vertex": 0,
                "tri_count": int(len(tris_all)),
                "base_index": 0,
                "slice_len": int(len(verts_all)),
                "material_id": 0,
            }
        ]
    else:
        atoms = [
            {
                "base_vertex": 0,
                "tri_count": int(len(t0)),
                "base_index": 0,
                "slice_len": int(len(v0)),
                "material_id": 0,
            },
            {
                "base_vertex": int(len(v0)),
                "tri_count": int(len(t1)),
                "base_index": int(len(t0) * 3),
                "slice_len": int(len(v1)),
                "material_id": 1,
            },
        ]
    bmin = tuple(map(float, verts_all.min(axis=0)))
    bmax = tuple(map(float, verts_all.max(axis=0)))
    center = 0.5 * (verts_all.min(axis=0) + verts_all.max(axis=0))
    radius = float(np.linalg.norm(verts_all - center, axis=1).max())
    return {
        "verts": verts_list,
        "normals": norms_list,
        "uv0": uvs_list,
        "blendindices": pal_idx,
        "blendweights": pal_w,
        "uvdir_v": uvdir_v,
        "uvdir_u": uvdir_u,
        "indices": flat_indices,
        "atoms": atoms,
        "bmin": bmin,
        "bmax": bmax,
        "radius": radius,
    }


def patch_female_heister_model(
    model_bytes: bytes,
    head_drawables: list[str],
    collapse_drawables: list[str],
    head_mat_name: str,
    hair_mat_name: str | None,
    packed_head: dict,
) -> bytes:
    """Patch head drawables and collapse legacy hair drawables in Clover, Bonnie, Sydney, or Rust `.model`."""
    mf = dm.ModelFile.read(model_bytes)

    mat_by_hash = {
        dm.decode_material(s.payload)["name_hash"]: s.id
        for s in mf.by_type(dm.MATERIAL)
    }
    head_mat_id = mat_by_hash[dm.hash64(head_mat_name)]
    hair_mat_id: int | None = None
    inserted_hair_mat_sec: dm.Section | None = None
    if hair_mat_name is not None:
        hair_hash = dm.hash64(hair_mat_name)
        if hair_hash in mat_by_hash:
            hair_mat_id = mat_by_hash[hair_hash]
        else:
            hair_mat_id = max((s.id for s in mf.sections if s.id < 100000), default=10000) + 1
            base_mat_dec = dm.decode_material(mf.by_id(head_mat_id).payload)
            base_mat_dec["name_hash"] = hair_hash
            inserted_hair_mat_sec = dm.Section(dm.MATERIAL, hair_mat_id, dm.encode_material(base_mat_dec))

    head_hashes = {dm.hash64(n) for n in head_drawables}
    collapse_hashes = {dm.hash64(n) for n in collapse_drawables}

    head_md_ids: set[int] = set()
    head_geo_ids: set[int] = set()
    head_topo_ids: set[int] = set()
    head_mg_ids: set[int] = set()
    head_sb_ids: set[int] = set()

    col_md_ids: set[int] = set()
    col_geo_ids: set[int] = set()
    col_topo_ids: set[int] = set()
    col_mg_ids: set[int] = set()
    col_sb_ids: set[int] = set()

    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        nh = md.get("name_hash")
        if nh in head_hashes:
            pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            head_md_ids.add(s.id)
            head_geo_ids.add(pg["geometry"])
            head_topo_ids.add(pg["topology"])
            head_mg_ids.add(md["matgroup"])
            head_sb_ids.add(md["skinbones"])
        elif nh in collapse_hashes:
            pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            col_md_ids.add(s.id)
            col_geo_ids.add(pg["geometry"])
            col_topo_ids.add(pg["topology"])
            col_mg_ids.add(md["matgroup"])
            col_sb_ids.add(md["skinbones"])

    # Tiny non-degenerate triangle hidden deep inside the Head bone (0.0, 5.33, 166.76)
    c_verts = [(0.0, 5.33, 166.76), (0.05, 5.33, 166.76), (0.0, 5.38, 166.76)]
    c_norms = [(0.0, 0.0, 1.0)] * 3
    c_uvs = [(0.0, 0.0), (0.01, 0.0), (0.0, 0.01)]
    c_bi = [(1, 0, 0, 0)] * 3
    c_bw = [(1.0, 0.0, 0.0)] * 3
    c_uv_v = [(0.0, 1.0, 0.0)] * 3
    c_uv_u = [(1.0, 0.0, 0.0)] * 3
    c_atoms = [{"base_vertex": 0, "tri_count": 1, "base_index": 0, "slice_len": 3, "material_id": 0}]

    new_sections: list[dm.Section] = []
    for s in mf.sections:
        if s.id in head_geo_ids:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(packed_head["verts"])
            dec["verts"] = packed_head["verts"]
            dec["normals"] = packed_head["normals"]
            dec["uv0"] = packed_head["uv0"]
            dec["blendindices"] = packed_head["blendindices"]
            dec["blendweights"] = packed_head["blendweights"]
            dec["uvdir_v"] = packed_head["uvdir_v"]
            dec["uvdir_u"] = packed_head["uvdir_u"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id in head_topo_ids:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = packed_head["indices"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id in head_md_ids:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = packed_head["atoms"]
            dec["bounds_min"] = packed_head["bmin"]
            dec["bounds_max"] = packed_head["bmax"]
            dec["bounding_radius"] = packed_head["radius"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id in head_mg_ids:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [head_mat_id] if hair_mat_id is None else [head_mat_id, hair_mat_id]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id in head_sb_ids:
            dec = dm.decode_skinbones(s.payload)
            dec["maps"] = [list(range(len(dec["objects"]))) for _ in range(len(packed_head["atoms"]) + 1)]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        elif s.id in col_geo_ids:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = 3
            dec["verts"] = c_verts
            dec["normals"] = c_norms
            dec["uv0"] = c_uvs
            dec["blendindices"] = c_bi
            dec["blendweights"] = c_bw
            dec["uvdir_v"] = c_uv_v
            dec["uvdir_u"] = c_uv_u
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id in col_topo_ids:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = [0, 1, 2]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id in col_md_ids:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = c_atoms
            dec["bounds_min"] = (0.0, 5.33, 166.76)
            dec["bounds_max"] = (0.05, 5.38, 166.76)
            dec["bounding_radius"] = 0.05
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id in col_mg_ids:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [dec["material_ids"][0]]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id in col_sb_ids:
            dec = dm.decode_skinbones(s.payload)
            dec["maps"] = [list(range(len(dec["objects"]))) for _ in range(2)]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        elif s.type == dm.CUSTOM_HASHLIST and inserted_hair_mat_sec is not None:
            dec = dm.decode_custom_hashlist(s.payload)
            if hair_mat_name not in dec["names"]:
                dec["names"].append(hair_mat_name)
            new_sections.append(dm.Section(s.type, s.id, dm.encode_custom_hashlist(dec)))
        else:
            new_sections.append(s)
            if s.id == head_mat_id and inserted_hair_mat_sec is not None:
                new_sections.append(inserted_hair_mat_sec)

    return dm.ModelFile(new_sections).write()


def disable_objects_in_xml(xml_bytes: bytes, obj_names: list[str]) -> bytes:
    """Set enabled=\"false\" on the given <object name=\"...\" .../> entries in a .object XML."""
    text = xml_bytes.decode("utf-8", errors="ignore")
    for name in obj_names:
        pattern = rf'(<object\s+name="{re.escape(name)}"\s+enabled=")true(")'
        text = re.sub(pattern, r"\1false\2", text)
    return text.encode("utf-8")


def patch_wild_material_config(xml_bytes: bytes, alpha_ref: str = "0.05") -> bytes:
    """Upgrade mtr_head in Rust's .material_config files to ALPHA_MASKED mip 0 on npc_criminal_wild_1_head_df/_nm."""
    text = xml_bytes.decode("utf-8", errors="ignore")
    new_head = (
        '<material name="mtr_head" unique="true" '
        'render_template="generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_3WEIGHTS" version="2">\n'
        '        <diffuse_texture file="units/pd2_dlc_wild/characters/npc_criminals_wild_1/npc_criminal_wild_1_head_df"/>\n'
        '        <bump_normal_texture file="units/pd2_dlc_wild/characters/npc_criminals_wild_1/npc_criminal_wild_1_head_nm"/>\n'
        f'        <variable value="{alpha_ref}" type="scalar" name="alpha_ref"/>\n'
        "    </material>"
    )
    text = re.sub(
        r'<material\s+[^>]*name="mtr_head"[^>]*>.*?</material>',
        new_head,
        text,
        flags=re.DOTALL,
    )
    return text.encode("utf-8")


def patch_old_hoxton_material_config(xml_bytes: bytes, alpha_ref: str = "0.05") -> bytes:
    """Upgrade `mtr_head` in Old Hoxton's .material_config to ALPHA_MASKED, keeping its texture paths.

    The suit-chill config points `mtr_head` at `shared_textures/old_hoxton_head_p_df/_nm`
    and the heist config at the non-`_p_` pair; the pack overrides all four textures,
    so only the render template changes: hair cards need ALPHA_MASKED with an external
    alpha_ref to cut out against the atlas' 0/24 hair alpha.
    """
    text = xml_bytes.decode("utf-8", errors="ignore")
    block_m = re.search(r'<material\s+[^>]*name="mtr_head"[^>]*>.*?</material>', text, flags=re.DOTALL)
    block = block_m.group(0) if block_m else ""
    df_m = re.search(r'<diffuse_texture\s+file="([^"]+)"', block)
    nm_m = re.search(r'<bump_normal_texture\s+file="([^"]+)"', block)
    df_rel = df_m.group(1) if df_m else f"{OLD_HOXTON_TEX_DIR}/old_hoxton_head_p_df"
    nm_rel = nm_m.group(1) if nm_m else f"{OLD_HOXTON_TEX_DIR}/old_hoxton_head_p_nm"
    new_head = (
        '<material name="mtr_head" unique="true" '
        'render_template="generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_3WEIGHTS" version="2">\n'
        f'        <diffuse_texture file="{df_rel}"/>\n'
        f'        <bump_normal_texture file="{nm_rel}"/>\n'
        f'        <variable value="{alpha_ref}" type="scalar" name="alpha_ref"/>\n'
        "    </material>"
    )
    text = re.sub(
        r'<material\s+[^>]*name="mtr_head"[^>]*>.*?</material>',
        new_head,
        text,
        flags=re.DOTALL,
    )
    return text.encode("utf-8")


def load_hila_eye_texture(size: int = 1024) -> np.ndarray:
    """Scale `references/textures/EYE_Diff.png` into the head atlas' eye quadrant, gloss in the alpha channel.

    The supplied diffuse is a 256x256 ME2 eyeball map: the iris is a small disc in the middle of a
    wide sclera field, because the game samples it through the eyeball's own spherical UVs. Both head
    pipelines here re-project the eyeball as a planar pass across the palpebral opening, so the image
    is magnified about its centre by `HILA_EYE_ZOOM` to bring its iris to the radius the synthesized
    eye used. Alpha is PD2 gloss, as in `build_crisp_miranda_eye_texture`: 10 on the iris, 8 on the
    sclera, 4 in the pupil.
    """
    src = np.asarray(Image.open(ROOT / HILA_EYE_SOURCE).convert("RGB"))
    side = int(round(src.shape[0] / HILA_EYE_ZOOM))
    lo = src.shape[0] // 2 - side // 2
    crop = src[lo : lo + side, lo : lo + side]
    rgb = np.asarray(Image.fromarray(crop).resize((size, size), Image.Resampling.LANCZOS))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    u = (xx + 0.5) / size - 0.5
    v = (yy + 0.5) / size - 0.5
    r = np.sqrt(u * u + v * v)
    rgba = np.dstack([rgb, np.where(r < 0.078, 4, np.where(r < 0.174, 10, 8)).astype(np.uint8)])
    return rgba



def match_romance_hila_skin_to_honoka(atlas: np.ndarray) -> np.ndarray:
    """Warm/lighten the face and scalp skin for Honoko without tinting hair, eyes or gloss.

    OfficeSuite's exposed upper-neck diffuse samples have median RGB around 204/152/123;
    Romance-over-Hila's adjacent scalp-skin samples are around 170/134/107. A restrained
    channel gain moves the two closer. A soft skin-colour mask preserves dark hair, lashes
    and mouth details; only the face and scalp quadrants are considered. Integer arithmetic
    makes the output deterministic across numpy and CPU implementations. This changes only
    the Romance Hila atlas, not the body or the other heister packs.
    """
    if atlas.shape != (2048, 2048, 4) or atlas.dtype != np.uint8:
        raise ValueError("expected a 2048x2048 uint8 RGBA head atlas")
    out = atlas.copy()
    gains = np.array([1200, 1140, 1180], dtype=np.int32)
    for x in (0, 1024):
        skin = out[:1024, x:x + 1024, :3]
        rgb = skin.astype(np.int32)
        red, green, blue = rgb.transpose(2, 0, 1)
        weight = np.minimum.reduce([
            np.clip((np.minimum(np.minimum(red, green), blue) - 40) * 255 // 35, 0, 255),
            np.clip((red - green - 5) * 255 // 10, 0, 255),
            np.clip((green - blue - 3) * 255 // 10, 0, 255),
        ])[..., None]
        target = (rgb * gains + 500) // 1000
        skin[:] = np.clip((rgb * (255 - weight) + target * weight + 127) // 255, 0, 255).astype(np.uint8)
    return out

def patch_hila_material_config(xml_bytes: bytes) -> bytes:
    """Point Hila's `mtr_head` at the atlas and drop the vanilla GSMA gloss map.

    The ECP head material is `generic:CONTOUR:DIFFUSE_TEXTURE:GSMA_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS`
    over `npc_criminal_ecp_female_head_gsma`, which was authored for Hila's own UVs. Every other
    heister's `mtr_head` carries gloss in the diffuse alpha instead, so the material becomes the same
    plain `generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:RL_PLAYERS:SKINNED_3WEIGHTS`. `mtr_lashes` is
    already `opacity:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS` and keeps its texture slots: the pack writes the
    shaved ME2 lash diffuse and its opacity map to exactly those two names.
    """
    text = xml_bytes.decode("utf-8", errors="ignore")
    new_head = (
        '<material name="mtr_head" unique="true" '
        'render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:RL_PLAYERS:SKINNED_3WEIGHTS" version="2">\n'
        f'        <diffuse_texture file="{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_head_df"/>\n'
        f'        <bump_normal_texture file="{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_head_nm"/>\n'
        '        <variable value="0 0 0" type="vector3" name="contour_color"/>\n'
        '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
        "    </material>"
    )
    text = re.sub(
        r'<material\s+[^>]*name="mtr_head"[^>]*>.*?</material>',
        new_head,
        text,
        flags=re.DOTALL,
    )
    return text.encode("utf-8")


def make_character_icon_dds(ada_icon_path: Path, portrait_rgb: Image.Image) -> bytes:
    """Create a 128x128 uncompressed BGRA8 DDS character icon in PAYDAY 2 high-contrast B&W style."""
    header = ada_icon_path.read_bytes()[:128]
    gray = portrait_rgb.convert("L").resize((128, 128), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    bg_mask = arr <= 34.0
    norm = np.clip((arr - 42.0) / 135.0, 0.0, 1.0)
    contrasted = np.power(norm, 0.85) * 255.0
    contrasted[bg_mask] = 0.0
    yy, xx = np.mgrid[0:128, 0:128]
    fade = np.clip((122.0 - yy) / 14.0, 0.0, 1.0)
    val = np.clip(contrasted * fade, 0.0, 255.0).astype(np.uint8)

    bgra = np.zeros((128, 128, 4), dtype=np.uint8)
    bgra[:, :, 0] = val
    bgra[:, :, 1] = val
    bgra[:, :, 2] = val
    bgra[:, :, 3] = 255
    return header + bgra.tobytes()


def render_head_portrait(atom0_mesh: dict, atom1_mesh: dict, atlas_rgb: np.ndarray, atom1_rgba: np.ndarray, alpha_cut: bool) -> Image.Image:
    """Render a front portrait of the head for the character icon."""
    W, H = 256, 256
    img = np.full((H, W, 3), [28, 30, 38], dtype=np.uint8)
    zbuf = np.full((H, W), -1e9, dtype=np.float32)
    light = np.array([0.20, 0.88, 0.42], dtype=np.float32)
    light /= np.linalg.norm(light)
    z_max_a1 = float(np.asarray(atom1_mesh["verts"], np.float32)[:, 2].max())
    if z_max_a1 > 189.0:
        z_center, scale = 176.5, 8.2
    else:
        z_center, scale = 173.5, 9.2

    for m, tex, is_cut in [(atom0_mesh, atlas_rgb, False), (atom1_mesh, atom1_rgba, alpha_cut)]:
        pos = np.asarray(m["verts"], np.float32)
        nrm = np.asarray(m["normals"], np.float32)
        tris = np.asarray(m["tris"], np.int32)
        uv = np.asarray(m["uvs"], np.float32)
        sx = (W * 0.5 + pos[:, 0] * scale).astype(np.float32)
        sy = (H * 0.5 - (pos[:, 2] - z_center) * scale).astype(np.float32)
        py = pos[:, 1]
        shade = np.clip(0.25 + 0.80 * np.maximum(0.0, nrm[:, 0] * light[0] + nrm[:, 1] * light[1] + nrm[:, 2] * light[2]), 0.15, 1.15)
        th, tw = tex.shape[:2]
        for a, b, c in tris:
            x0, x1, x2, y0, y1, y2 = sx[a], sx[b], sx[c], sy[a], sy[b], sy[c]
            ix_min, ix_max = max(0, int(min(x0, x1, x2))), min(W - 1, int(max(x0, x1, x2)) + 1)
            iy_min, iy_max = max(0, int(min(y0, y1, y2))), min(H - 1, int(max(y0, y1, y2)) + 1)
            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if denom <= 1e-5:
                continue
            inv_d = 1.0 / denom
            for py_i in range(iy_min, iy_max + 1):
                for px_i in range(ix_min, ix_max + 1):
                    w0 = ((y1 - y2) * (px_i - x2) + (x2 - x1) * (py_i - y2)) * inv_d
                    w1 = ((y2 - y0) * (px_i - x2) + (x0 - x2) * (py_i - y2)) * inv_d
                    w2 = 1.0 - w0 - w1
                    if w0 >= -1e-4 and w1 >= -1e-4 and w2 >= -1e-4:
                        z_p = w0 * py[a] + w1 * py[b] + w2 * py[c]
                        if z_p > zbuf[py_i, px_i]:
                            u_p = np.clip(w0 * uv[a, 0] + w1 * uv[b, 0] + w2 * uv[c, 0], 0.0, 1.0)
                            v_img_p = np.clip(1.0 - (w0 * uv[a, 1] + w1 * uv[b, 1] + w2 * uv[c, 1]), 0.0, 1.0)
                            tx_i, ty_i = int(u_p * (tw - 1)), int(v_img_p * (th - 1))
                            if is_cut and tex.shape[2] == 4 and tex[ty_i, tx_i, 3] < 15:
                                continue
                            sh = w0 * shade[a] + w1 * shade[b] + w2 * shade[c]
                            col = np.clip(tex[ty_i, tx_i, :3] * sh, 0, 255).astype(np.uint8)
                            zbuf[py_i, px_i] = z_p
                            img[py_i, px_i] = col
    return Image.fromarray(img)


def shade_nostril_cavities(face_rgba: np.ndarray) -> np.ndarray:
    """Darken the two nostril-cavity interior UV pockets and zero their specular gloss so inner nostril walls do not catch bright frontal highlights.

    Evaluated in double precision and cut off to bytes with a margin
    (`determinism.floor8`): in single precision the result depended on the
    math library of the machine that built the pack.
    """
    out = face_rgba.copy()
    H, W = out.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64) / float(H)
    right, left, down = (xx - 0.454) / 0.020, (xx - 0.559) / 0.020, (yy - 0.472) / 0.025
    d_min = np.minimum(np.sqrt(right * right + down * down), np.sqrt(left * left + down * down))
    w_nost = np.clip(1.0 - (d_min ** 1.6), 0.0, 1.0) * 0.90
    target_dark = np.array([14.0, 7.0, 5.0])
    for c_i in range(3):
        out[:, :, c_i] = determinism.floor8(
            out[:, :, c_i] * (1.0 - w_nost) + target_dark[c_i] * w_nost, "the nostrils of a head pack"
        )
    out[:, :, 3] = np.where(d_min < 1.0, np.minimum(out[:, :, 3], 2), out[:, :, 3]).astype(np.uint8)
    # Darken the upper eyelid lash margin + upper waterline so the upper lash line is crisp
    w_lash = np.zeros_like(xx)
    for uc, u_min, u_max in ((0.260, 0.190, 0.322), (0.747, 0.684, 0.808)):
        du = (xx - uc) / 0.062
        du2 = du * du
        v_center = 0.293 + 0.003 * du2
        dv = (yy - v_center) / 0.011
        w_eye = np.exp(-(du2 * du2) - (dv * dv) * 1.8) * (
            (xx >= u_min) & (xx <= u_max) & (yy <= 0.3055)
        )
        w_lash = np.maximum(w_lash, w_eye)
    near, far, low = (xx - 0.068) / 0.042, (xx - 0.927) / 0.036, (yy - 0.926) / 0.010
    w_wl = np.maximum(
        np.exp(-(near * near) * (near * near) - low * low),
        np.exp(-(far * far) * (far * far) - low * low),
    )
    w_l = np.clip(np.maximum(w_lash, w_wl) * 0.88, 0.0, 1.0)
    target_lash = np.array([18.0, 13.0, 11.0])
    for c_i in range(3):
        out[:, :, c_i] = determinism.floor8(
            out[:, :, c_i] * (1.0 - w_l) + target_lash[c_i] * w_l, "the lash lines of a head pack"
        )
    return out


def flatten_nostril_normals(face_nm_pd2: np.ndarray) -> np.ndarray:
    """Flatten PD2 normal map ([255, ny, 0, nx]) inside the two nostril UV pockets to neutral [255, 128, 0, 128]."""
    out = face_nm_pd2.copy()
    H, W = out.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) / float(H)
    d_min = np.minimum(
        np.hypot((xx - 0.454) / 0.022, (yy - 0.472) / 0.026),
        np.hypot((xx - 0.559) / 0.022, (yy - 0.472) / 0.026),
    )
    m = d_min < 1.0
    out[m, 0] = 255
    out[m, 1] = 128
    out[m, 2] = 0
    out[m, 3] = 128
    return out


def prepare_crisp_eyelash_textures(me2_dir: Path) -> tuple[np.ndarray, bytes, bytes]:
    """Load miranda_eyelashes.png and sharpen its alpha mask so semi-transparent strip halos don't smudge the eyelids."""
    lash_rgba = np.asarray(Image.open(me2_dir / "miranda_eyelashes.png").convert("RGBA")).copy()
    a_f = lash_rgba[:, :, 3].astype(np.float32)
    a_sharp = np.clip((a_f - 115.0) / 60.0, 0.0, 1.0) * 255.0
    lash_rgba[:, :, 3] = a_sharp.astype(np.uint8)
    # Soften pure-black (0,0,0) to deep espresso-black (18,14,12) so lashes blend naturally
    lash_rgba[:, :, 0] = 18
    lash_rgba[:, :, 1] = 14
    lash_rgba[:, :, 2] = 12
    lashes_df_dds = encode_rgba_dds(lash_rgba)
    lash_op = np.zeros_like(lash_rgba)
    lash_op[:, :, 0] = lash_rgba[:, :, 3]
    lash_op[:, :, 1] = lash_rgba[:, :, 3]
    lash_op[:, :, 2] = lash_rgba[:, :, 3]
    lash_op[:, :, 3] = 255
    lashes_op_dds = encode_rgba_dds(lash_op)
    return lash_rgba, lashes_df_dds, lashes_op_dds


def find_miranda_las_zip() -> Path:
    for candidate in (
        dist_path(ROOT, "Miranda_LAS.zip"),
        ROOT / "build" / "pd2-las" / "Miranda_LAS.zip",
        ROOT / "Miranda_LAS.zip",
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Missing dist/Miranda_L4D2/Miranda_L4D2_LAS.zip (run tools/pd2-las/build_models.py first)")


def write_deterministic_zip(files: dict[str, bytes], out_zip_paths: list[Path]) -> None:
    raw = las_outfit_pack.zip_bytes((name, files[name]) for name in sorted(files))
    for zp in out_zip_paths:
        zp.parent.mkdir(parents=True, exist_ok=True)
        zp.write_bytes(raw)
        sha = write_pack_checksum(zp, ROOT)
        print(f"Wrote {zp} ({len(raw):,} bytes, sha256={sha[:16]}…)")


def _emit_hila_packages(
    variant_tag: str,
    packed_suit_head: dict,
    head_df_dds: bytes,
    head_nm_dds: bytes,
    sec_df_dds: bytes,
    sec_op_dds: bytes,
    icon_dds: bytes,
) -> None:
    """Package Miranda over Hila (npc_criminals_ecp_female) from references/templates/npc_criminals_ecp_female.7z.

    Hila's `g_head` carries two atoms (head, 3D eyelashes) on `mtr_head` + `mtr_lashes`, and her hair
    lives in `g_hair_mask_off` / `g_hair_mask_on`, which are collapsed to the hidden triangle and
    disabled in both object files exactly like Sydney's. There is no Safe House (`*_chill`) unit for
    her, so the pack replaces the heist and menu models only.
    """
    hila_root = ensure_hila_extracted(EXTRACT_DIR / "ecp_female")
    hair_objs = ["g_hair_mask_off", "g_hair_mask_on"]
    model_bytes = patch_female_heister_model(
        (hila_root / f"{HILA_UNIT_STEM}.model").read_bytes(),
        head_drawables=["g_head"],
        collapse_drawables=hair_objs,
        head_mat_name="mtr_head",
        hair_mat_name="mtr_lashes",
        packed_head=packed_suit_head,
    )
    obj = disable_objects_in_xml(
        (hila_root / f"{HILA_UNIT_STEM}.object").read_bytes(), hair_objs
    )
    menu_obj = disable_objects_in_xml(
        (hila_root / f"{HILA_UNIT_STEM}_menu.object").read_bytes(), hair_objs
    )
    mtr = patch_hila_material_config(
        (hila_root / "mtr_criminal_ecp_female.material_config").read_bytes()
    )
    mtr_cc = patch_hila_material_config(
        (hila_root / "mtr_criminal_ecp_female_cc.material_config").read_bytes()
    )
    prefix = f"Miranda {variant_tag} over Hila"
    files = {
        f"{prefix}/{HILA_ICON_PATH}": icon_dds,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}.model": model_bytes,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_menu.model": model_bytes,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}.object": obj,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_menu.object": menu_obj,
        f"{prefix}/{HILA_UNIT_DIR}/mtr_criminal_ecp_female.material_config": mtr,
        f"{prefix}/{HILA_UNIT_DIR}/mtr_criminal_ecp_female_cc.material_config": mtr_cc,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_head_df.texture": head_df_dds,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_head_nm.texture": head_nm_dds,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_lashes_df.texture": sec_df_dds,
        f"{prefix}/{HILA_UNIT_DIR}/{HILA_UNIT_STEM}_lashes_op.texture": sec_op_dds,
    }
    write_deterministic_zip(files, [dist_path(ROOT, f"Miranda_{variant_tag}_over_Hila.zip")])


def build_l4d2_hila_head(ada_root: Path, me2_dir: Path, sec_nm_dds: bytes) -> None:
    """Build the L4D2 Miranda head and emit `Miranda_L4D2_over_Hila.zip`.

    The over Joy/Clover/Bonnie/Sydney variants this assembly used to write were retired in
    the dist clean-up, together with their zip; what remains is the assembly and the Hila
    pack it feeds (D80).
    """
    with zipfile.ZipFile(find_miranda_las_zip()) as zf:
        mir_bytes = zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
        face_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_df.texture"))).convert("RGBA")
        face_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_nm.texture"))).convert("RGBA")
        head_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_df.texture"))).convert("RGBA")
        head_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_nm.texture"))).convert("RGBA")
        body_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_df.texture"))).convert("RGBA")
        body_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_nm.texture"))).convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)

    body_df_arr = np.asarray(body_df_im).copy()
    by0, by1 = int(0.48 * body_df_arr.shape[0]), int(0.56 * body_df_arr.shape[0])
    bx0, bx1 = int(0.58 * body_df_arr.shape[1]), int(0.75 * body_df_arr.shape[1])
    bpatch = body_df_arr[by0:by1, bx0:bx1, :3]
    bskin_med = np.median(bpatch[bpatch.mean(axis=2) > 135], axis=0).astype(np.uint8)
    bpatch[bpatch.mean(axis=2) < 130] = bskin_med
    body_df_arr[by0:by1, bx0:bx1, :3] = bpatch

    crisp_eye_1024 = build_crisp_miranda_eye_texture(me2_dir, size=1024)

    atlas_df = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_df[0:1024, 0:1024] = np.asarray(face_df_im)
    atlas_df[0:1024, 1024:2048] = np.asarray(head_df_im)
    atlas_df[1024:2048, 0:1024] = body_df_arr
    atlas_df[1024:2048, 1024:2048] = crisp_eye_1024
    atlas_df[0:1024, 0:1024, 3] = np.minimum(atlas_df[0:1024, 0:1024, 3], 18)
    atlas_df[0:1024, 0:1024] = shade_nostril_cavities(atlas_df[0:1024, 0:1024])
    atlas_df[0:1024, 1024:2048, 3] = 16
    atlas_df[1024:2048, 0:1024, 3] = np.minimum(atlas_df[1024:2048, 0:1024, 3], 18)

    atlas_nm = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_nm[:, :] = [255, 128, 0, 128]
    atlas_nm[0:1024, 0:1024] = flatten_nostril_normals(np.asarray(face_nm_im))
    atlas_nm[0:1024, 1024:2048] = np.asarray(head_nm_im)
    atlas_nm[1024:2048, 0:1024] = np.asarray(body_nm_im)
    atlas_nm[:, :, 0] = 255
    atlas_nm[:, :, 2] = 0

    pm_mir = dm.ModelFile.read(mir_bytes)
    md_head = dm.decode_model_data(pm_mir.by_id(94).payload)
    pg_head = dm.decode_passthroughgp(pm_mir.by_id(md_head["passthroughgp"]).payload)
    geo_head = dm.decode_geometry(pm_mir.by_id(pg_head["geometry"]).payload)
    topo_head = np.array(dm.decode_topology(pm_mir.by_id(pg_head["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    vh = np.asarray(geo_head["verts"], dtype=np.float32)
    nh = np.asarray(geo_head["normals"], dtype=np.float32)
    uvh_img = np.column_stack([np.asarray(geo_head["uv0"])[:, 0], 1.0 - np.asarray(geo_head["uv0"])[:, 1]])

    # Fit rigid similarity transform from ME2 Face to L4D2 Face so Atom 1 can carry 3D Eyelashes
    dae_path = me2_dir / "Miranda Lawson (Romance) - Adjusted Version.dae"
    scene = me2_dae.load_dae(dae_path.read_bytes())
    m_me2_face = [m for m in scene.meshes if m.name == "Face"][0]
    m_me2_lashes = [m for m in scene.meshes if m.name == "Eyelashes"][0]
    a3 = md_head["atoms"][3]
    pos_l4d_face = np.asarray(geo_head["verts"], dtype=np.float64)[a3["base_vertex"] : a3["base_vertex"] + a3["slice_len"]]
    uv_l4d_face = np.asarray(geo_head["uv0"], dtype=np.float64)[a3["base_vertex"] : a3["base_vertex"] + a3["slice_len"]]
    pos_me2_face = np.asarray(m_me2_face.positions, dtype=np.float64)
    uv_me2_face = np.asarray(m_me2_face.uvs, dtype=np.float64)

    dists = np.linalg.norm(uv_l4d_face[:, None, :] - uv_me2_face[None, :, :], axis=2)
    nearest = dists.argmin(axis=1)
    P_src, P_tgt = pos_me2_face[nearest], pos_l4d_face
    mu_s, mu_t = P_src.mean(axis=0), P_tgt.mean(axis=0)
    U, S, Vt = np.linalg.svd((P_tgt - mu_t).T @ (P_src - mu_s))
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    scale = float(np.sum(S) / np.sum((P_src - mu_s) ** 2))
    t_vec = mu_t - scale * (R @ mu_s)
    lash_p = ((scale * (R @ np.asarray(m_me2_lashes.positions, dtype=np.float64).T)).T + t_vec).astype(np.float32)
    lash_n = (R @ np.asarray(m_me2_lashes.normals, dtype=np.float64).T).T.astype(np.float32)
    lash_uv = np.asarray(m_me2_lashes.uvs, dtype=np.float32)
    lash_tris = np.asarray(m_me2_lashes.triangles, dtype=np.int32)

    def build_l4d2_meshes(for_suit: bool) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        a0_verts, a0_norms, a0_uvs, a0_tris = [], [], [], []

        def append_part(target_v, target_n, target_uv, target_t, p, n, uv, t):
            offset = sum(len(x) for x in target_v)
            target_v.append(p)
            target_n.append(n)
            target_uv.append(uv)
            target_t.append(t + offset)

        # Extract Face (Atom 3, mid==1) and Scalp/Neck (Atom 4, mid==2) first so we can repair seam normals
        atoms_by_mid: dict[int, list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = {}
        for atom in md_head["atoms"]:
            bv, sl, bi, tc, mid = atom["base_vertex"], atom["slice_len"], atom["base_index"], atom["tri_count"], atom["material_id"]
            p_s = vh[bv : bv + sl].copy()
            n_s = nh[bv : bv + sl].copy()
            uv_s = uvh_img[bv : bv + sl].copy()
            t_s = topo_head[bi // 3 : bi // 3 + tc] - bv
            if mid == 3:
                if for_suit:
                    p_raw = p_s.copy()
                    n_raw = n_s.copy()
                    is_ns_raw = neck_skin_uv_island_mask(uv_s, t_s)
                    p_s = shape_neck_and_hair_for_suit_collar(p_s, uv_s, z_drop=5.4, y_push=3.0, x_flare=0.28, tris=t_s)
                    p_s, n_s, uv_s, t_s = extend_neck_skirt(p_s, n_s, uv_s, t_s)
                    p_s, n_s = blend_l4d2_scalp_and_neck_posture(p_raw, n_raw, p_s, n_s, is_ns_raw)
                else:
                    p_s = extend_scalp_neck_skin_into_collar(p_s, uv_s, z_drop=3.2, y_push=2.0, tris=t_s)
                    p_s = tuck_hair_for_joy_hood(p_s, uv_s, tris=t_s)
                    p_s, n_s, uv_s, t_s = extend_neck_skirt(p_s, n_s, uv_s, t_s)
            else:
                if mid == 0:
                    uv_s = project_me2_eye_uv_img(p_s)
                    n_s = soften_eyeball_normals(n_s)
                if for_suit:
                    p_s, n_s = rigid_l4d2_head_posture(p_s, n_s)
            atoms_by_mid.setdefault(mid, []).append((p_s, n_s, uv_s, t_s))

        face_p, face_n, face_uv, face_t = atoms_by_mid[1][0]
        scalp_p, scalp_n, scalp_uv, scalp_t = atoms_by_mid[3][0]
        face_n, scalp_n = repair_skin_and_neck_normals(
            face_p, face_n, face_t, scalp_p, scalp_n, scalp_uv, scalp_t
        )
        atoms_by_mid[1][0] = (face_p, face_n, face_uv, face_t)
        atoms_by_mid[3][0] = (scalp_p, scalp_n, scalp_uv, scalp_t)

        mat_quad = {1: (0, 0), 2: (1, 0), 3: (1, 0), 0: (1, 1)}
        for mid in (3, 0, 1, 2):
            qx, qy = mat_quad[mid]
            for p_s, n_s, uv_s, t_s in atoms_by_mid.get(mid, []):
                uv_q = map_uv_to_quadrant(uv_s, qx, qy)
                append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p_s, n_s, uv_q, t_s)

        if for_suit:
            lp_out, ln_out = rigid_l4d2_head_posture(lash_p, lash_n)
        else:
            lp_out, ln_out = lash_p.copy(), lash_n.copy()

        return (
            {
                "verts": np.vstack(a0_verts),
                "normals": np.vstack(a0_norms),
                "uvs": np.vstack(a0_uvs),
                "tris": np.vstack(a0_tris),
            },
            {
                "verts": lp_out,
                "normals": ln_out,
                "uvs": lash_uv.copy(),
                "tris": lash_tris.copy(),
            },
        )

    atom0_joy, atom1_joy = build_l4d2_meshes(for_suit=False)
    atom0_suit, atom1_suit = build_l4d2_meshes(for_suit=True)
    packed_suit_head = _prepare_combined_head_arrays(
        atom0_suit, atom1_suit, bone_offset=1, orthonormal_tangents=True
    )

    lash_rgba, lashes_df_dds, lashes_op_dds = prepare_crisp_eyelash_textures(me2_dir)
    eyes_df_dds = lashes_df_dds

    head_nm_dds = encode_rgba_dds(atlas_nm)

    portrait = render_head_portrait(atom0_joy, atom1_joy, atlas_df[:, :, :3], lash_rgba, alpha_cut=True)
    icon_dds = make_character_icon_dds(ada_root / JOY_ICON_PATH, portrait)

    hila_atlas_df = atlas_df.copy()
    hila_atlas_df[1024:2048, 1024:2048] = load_hila_eye_texture()
    _emit_hila_packages(
        variant_tag="L4D2",
        packed_suit_head=packed_suit_head,
        head_df_dds=encode_rgba_dds(hila_atlas_df),
        head_nm_dds=head_nm_dds,
        sec_df_dds=eyes_df_dds,
        sec_op_dds=lashes_op_dds,
        icon_dds=icon_dds,
    )


def build_geralt_rust_mod(ada_root: Path, geralt_root: Path, out_zip_paths: list[Path]) -> None:
    """Build Witcher 3 Geralt of Rivia head replacement over Rust (npc_criminal_wild_1)."""
    gm = sm.load_model(
        (geralt_root / "models" / "survivors" / "survivor_gambler.mdl").read_bytes(),
        (geralt_root / "models" / "survivors" / "survivor_gambler.vvd").read_bytes(),
        (geralt_root / "models" / "survivors" / "survivor_gambler.dx90.vtx").read_bytes(),
    )

    vtf_by_lower = {p.stem.lower(): p for p in geralt_root.rglob("*.vtf")}

    def load_vtf_rgba(stem: str, size: tuple[int, int] | None = None) -> np.ndarray:
        vimg = vtf_mod.parse_vtf(vtf_by_lower[stem.lower()].read_bytes())
        im = Image.open(io.BytesIO(vtf_mod.to_dds(vimg))).convert("RGBA")
        if size is not None and im.size != size:
            rgb = np.asarray(im.convert("RGB").resize(size, Image.Resampling.LANCZOS))
            alpha = np.asarray(im.getchannel("A").resize(size, Image.Resampling.LANCZOS))
            return np.dstack([rgb, alpha]).copy()
        return np.asarray(im).copy()

    def load_pd2_nm(stem: str, size: tuple[int, int]) -> np.ndarray:
        arr = load_vtf_rgba(stem, size)
        return dds.pd2_normal_channels(arr, invert_y=True).copy()

    # Unified 2048x2048 atlas in npc_criminal_wild_1_head_df / _nm (single vanilla mtr_head with ALPHA_MASKED, alpha_ref=0.05):
    # Top half y in [0, 1024] (100% opaque with low natural specular alpha=18..28 > 13):
    # - [0:1024, 0:1024]     (u in [0.00, 0.50], v_img in [0.00, 0.50]): Geralt_head_BM (1024x1024, alpha=18)
    # - [0:512, 1024:2048]   (u in [0.50, 1.00], v_img in [0.00, 0.25]): Teeths_BM (1024x512 native, alpha=18)
    # - [512:1024, 1024:1536] (u in [0.50, 0.75], v_img in [0.25, 0.50]): Eyes_BM (512x512 native, alpha=28)
    # Bottom half y in [1024, 2048] (cutout alpha=0 vs opaque alpha=22 > 13 for ALPHA_MASKED alpha_ref=0.05):
    # - [1024:2048, 0:1024]    (u in [0.00, 0.50], v_img in [0.50, 1.00]): hair_d (1024x1024)
    # - [1024:1536, 1024:2048] (u in [0.50, 1.00], v_img in [0.50, 0.75]): beard_d (1024x512 native)
    # - [1536:2048, 1024:1536] (u in [0.50, 0.75], v_img in [0.75, 1.00]): eyelashes (512x512 native)
    head_df_atlas = np.zeros((2048, 2048, 4), dtype=np.uint8)
    head_df_atlas[0:1024, 0:2048, 3] = 18

    head_bm_arr = load_vtf_rgba("geralt_head_bm", (1024, 1024))
    head_bm_arr[:, :, 3] = 18
    teeth_bm_arr = load_vtf_rgba("teeths_bm", (1024, 512))
    teeth_bm_arr[:, :, 3] = 18
    eyes_bm_arr = load_vtf_rgba("eyes_bm", (512, 512))
    eyes_bm_arr[:, :, 3] = 28

    hair_arr = load_vtf_rgba("hair_d", (1024, 1024))
    hair_arr[:, :, :3] = np.clip(hair_arr[:, :, :3].astype(np.float32) * 0.86, 0, 255).astype(np.uint8)
    hair_mask = (hair_arr[:, :, 3] >= 25).astype(np.int32)
    # Remove only isolated 1px specks (neigh_sum == 1) while preserving 1px diagonal temple hair strands
    padded = np.pad(hair_mask, 1, mode="edge")
    neigh_sum = sum(padded[dy : dy + 1024, dx : dx + 1024] for dy in range(3) for dx in range(3))
    hair_keep = (hair_mask == 1) & (neigh_sum >= 2)
    hair_arr[:, :, 3] = np.where(hair_keep, 24, 0).astype(np.uint8)

    beard_arr = load_vtf_rgba("beard_d", (1024, 512))
    beard_rgb_scaled = np.clip(beard_arr[:, :, :3].astype(np.float32) * 0.90, 0, 255)
    beard_core = beard_arr[:, :, 3] >= 12
    pad_b = np.pad(beard_core.astype(np.int32), 1, mode="edge")
    pad_rgb = np.pad(beard_rgb_scaled * beard_core[:, :, None], ((1, 1), (1, 1), (0, 0)), mode="edge")
    b_cnt = sum(pad_b[dy : dy + 512, dx : dx + 1024] for dy in range(3) for dx in range(3))
    b_rgb_sum = sum(pad_rgb[dy : dy + 512, dx : dx + 1024] for dy in range(3) for dx in range(3))
    beard_dil = b_cnt > 0
    fringe = beard_dil & (~beard_core)
    beard_rgb_scaled[fringe] = b_rgb_sum[fringe] / np.maximum(b_cnt[fringe, None], 1)
    beard_arr[:, :, :3] = np.clip(beard_rgb_scaled, 0, 255).astype(np.uint8)
    beard_arr[:, :, 3] = np.where(beard_dil, 24, 0).astype(np.uint8)

    lash_arr = load_vtf_rgba("eyelashes", (512, 512))
    lash_arr[:, :, 3] = np.where(lash_arr[:, :, 3] >= 25, 24, 0).astype(np.uint8)

    head_df_atlas[0:1024, 0:1024] = head_bm_arr
    head_df_atlas[0:512, 1024:2048] = teeth_bm_arr
    head_df_atlas[512:1024, 1024:1536] = eyes_bm_arr
    head_df_atlas[1024:2048, 0:1024] = hair_arr
    head_df_atlas[1024:1536, 1024:2048] = beard_arr
    head_df_atlas[1536:2048, 1024:1536] = lash_arr

    head_nm_atlas = np.zeros((2048, 2048, 4), dtype=np.uint8)
    head_nm_atlas[:, :] = [255, 128, 0, 128]
    head_nm_atlas[0:1024, 0:1024] = load_pd2_nm("geralt_head_nm", (1024, 1024))
    head_nm_atlas[0:512, 1024:2048] = load_pd2_nm("teeths_nm", (1024, 512))
    head_nm_atlas[1024:2048, 0:1024] = load_pd2_nm("hair_n", (1024, 1024))
    head_nm_atlas[1024:1536, 1024:2048] = load_pd2_nm("beard_n", (1024, 512))
    head_nm_atlas[:, :, 0] = 255
    head_nm_atlas[:, :, 2] = 0

    src_anchor = np.array([0.0, 4.43, 65.80], dtype=np.float32)
    dst_anchor = np.array([0.0, 19.3, 171.8], dtype=np.float32)
    scale = 2.62

    def extract_geralt_part(
        mat_name: str, u_off: float, u_scale: float, v_off: float, v_scale: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        m = next(x for x in gm.meshes if x.material == mat_name)
        # Swap (a, b, c) -> (a, c, b) to convert Source Engine CW winding to PAYDAY 2 Diesel CCW winding
        idx = np.asarray(m.triangle_indices, dtype=np.int32).reshape(-1, 3)[:, [0, 2, 1]]

        p_raw = np.array([gm.vertices[vi].pos for vi in idx.ravel()], dtype=np.float32)
        n_raw = np.array([gm.vertices[vi].normal for vi in idx.ravel()], dtype=np.float32)
        uv_raw = np.array([gm.vertices[vi].uv for vi in idx.ravel()], dtype=np.float32).reshape(-1, 3, 2)

        # Shift all 3 vertices of each triangle by the same integer UV tile offset
        u_tile = np.floor(uv_raw[:, :, 0].mean(axis=1, keepdims=True))
        v_tile = np.floor(uv_raw[:, :, 1].mean(axis=1, keepdims=True))
        u_img = np.clip(uv_raw[:, :, 0] - u_tile, 0.002, 0.998).ravel()
        v_img = np.clip(uv_raw[:, :, 1] - v_tile, 0.002, 0.998).ravel()

        p_rot = np.column_stack([-p_raw[:, 0], -p_raw[:, 1], p_raw[:, 2]])
        n_rot = np.column_stack([-n_raw[:, 0], -n_raw[:, 1], n_raw[:, 2]])
        p = (p_rot - src_anchor) * scale + dst_anchor
        n = n_rot.copy()
        t = np.arange(len(p), dtype=np.int32).reshape(-1, 3)

        if mat_name == "Geralt_head_BM":
            w_bot = np.clip((163.8 - p[:, 2]) / 5.5, 0.0, 1.0)
            w_front = np.clip((p[:, 1] - 1.0) / 7.0, 0.0, 1.0)
            w_back = np.clip((1.0 - p[:, 1]) / 6.0, 0.0, 1.0)
            p[:, 2] -= 4.8 * (w_bot ** 1.1)
            p[:, 0] *= 1.0 + 0.12 * (w_bot ** 1.4)
            p[:, 1] += 0.45 * w_bot * w_front - 0.5 * w_bot * w_back
        elif mat_name == "hair_d":
            w_low = np.clip((161.5 - p[:, 2]) / 6.5, 0.0, 1.0)
            p[:, 0] *= 1.0 - 0.10 * (w_low ** 1.2)
            p[:, 2] -= 1.8 * w_low
            center = np.array([0.0, 4.0, 172.0], dtype=np.float32)
            radial = p - center
            radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-6)
            dot = np.sum(n * radial, axis=1)
            n[dot < -0.05] *= -1.0
            n = 0.75 * n + 0.25 * radial
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        elif mat_name == "beard_d":
            p[:, 1] += 0.18
            p[:, 0] += 0.06 * np.sign(p[:, 0])
        elif mat_name == "Eyes_BM":
            n = soften_eyeball_normals(n)

        u_atlas = u_off + u_scale * u_img
        v_img_atlas = v_off + v_scale * v_img
        uv_diesel = np.column_stack([u_atlas, 1.0 - v_img_atlas]).astype(np.float32)
        return p, n.astype(np.float32), uv_diesel, t

    a0_v, a0_n, a0_uv, a0_t = [], [], [], []
    for mname, uo, us, vo, vs in [
        ("Geralt_head_BM", 0.0, 0.5, 0.0, 0.5),
        ("Teeths_BM", 0.5, 0.5, 0.0, 0.25),
        ("Eyes_BM", 0.5, 0.25, 0.25, 0.25),
    ]:
        p, n, uv, t = extract_geralt_part(mname, uo, us, vo, vs)
        off = sum(len(x) for x in a0_v)
        a0_v.append(p)
        a0_n.append(n)
        a0_uv.append(uv)
        a0_t.append(t + off)

    a1_v, a1_n, a1_uv, a1_t = [], [], [], []
    for mname, uo, us, vo, vs in [
        ("hair_d", 0.0, 0.5, 0.5, 0.5),
        ("beard_d", 0.5, 0.5, 0.5, 0.25),
        ("eyelashes", 0.5, 0.25, 0.75, 0.25),
    ]:
        p, n, uv, t = extract_geralt_part(mname, uo, us, vo, vs)
        off = sum(len(x) for x in a1_v)
        a1_v.append(p)
        a1_n.append(n)
        a1_uv.append(uv)
        a1_t.append(t + off)

    atom0_mesh = {
        "verts": np.vstack(a0_v),
        "normals": np.vstack(a0_n),
        "uvs": np.vstack(a0_uv),
        "tris": np.vstack(a0_t),
    }
    atom1_mesh = {
        "verts": np.vstack(a1_v),
        "normals": np.vstack(a1_n),
        "uvs": np.vstack(a1_uv),
        "tris": np.vstack(a1_t),
    }

    packed_rust_head = _prepare_combined_head_arrays(
        atom0_mesh,
        atom1_mesh,
        bone_offset=1,
        jaw_lift=7.5,
        single_atom=True,
        double_side_atom1=True,
    )

    def encode_geralt_head_df_dds(arr: np.ndarray) -> bytes:
        """Encode Geralt's 2048x2048 head_df atlas with coverage-preserving alpha mipmaps in the cutout bottom half."""
        return encode_cutout_head_df_dds(arr)

    head_df_dds = encode_geralt_head_df_dds(head_df_atlas)
    head_nm_dds = encode_rgba_dds(head_nm_atlas)

    portrait = render_head_portrait(
        atom0_mesh, atom1_mesh, head_df_atlas[:, :, :3], head_df_atlas, alpha_cut=True
    )
    icon_dds = make_character_icon_dds(ada_root / JOY_ICON_PATH, portrait)

    fps_zip = ROOT / "references" / "templates" / "Heister - FPS Gloves in TPS 2.zip"
    with zipfile.ZipFile(fps_zip) as zf:
        rust_model = patch_female_heister_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{WILD_UNIT_DIR}/npc_criminal_wild_1.model"),
            head_drawables=["g_head"],
            collapse_drawables=[],
            head_mat_name="mtr_head",
            hair_mat_name=None,
            packed_head=packed_rust_head,
        )
        rust_obj = zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{WILD_UNIT_DIR}/npc_criminal_wild_1.object")
        rust_menu_obj = zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{WILD_UNIT_DIR}/npc_criminal_wild_1_menu.object")
        rust_mtr = patch_wild_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{WILD_UNIT_DIR}/mtr_criminal_wild_1.material_config"),
            alpha_ref="0.05",
        )
        rust_mtr_cc = patch_wild_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{WILD_UNIT_DIR}/mtr_criminal_wild_1_cc.material_config"),
            alpha_ref="0.05",
        )
        rust_chill_mtr = patch_wild_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/mtr_criminal_wild_1.material_config"),
            alpha_ref="0.05",
        )

    prefix = "Geralt over Rust"
    files = {
        f"{prefix}/{WILD_ICON_PATH}": icon_dds,
        f"{prefix}/{WILD_UNIT_DIR}/npc_criminal_wild_1.model": rust_model,
        f"{prefix}/{WILD_UNIT_DIR}/npc_criminal_wild_1_menu.model": rust_model,
        f"{prefix}/{WILD_UNIT_DIR}/npc_criminal_wild_1.object": rust_obj,
        f"{prefix}/{WILD_UNIT_DIR}/npc_criminal_wild_1_menu.object": rust_menu_obj,
        f"{prefix}/{WILD_UNIT_DIR}/mtr_criminal_wild_1.material_config": rust_mtr,
        f"{prefix}/{WILD_UNIT_DIR}/mtr_criminal_wild_1_cc.material_config": rust_mtr_cc,
        f"{prefix}/{CHILL_UNIT_DIR}/mtr_criminal_wild_1.material_config": rust_chill_mtr,
        f"{prefix}/{WILD_UNIT_DIR}/npc_criminal_wild_1_head_df.texture": head_df_dds,
        f"{prefix}/{WILD_UNIT_DIR}/npc_criminal_wild_1_head_nm.texture": head_nm_dds,
    }
    write_deterministic_zip(files, out_zip_paths)


#: Clean-skin patches of the Random4 head raster, used for its tone and its detail
ARIVUS_SKIN_PATCHES = ((112, 150, 200, 320), (196, 216, 178, 225),
                       (196, 216, 300, 347), (300, 330, 190, 232))
#: The cleanest patch of the same raster: the structure the fill borrows (D64)
ARIVUS_DETAIL_PATCH = (118, 150, 196, 330)
#: The rows the painted mouth occupies on the same raster (`y 252..288`): a column's lip
#: span is clipped to them so the chin hair under the lower lip cannot join the lips.
LIP_ROWS = slice(252, 289)


def _blur(arr: np.ndarray, radius: float) -> np.ndarray:
    """Gaussian blur of a 2-D float array, in the raster's own 8-bit space."""
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)


def _smooth_mask(mask: np.ndarray, radius: float) -> np.ndarray:
    """A 0..1 version of a boolean mask, blurred: the ramp used to feather an edge."""
    im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(im, dtype=np.float32) / 255.0


def shave_arivus_face(cell: np.ndarray) -> np.ndarray:
    """Erase the Random4 ped's painted beard, moustache and sideburns from its head raster.

    The ped has no beard geometry: the hair is painted into `head_diff_000_a_whi`
    as one dark blob that runs from the temples down around the jaw. A clean-shave
    look therefore means inpainting that region with skin taken from around it —
    and following the paint itself, not a hand-drawn box around it.

    Four passes, in this order (D72):

    * **Find the beard.** The geometric U of D64 ran diagonally across the clean cheeks
      and its sideburn boxes were 88 px wide, so the inpaint covered a rectangle under a
      pale forehead. The mask now floods from the raster's own dark hairs through the
      softer stubble, but only inside the zone a beard can occupy (the lower face and
      narrow strips in front of the ears). Ear pixels are kept by their pink chroma; the
      darker, low-redness hairs that overlap the ear ellipse are given to the mask.
    * **Harmonic fill** of the masked pixels: a Laplace relaxation from the clean
      skin ring around them, started flat from the skin tone, so the jaw picks up the
      real shading of its surroundings rather than a patch of one colour.
    * **Tone and detail.** The fill is then matched to the mean of the clean skin just
      outside it (a gain of at most ±15%, so it cannot invent shading), and given the
      high-frequency structure of a clean patch of the same raster - pores, freckles,
      the fine grain of the source - mirrored and tiled so it does not repeat as a grid.
    * **Feather.** The filled result is blended into the untouched raster over a couple
      of pixels, so the mask's outline is not an edge.

    Lips, nostrils, ears and eyebrows are protected and pasted back verbatim. Fixed
    512x512 layout, no randomness: the same raster always produces the same bytes.
    """
    rgb = cell[:, :, :3].astype(np.float32)
    H, W = rgb.shape[:2]
    if (H, W) != (512, 512):
        raise ValueError(f"Random4 head atlas is 512x512, got {W}x{H}")
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W]

    samples = [rgb[y0:y1, x0:x1].reshape(-1, 3) for y0, y1, x0, x1 in ARIVUS_SKIN_PATCHES]
    lums = [lum[y0:y1, x0:x1].ravel() for y0, y1, x0, x1 in ARIVUS_SKIN_PATCHES]
    skin = np.median(np.concatenate(samples), axis=0)
    skin_lum = float(np.median(np.concatenate(lums)))

    # --- pixels that belong to the face itself and must survive the paint-out ---
    protect = np.zeros((H, W), dtype=bool)
    feature = np.zeros((H, W), dtype=bool)
    for cx, cy, rx, ry in ((110, 210, 21, 34), (419, 210, 21, 34)):  # ears
        protect |= ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    for cx, cy, r in ((244, 230, 6), (266, 230, 6)):  # nostril openings
        protect |= (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    # lips: the painted mouth. Measured, not guessed: on this raster the lip-coloured
    # pixels (redness 52..64 against the moustache's ~35) fill x 210..298, y 252..292.
    # Those pixels alone would leave the mouth slit - the dark line between the two
    # lips - to be painted over, and a ring of beard around them to be pasted back, so
    # each column keeps the span from its top lip pixel to its bottom one (that span is
    # the slit) and the result grows by one pixel for the lip's own antialiased outline.
    redness = rgb[:, :, 0] - (rgb[:, :, 1] + rgb[:, :, 2]) / 2.0
    # The ear ellipse overlaps the painted sideburn in front of it. Keeping the whole
    # ellipse pastes that hair straight back (the dark strip beside the ear in the sheet);
    # the ear itself is pinker than the hair (redness ~37..49 against ~25..30), so give back
    # only the dark, low-redness pixels of the ellipse to the mask and keep the ear verbatim.
    ear_hair = np.zeros((H, W), dtype=bool)
    ear_hair |= ((xx - 110) / 21.0) ** 2 + ((yy - 210) / 34.0) ** 2 <= 1.0
    ear_hair &= xx >= 120  # only the cheek-facing edge of the left ellipse
    right_ear = ((xx - 419) / 21.0) ** 2 + ((yy - 210) / 34.0) ** 2 <= 1.0
    ear_hair |= right_ear & (xx <= 410)  # and the cheek-facing edge of the right one
    ear_hair &= (redness <= 33.0) & (lum <= 115.0)
    protect &= ~ear_hair
    feature &= ~ear_hair
    mouth_oval = ((xx - 254) / 44.0) ** 2 + ((yy - 270) / 18.0) ** 2 <= 1.0
    lip_core = mouth_oval & (redness > 48.0) & (lum > 66.0)
    lip = np.zeros((H, W), dtype=bool)
    for col in np.nonzero(mouth_oval.any(axis=0))[0]:
        # the span is clipped to the mouth's own rows: the shadow under the lower lip is
        # reddish and bright enough to pass the lip test, and letting a column's bottom
        # follow it pastes the chin hairs back on (which is what the portrait showed)
        rows = np.nonzero(lip_core[LIP_ROWS, col])[0]
        if rows.size:
            lip[rows.min() + LIP_ROWS.start:rows.max() + LIP_ROWS.start + 1, col] = True
    lip &= mouth_oval
    # The ped paints sparse hairs straight onto the skin under the lower lip, and a few of
    # them are reddish enough to pass the lip test and join the protected set - which pastes
    # a "soul patch" back on a clean-shaven face. Below the mouth slit they are given back to
    # the mask; the slit itself (above this line) stays protected with the lips.
    if lip.any():
        under_lip = yy > 276
        scars = under_lip & (lum < 0.70 * skin_lum)
        # The column span also sweeps up two dark moustache ticks at the mouth's
        # corners. Near the ends of the mouth the slit is pinker than the hair: give
        # back the low-redness pixels there, while keeping the central dark slit.
        corners = (((xx < 222) | (xx > 286)) & (redness < 30.0)
                   & (lum < 0.72 * skin_lum))
        lip &= ~(scars | corners)
    protect |= lip
    feature |= protect
    # eyebrows: the dark blobs that sit above the eye line
    seen = np.zeros((H, W), dtype=bool)
    brow = np.zeros((H, W), dtype=bool)
    for y0 in range(140, 200):
        for x0 in range(150, 370):
            if lum[y0, x0] >= 128 or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            pts = []
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 140 <= ny < 200 and 150 <= nx < 370 and not seen[ny, nx] and lum[ny, nx] < 128:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            # A brow is a wide, flat arc; a sideburn can touch the same scan band
            # but is tall and narrow, so keep it out of the protected set.
            if len(pts) > 600 and min(ys) < 172 and (max(xs) - min(xs)) > 55 and (max(ys) - min(ys)) < 55:
                for py, px in pts:
                    brow[py, px] = True
    brow = np.asarray(
        Image.fromarray((brow * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    ) > 127
    protect |= brow

    # --- find the beard from its own pixels, not from a rectangle ---
    # The old "geometric U" ran diagonally from each temple to the moustache, and the sideburn
    # boxes were 88 px wide. Between them they covered the clean cheeks, eye corners and the
    # bridge of the nose: the raster came out as one dark rectangle under a pale forehead (the
    # 2026-11-25 sheet showed its edge on the face, not just in the atlas). The paint itself is
    # easy to separate - the beard's hairs read 35..100 in luminance against ~140 on the clean
    # cheek - so seed on the dark hairs and flood through the softer, reddish stubble, but only
    # inside the zone a beard can occupy. A flood over the whole face (D64's first attempt)
    # crossed the eye sockets and the nose's flank; this one cannot.
    lower_zone = (yy >= 232) & (yy <= 338) & (xx >= 104) & (xx <= 416)
    side_zone = ((yy >= 142) & (yy <= 266)
                 & ((xx >= 106) & (xx <= 170) | (xx >= 362) & (xx <= 420)))
    beard_zone = (lower_zone | side_zone) & ~protect
    seed = beard_zone & (lum < 0.70 * skin_lum)
    # The temple shadows are broad but hairless; a flood as permissive as the jaw's
    # would follow them to a straight box edge, so the sideburns need a tighter cut.
    stubble = (lower_zone & (lum < 0.86 * skin_lum)) | (side_zone & (lum < 0.78 * skin_lum))
    mask = seed.copy()
    queue = deque(map(tuple, np.argwhere(seed)))
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < H and 0 <= nx < W and stubble[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                queue.append((ny, nx))
    # The hairs leave bright gaps between strokes: close those, restore the outline, then
    # take a couple of pixels of the soft painted edge. The original features are pasted
    # back at the end, so nothing here reaches into a lip, an eye or an ear.
    mask = np.asarray(
        Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    ) > 127
    mask = np.asarray(
        Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))
    ) > 127
    mask = np.asarray(
        Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    ) > 127
    # Ring the mouth, nose and ears with inpainted skin, but only where the beard was:
    # dilating every feature across the upper face is what left pale blobs beside the nose.
    ring = np.asarray(
        Image.fromarray((feature * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(11))
    ) > 127
    mask |= ring & beard_zone
    mask &= ~protect

    # --- harmonic fill from clean skin only ---
    # Relaxation over the masked pixels, starting from the skin tone. The
    # protected features are kept out of the boundary (weight 0) so the lips'
    # dark shading does not bleed into the jaw as a halo: the fill takes its
    # shading from the clean cheeks and neck around the beard.
    out = rgb.copy()
    out[mask] = skin
    y0, y1, x0, x1 = 126, 356, 108, 416
    sub = out[y0:y1, x0:x1]
    mm = mask[y0:y1, x0:x1]
    hgt, wid = sub.shape[:2]
    wgt = (~protect[y0:y1, x0:x1]).astype(np.float32)
    pw = np.pad(wgt, 1, mode="constant")
    # the 8-neighbourhood as (row offset, column offset) slices into the padded box
    offsets = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2))
    w_slices = [pw[a:a + hgt, b:b + wid] for a, b in offsets]
    for _ in range(900):
        pad = np.pad(sub, ((1, 1), (1, 1), (0, 0)), mode="edge")
        num = np.zeros_like(sub)
        den = np.zeros((hgt, wid), np.float32)
        for (a, b), wsl in zip(offsets, w_slices):
            num += pad[a:a + hgt, b:b + wid] * wsl[:, :, None]
            den += wsl
        good = mm & (den > 0)
        sub[good] = num[good] / den[good][:, None]

    # --- sweep the specks the growth could not reach ---
    # A painted edge that thins into single hairs leaves them stranded where the rim stops,
    # and a hair on a flat cheek reads as a freckle. Anything inside the filled area (plus a
    # two-pixel skirt) that is much darker than the fill around it becomes that fill.
    filled = np.clip(np.rint(sub), 0, 255).astype(np.uint8)
    local = np.stack(
        [_blur(filled[:, :, c].astype(np.float32), 3.0) for c in range(3)], axis=2
    )
    band = np.asarray(
        Image.fromarray((mm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    ) > 127
    filled_lum = filled.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    local_lum = local @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    specks = band & (filled_lum < 0.80 * local_lum)
    sub[specks] = local[specks]

    # --- the fill takes the level of the clean skin just outside it ---
    ring_w = np.clip(_smooth_mask(mask, 6.0) - _smooth_mask(mask, 1.5), 0.0, 1.0)
    ring_sel = (ring_w > 0.25) & ~mask
    for c in range(3):
        ref = float(rgb[:, :, c][ring_sel].mean()) if ring_sel.any() else float(skin[c])
        got = float(sub[:, :, c][mm].mean())
        if got > 1e-3 and ref > 1e-3:
            sub[:, :, c][mm] *= float(np.clip(ref / got, 0.85, 1.15))

    # --- and the structure of real skin, from a clean patch of the same raster ---
    sy0, sy1, sx0, sx1 = ARIVUS_DETAIL_PATCH
    patch = rgb[sy0:sy1, sx0:sx1]
    high = patch - np.stack([_blur(patch[:, :, c], 2.0) for c in range(3)], axis=2)
    # mirrored in both axes before tiling, so the patch's own edges do not read as a grid
    tile = np.concatenate([high, high[::-1]], axis=0)
    tile = np.concatenate([tile, tile[:, ::-1]], axis=1)
    reps = (int(np.ceil(hgt / tile.shape[0])) + 1, int(np.ceil(wid / tile.shape[1])) + 1)
    detail = np.tile(tile, (reps[0], reps[1], 1))[:hgt, :wid]
    sub[mm] = np.clip(sub[mm] + 1.10 * detail[mm], 0, 255)

    # --- one even skin field over the shaved area ---
    # This ped paints its stubble in two layers: a reddish one under the hairs, and the hairs
    # over it. The fill takes the hairs away, but the rim can only follow the painted edge so
    # far, and the detail pass above adds the clean patch's grain at 1.1x - between them the
    # cheek and the jaw still read as soot in the 2026-11-25 portrait ("still need work on
    # textures"). So the shaved area is flattened into one field: its own low-frequency
    # shading, this raster's own skin chroma (so no red mottle survives), and a third of its
    # detail, which keeps it skin rather than a mannequin's cheek.
    own_lum = sub @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    # The chroma reference is the clean skin *around this mask*, not the whole-raster median:
    # that median is the pale forehead, and using it left the jaw a shade cooler than the
    # cheeks it meets - which is what makes an inpainted patch read as a patch.
    near = np.clip(_smooth_mask(mask, 9.0) - _smooth_mask(mask, 4.0), 0.0, 1.0) > 0.12
    near &= ~mask
    ref_col = (np.median(rgb[near], axis=0) if near.any() else skin).astype(np.float32)
    ref_lum = float(ref_col @ np.array([0.299, 0.587, 0.114], dtype=np.float32))
    skin_unit = ref_col / max(ref_lum, 1e-3)
    toned = skin_unit[None, None, :] * own_lum[..., None]
    # Its own luminance (so every wrinkle and shadow stays) on that chroma (so the stubble's
    # red cast is gone), keeping a third of the original colour so the field is not one
    # airbrushed tone - a fully flattened cheek reads as a grey mask against the untouched
    # skin around it, which the first attempt at this showed. The mix is *faded* outward from
    # the mask over ~9 px instead of stamped over a grown zone: a binary zone leaves a soft
    # rectangle of its own, which is the same failure by another route.
    fade = np.clip(_smooth_mask(mask, 9.0), 0.0, 1.0)[y0:y1, x0:x1]
    fade = (fade * (~protect[y0:y1, x0:x1]).astype(np.float32))[..., None]
    sub = sub * (1.0 - fade) + (0.68 * toned + 0.32 * sub) * fade
    # ... and its level back to the clean skin just outside it: a field that is a shade
    # lighter than the cheeks reads as a mask even when no hair is left in it. Same fade.
    ring_w = np.clip(_smooth_mask(mask, 7.0) - _smooth_mask(mask, 4.0), 0.0, 1.0)
    ring_sel = (ring_w > 0.3) & ~mask
    if ring_sel.any():
        for c in range(3):
            ref = float(rgb[:, :, c][ring_sel].mean())
            got = float((sub[:, :, c] * fade[..., 0]).sum() / max(float(fade.sum()), 1e-6))
            if got > 1e-3 and ref > 1e-3:
                gain = float(np.clip(ref / got, 0.90, 1.10))
                sub[:, :, c] *= 1.0 + (gain - 1.0) * fade[..., 0]
    out[y0:y1, x0:x1] = sub

    # --- feather the mask's outline into the untouched raster ---
    alpha = _smooth_mask(mask, 5.0)[:, :, None]
    out = out * alpha + rgb * (1.0 - alpha)
    out[protect] = rgb[protect]
    cleaned = cell.copy()
    cleaned[:, :, :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return cleaned


def load_arivus_diffuse(path: Path = ARIVUS_DIFFUSE) -> tuple[np.ndarray, bytes]:
    """Read the supplied single-level 2048² BC3 Arivus atlas, retaining its blocks."""
    data = path.read_bytes()
    if (len(data) != 128 + 2048 * 2048 or data[:4] != b"DDS "
            or data[84:88] != b"DXT5"
            or struct.unpack_from("<II", data, 12) != (2048, 2048)
            or struct.unpack_from("<I", data, 28)[0] not in (0, 1)):
        raise ValueError(f"{path}: expected a single-level 2048x2048 DXT5 DDS")
    with Image.open(io.BytesIO(data)) as image:
        pixels = np.array(image.convert("RGBA"), dtype=np.uint8)
    # Skin must pass the material's alpha test; hair uses alpha for cutout.
    if pixels[:1024, :, 3].min() < 15:
        raise ValueError(f"{path}: skin alpha falls below the material cutout threshold")
    return pixels, data[128:]


def build_arivus_hoxton_mod(
    ada_root: Path, arivus_root: Path, suit_unit_dir: Path, out_zip_paths: list[Path]
) -> None:
    """Build the Arivus (Random4 GTA ped) head replacement over Old Hoxton.

    Old Hoxton is one of the suit heisters: his head is the `g_head_old_hoxton`
    drawable inside the shared `npc_criminals_suit_1` model (heist + menu), and
    the Safe House rides `npc_criminals_suit_chill.model`. The pack replaces that
    drawable and overrides the four `shared_textures/old_hoxton_head[_p_]df/_nm`
    textures with the supplied 2048 Arivus atlas and a flat normal map. The atlas
    matches the Random4 head (material 5) and hair (material 6) UVs; the necklace
    (material 4) and shirt (material 7) are clothing
    and stay out. Transform: source rig axes (+x up, +y fwd, +z left) map to
    Diesel world (+x right, +y fwd, +z up) around the Head-bone anchors below.
    """
    dff = rwd.read_dff((arivus_root / "Random4.dff").read_bytes())
    V, Nrm, UV = dff.positions, dff.normals, dff.uvs

    def _rot(pts: np.ndarray) -> np.ndarray:
        return np.column_stack([-pts[:, 2], pts[:, 1], pts[:, 0]])

    a_rot = _rot(np.asarray([ARIVUS_SRC_ANCHOR], dtype=np.float64))[0]
    dst_anchor = np.asarray(ARIVUS_DST_ANCHOR, dtype=np.float64)

    def extract_arivus_part(
        mat_index: int, u_off: float, u_scale: float, v_off: float, v_scale: float
    ) -> dict:
        vidx = np.concatenate([v for m, v in dff.groups if m == mat_index]).reshape(-1, 3)
        idx = vidx.ravel()
        p_raw = V[idx].astype(np.float64)
        n_raw = Nrm[idx].astype(np.float64)
        uv_raw = UV[idx].reshape(-1, 3, 2).astype(np.float64)
        # Shift all 3 vertices of each triangle by the same integer UV tile offset
        u_tile = np.floor(uv_raw[:, :, 0].mean(axis=1, keepdims=True))
        v_tile = np.floor(uv_raw[:, :, 1].mean(axis=1, keepdims=True))
        u_img = np.clip(uv_raw[:, :, 0] - u_tile, 0.002, 0.998).ravel()
        # Random4's UVs put v = 0 at the texture top (DirectX order): the
        # fractional v already counts image rows downwards. Flipping it here puts
        # the beard on the forehead and the eye quads on the chin.
        v_img = np.clip(uv_raw[:, :, 1] - v_tile, 0.002, 0.998).ravel()
        p = (_rot(p_raw) - a_rot) * ARIVUS_SCALE + dst_anchor
        # The ped is left where it lands. D72 used to drag the whole neck cone down
        # (up to 4.3 cm at the throat) and push it back up near z 168, which squashed
        # the neck to half its height and still left its open rim in the collar
        # opening as a jagged skin line (D79). The rim is closed by a skirt instead,
        # below, where it can be measured.
        n = _rot(n_raw)
        u_atlas = u_off + u_scale * u_img
        v_img_atlas = v_off + v_scale * v_img
        uv_diesel = np.column_stack([u_atlas, 1.0 - v_img_atlas]).astype(np.float32)
        t = np.arange(len(p), dtype=np.int32).reshape(-1, 3)
        return {
            "verts": p.astype(np.float32),
            "normals": n.astype(np.float32),
            "uvs": uv_diesel,
            "tris": t,
        }

    # The supplied edit already uses this mesh's atlas layout: skin/eyes at
    # top left, cutout hair at bottom left. Its BC3 base level is preserved
    # exactly; mip levels are generated below for the game's texture sampler.
    head_df_atlas, head_df_base = load_arivus_diffuse()

    # No source normal map exists for this ped; a flat PD2 normal is honest
    # (R = 255, G = 128, B = 0, A = 128, as in the other head packs' channels).
    head_nm_atlas = np.zeros((2048, 2048, 4), dtype=np.uint8)
    head_nm_atlas[:, :] = [255, 128, 0, 128]

    def suit_bytes(name: str) -> bytes:
        p = _find_named(suit_unit_dir, name)
        if p is None:
            raise FileNotFoundError(f"{name} missing from the npc_criminals_suit_1 reference")
        return p.read_bytes()

    atom0_mesh = extract_arivus_part(5, 0.0, 0.5, 0.0, 0.5)  # head: top-left cell
    atom1_mesh = extract_arivus_part(6, 0.0, 0.5, 0.5, 0.5)  # hair: bottom-left cell
    # Close the neck (D79): drop the ped's V-shaped cut to the collar's height, then
    # stitch a skirt from the rim down to z 148 tucked inside the suit. The extract
    # is triangle soup (one vertex per corner), so the rim only exists as an *open
    # edge* after welding: dedup first, then close it.
    welded = deduplicate_mesh(atom0_mesh["verts"], atom0_mesh["normals"],
                              atom0_mesh["uvs"], atom0_mesh["tris"])
    neck_skirt = extend_neck_into_collar(*welded)
    atom0_mesh = {"verts": neck_skirt[0], "normals": neck_skirt[1],
                  "uvs": neck_skirt[2], "tris": neck_skirt[3]}
    packed_head = _prepare_combined_head_arrays(
        atom0_mesh,
        atom1_mesh,
        bone_offset=0,  # the head's palette starts at Spine2: SkinBones lists exactly it
        jaw_lift=7.5,
        single_atom=True,
        double_side_atom1=True,
    )

    portrait = render_head_portrait(
        atom0_mesh, atom1_mesh, head_df_atlas[:, :, :3], head_df_atlas, alpha_cut=True
    )
    icon_dds = make_character_icon_dds(ada_root / JOY_ICON_PATH, portrait)
    head_df_dds = encode_cutout_head_df_dds(head_df_atlas, base_payload=head_df_base)
    head_nm_dds = encode_rgba_dds(head_nm_atlas)

    def patch_suit_model(model_bytes: bytes) -> bytes:
        return patch_female_heister_model(
            model_bytes,
            head_drawables=["g_head_old_hoxton"],
            collapse_drawables=[],
            head_mat_name="mtr_head",
            hair_mat_name=None,
            packed_head=packed_head,
        )

    suit_model = patch_suit_model(suit_bytes(f"{SUIT_UNIT_STEM}.model"))
    suit_menu_model = patch_suit_model(suit_bytes(f"{SUIT_MENU_STEM}.model"))

    fps_zip = ROOT / "references" / "templates" / "Heister - FPS Gloves in TPS 2.zip"
    with zipfile.ZipFile(fps_zip) as zf:
        chill_model = patch_suit_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/npc_criminals_suit_chill.model")
        )
        chill_mtr = patch_old_hoxton_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/mtr_old_hoxton.material_config")
        )

    prefix = "Arivus over Hoxton"
    files: dict[str, bytes] = {
        f"{prefix}/{OLD_HOXTON_ICON_PATH}": icon_dds,
        f"{prefix}/{SUIT_UNIT_DIR}/{SUIT_UNIT_STEM}.model": suit_model,
        f"{prefix}/{SUIT_UNIT_DIR}/{SUIT_MENU_STEM}.model": suit_menu_model,
        f"{prefix}/{CHILL_UNIT_DIR}/npc_criminals_suit_chill.model": chill_model,
        f"{prefix}/{CHILL_UNIT_DIR}/mtr_old_hoxton.material_config": chill_mtr,
    }
    for cfg in sorted(suit_unit_dir.rglob("mtr_old_hoxton*.material_config")):
        files[f"{prefix}/{SUIT_UNIT_DIR}/{cfg.name}"] = patch_old_hoxton_material_config(cfg.read_bytes())
    for obj_name in (f"{SUIT_UNIT_STEM}.object", f"{SUIT_MENU_STEM}.object"):
        obj = _find_named(suit_unit_dir, obj_name)
        if obj is not None:
            files[f"{prefix}/{SUIT_UNIT_DIR}/{obj_name}"] = obj.read_bytes()
    for stem in ("old_hoxton_head_p_df", "old_hoxton_head_p_nm", "old_hoxton_head_df", "old_hoxton_head_nm"):
        payload = head_df_dds if stem.endswith("_df") else head_nm_dds
        files[f"{prefix}/{OLD_HOXTON_TEX_DIR}/{stem}.texture"] = payload
    write_deterministic_zip(files, out_zip_paths)


def main() -> None:
    determinism.enter(__file__)
    ada_root = ensure_ada_reference(EXTRACT_DIR / "ada_joy")
    me2_dir = ensure_me2_extracted(EXTRACT_DIR / "me2_extract")
    geralt_root = ensure_geralt_extracted(EXTRACT_DIR / "geralt_extract")
    flat_nm = np.zeros((512, 512, 4), dtype=np.uint8)
    flat_nm[:, :] = [255, 128, 0, 128]
    sec_nm_dds = encode_rgba_dds(flat_nm)

    # The head assemblies: each emits its over Hila pack and nothing else (the over Joy
    # zips they used to write are retired, with the code that wrote them).
    build_l4d2_hila_head(ada_root, me2_dir, sec_nm_dds=sec_nm_dds)
    build_geralt_rust_mod(
        ada_root,
        geralt_root,
        [dist_path(ROOT, "Geralt_over_Rust.zip")],
    )
    arivus_root = ensure_arivus_extracted(EXTRACT_DIR / "arivus_extract")
    try:
        suit_unit_dir = ensure_suit_reference(EXTRACT_DIR / "suit_extract")
    except FileNotFoundError as exc:
        # The shared suit model is game content; the pack builds once the user
        # extracts units/payday2/characters/npc_criminals_suit_1/ (see
        # ensure_suit_reference). Everything else keeps building meanwhile.
        print(f"SKIP Arivus_over_Hoxton: {exc}", file=sys.stderr)
    else:
        build_arivus_hoxton_mod(
            ada_root,
            arivus_root,
            suit_unit_dir,
            [dist_path(ROOT, "Arivus_over_Hoxton.zip")],
        )


if __name__ == "__main__":
    main()
