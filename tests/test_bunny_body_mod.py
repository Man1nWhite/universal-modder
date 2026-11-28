"""Verification of `dist/Miranda/OfficeSuite_over_Bunny.zip` (D85).

Checks the native `mod_overrides` Hop to It (`player_styles.bunny`, `ccmt_acc_bunny`)
replacement pack offline without needing the 2B templates unpacked:
- checksum sidecar, pack registration, and archive layout (no `.unit` overrides);
- every `.material_config` texture reference resolves inside the zip, and `bunny.texture`
  matches `OfficeSuite`'s 256x256 BC3 icon byte for byte;
- all five third-person `.model` variants and `ccmt_acc_fps_bunny_male.model` decode in both
  `diesel_model` and `dmodel`, with `IBM @ World == I` on every weighted joint and `g_arms`
  inside `co_box`;
- 0-texel-diff parity between `OfficeSuite`'s six diffuse tiles and the 4096x2048 BC3 atlas,
  plus exact `Hips`-local vertex parity on both TPP and FPS rigs;
- D70 palm cut dominance invariant and warning-free skinned `.glb` export.
"""
from __future__ import annotations

import hashlib
import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))

import diesel_model as dm  # noqa: E402
import dmodel  # noqa: E402
import hila_texture_atlas as hta  # noqa: E402
import model_to_glb as mtg  # noqa: E402
from build_bunny_body_mod import COMPANION, FPS_UNIT, ICON_PATH, MOD_PREFIX, TPP_UNITS, UNIT_ROOT  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from pack_checksum import verify_checksum  # noqa: E402
from status import target as make_target  # noqa: E402

PACK = dist_path(ROOT, "OfficeSuite_over_Bunny.zip")
SOURCE = dist_path(ROOT, "OfficeSuite.zip")
PREFIX = f"{MOD_PREFIX}/"

HAND_AND_FINGER_HASHES = {
    dm.hash64(f"{side}{part}")
    for side in ("Left", "Right")
    for part in (
        "Hand",
        "HandThumb1", "HandThumb2", "HandThumb3",
        "HandIndex1", "HandIndex2", "HandIndex3",
        "HandMiddle1", "HandMiddle2", "HandMiddle3",
        "HandRing1", "HandRing2", "HandRing3",
        "HandPinky1", "HandPinky2", "HandPinky3",
    )
}


def _worlds(mf: dm.ModelFile) -> tuple[dict[int, dict], dict[int, np.ndarray]]:
    objs = {
        s.id: dm.decode_object3d(s.payload)
        for s in mf.sections
        if s.type in (dm.OBJECT3D, dm.MODEL_DATA)
    }
    out: dict[int, np.ndarray] = {}

    def get(sid: int) -> np.ndarray:
        if sid not in out:
            loc = np.asarray(objs[sid]["matrix"], dtype=np.float64).reshape(4, 4)
            pid = objs[sid]["parent"]
            out[sid] = loc @ get(pid) if pid in objs and pid != sid else loc
        return out[sid]

    for sid in objs:
        get(sid)
    return objs, out


def test_pack_is_paired_and_registered():
    assert PACK.is_file() and SOURCE.is_file()
    assert verify_checksum(PACK, ROOT) == hashlib.sha256(PACK.read_bytes()).hexdigest()
    assert make_target(PACK.stem) == "bunny"
    assert (ROOT / "tools/pd2-las/build_bunny_body_mod.py").is_file()
    assert "\nbunny:" in (ROOT / "tools/pd2-las/Makefile").read_text()


def test_members_cover_all_five_body_types_fps_materials_textures_and_icon():
    expected = sorted([
        f"{PREFIX}README.txt",
        f"{PREFIX}{COMPANION}/mod.txt",
        f"{PREFIX}{COMPANION}/forearm_fix.lua",
        f"{PREFIX}{ICON_PATH}",
        f"{PREFIX}{UNIT_ROOT}/shared_materials/ccmt_acc_bunny.material_config",
        f"{PREFIX}{UNIT_ROOT}/shared_materials/ccmt_acc_bunny_fps.material_config",
        f"{PREFIX}{UNIT_ROOT}/acc_bunny_df.texture",
        f"{PREFIX}{UNIT_ROOT}/acc_bunny_nm.texture",
        f"{PREFIX}{UNIT_ROOT}/acc_bunny_fps_df.texture",
        f"{PREFIX}{UNIT_ROOT}/acc_bunny_fps_nm.texture",
        *(f"{PREFIX}{UNIT_ROOT}/{u}/{u}.model" for u in (*TPP_UNITS, FPS_UNIT)),
        *(f"{PREFIX}{UNIT_ROOT}/{u}/{u}.object" for u in (*TPP_UNITS, FPS_UNIT)),
    ])
    with zipfile.ZipFile(PACK) as zf, zipfile.ZipFile(SOURCE) as src:
        names = zf.namelist()
        assert names == expected
        assert not any(n.endswith(".unit") for n in names)

        for cfg_rel in (
            f"{PREFIX}{UNIT_ROOT}/shared_materials/ccmt_acc_bunny.material_config",
            f"{PREFIX}{UNIT_ROOT}/shared_materials/ccmt_acc_bunny_fps.material_config",
        ):
            root = ET.fromstring(zf.read(cfg_rel))
            for tag in ("diffuse_texture", "bump_normal_texture"):
                for elem in root.iter(tag):
                    tex_rel = f"{PREFIX}{elem.attrib['file']}.texture"
                    assert tex_rel in names, f"missing texture referenced by {cfg_rel}: {tex_rel}"

        icon_bytes = zf.read(f"{PREFIX}{ICON_PATH}")
        src_icon = src.read("OfficeSuite/assets/guis/dlcs/officesuite/armor_skins/officesuite.texture")
        assert icon_bytes == src_icon
        im = Image.open(io.BytesIO(icon_bytes))
        assert im.size == (256, 256)


def test_all_models_parse_in_both_parsers_with_valid_skinbones_and_bounds():
    co_box_hash = dm.hash64("co_box")
    g_arms_hash = dm.hash64("g_arms")
    with zipfile.ZipFile(PACK) as zf:
        for stem in (*TPP_UNITS, FPS_UNIT):
            raw = zf.read(f"{PREFIX}{UNIT_ROOT}/{stem}/{stem}.model")
            mf = dm.ModelFile.read(raw)
            parsed = dmodel.DieselModel.from_bytes(raw)
            assert len(parsed.sections) == len(mf.sections)
            assert mf.write() == raw

            objs, worlds = _worlds(mf)
            for sb_sec in mf.by_type(dm.SKINBONES):
                sb = dm.decode_skinbones(sb_sec.payload)
                for bid, rot in zip(sb["objects"], sb["rotations"]):
                    ibm = np.asarray(rot, dtype=np.float64).reshape(4, 4)
                    prod = ibm @ worlds[bid]
                    assert np.max(np.abs(prod - np.eye(4))) < 2e-5, f"{stem} bone {bid}"

            for md_sec in mf.by_type(dm.MODEL_DATA):
                md = dm.decode_model_data(md_sec.payload)
                if md["version"] == 6:
                    continue
                pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
                topo = dm.decode_topology(mf.by_id(pg["topology"]).payload)
                assert len(md["atoms"]) == 1
                a = md["atoms"][0]
                assert a["base_vertex"] == 0 and a["slice_len"] == geo["vert_count"]
                assert min(topo["indices"]) >= 0 and max(topo["indices"]) < geo["vert_count"]

                # Dominant weight must never sit on Hand or finger joints (D70 palm cut).
                if md["skinbones"] and "uv0" in geo and "blendindices" in geo:
                    sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
                    pal = sb["maps"][0]
                    for bi, bw in zip(geo["blendindices"], geo["blendweights"]):
                        w4 = (*bw, max(0.0, 1.0 - sum(bw)))
                        dom_slot = bi[int(np.argmax(w4))]
                        dom_hash = objs[sb["objects"][pal[dom_slot]]]["name_hash"]
                        assert dom_hash not in HAND_AND_FINGER_HASHES

            if stem == FPS_UNIT:
                md_map = {
                    dm.decode_model_data(s.payload)["name_hash"]: dm.decode_model_data(s.payload)
                    for s in mf.by_type(dm.MODEL_DATA)
                    if dm.decode_model_data(s.payload)["version"] != 6
                }
                md_arms_id = next(
                    s.id for s in mf.by_type(dm.MODEL_DATA)
                    if dm.decode_model_data(s.payload)["version"] != 6
                    and dm.decode_model_data(s.payload)["name_hash"] == g_arms_hash
                )
                md_cobox_id = next(
                    s.id for s in mf.by_type(dm.MODEL_DATA)
                    if dm.decode_model_data(s.payload)["version"] != 6
                    and dm.decode_model_data(s.payload)["name_hash"] == co_box_hash
                )
                arms_geo = dm.decode_geometry(
                    mf.by_id(dm.decode_passthroughgp(mf.by_id(md_map[g_arms_hash]["passthroughgp"]).payload)["geometry"]).payload
                )
                cobox_geo = dm.decode_geometry(
                    mf.by_id(dm.decode_passthroughgp(mf.by_id(md_map[co_box_hash]["passthroughgp"]).payload)["geometry"]).payload
                )
                arms_v = np.column_stack([np.asarray(arms_geo["verts"]), np.ones(arms_geo["vert_count"])]) @ worlds[md_arms_id]
                box_v = np.column_stack([np.asarray(cobox_geo["verts"]), np.ones(cobox_geo["vert_count"])]) @ worlds[md_cobox_id]
                assert np.all(arms_v[:, :3].min(axis=0) >= box_v[:, :3].min(axis=0))
                assert np.all(arms_v[:, :3].max(axis=0) <= box_v[:, :3].max(axis=0))


def test_atlas_preserves_texel_identity_and_bone_local_geometry():
    hips_hash = dm.hash64("Hips")
    g_body_hash = dm.hash64("g_body")
    g_arms_hash = dm.hash64("g_arms")
    slot_by_hash = {dm.hash64(f"officesuite_{s}"): s for s in hta.TILES}

    with zipfile.ZipFile(PACK) as zf, zipfile.ZipFile(SOURCE) as src:
        atlas_im = np.asarray(
            Image.open(io.BytesIO(zf.read(f"{PREFIX}{UNIT_ROOT}/acc_bunny_df.texture"))).convert("RGBA")
        )
        tile_ims = {
            s: np.asarray(
                Image.open(
                    io.BytesIO(
                        src.read(f"OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite_{s}_df.texture")
                    )
                ).convert("RGBA")
            )
            for s in hta.TILES
        }

        mf_src = dm.ModelFile.read(src.read("OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite.model"))
        mf_dst = dm.ModelFile.read(
            zf.read(f"{PREFIX}{UNIT_ROOT}/ccmt_acc_bunny_female_average/ccmt_acc_bunny_female_average.model")
        )
        src_objs, src_worlds = _worlds(mf_src)
        dst_objs, dst_worlds = _worlds(mf_dst)

        src_md = next(
            dm.decode_model_data(s.payload) for s in mf_src.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == g_body_hash
        )
        dst_md = next(
            dm.decode_model_data(s.payload) for s in mf_dst.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == g_body_hash
        )
        src_geo = dm.decode_geometry(
            mf_src.by_id(dm.decode_passthroughgp(mf_src.by_id(src_md["passthroughgp"]).payload)["geometry"]).payload
        )
        dst_geo = dm.decode_geometry(
            mf_dst.by_id(dm.decode_passthroughgp(mf_dst.by_id(dst_md["passthroughgp"]).payload)["geometry"]).payload
        )
        src_mats = {s.id: dm.decode_material(s.payload)["name_hash"] for s in mf_src.by_type(dm.MATERIAL)}
        src_mg = dm.decode_material_group(mf_src.by_id(src_md["matgroup"]).payload)

        src_uv = np.asarray(src_geo["uv0"], dtype=np.float64)
        dst_uv = np.asarray(dst_geo["uv0"], dtype=np.float64)
        src_faces = np.asarray(
            dm.decode_topology(
                mf_src.by_id(dm.decode_passthroughgp(mf_src.by_id(src_md["passthroughgp"]).payload)["topology"]).payload
            )["indices"],
            dtype=np.int64,
        ).reshape(-1, 3)
        ah, aw = atlas_im.shape[:2]

        for atom in src_md["atoms"]:
            slot = slot_by_hash[src_mats[src_mg["material_ids"][atom["material_id"]]]]
            tile = tile_ims[slot]
            th, tw = tile.shape[:2]
            rx, ry, rside = hta.TILES[slot]
            expected_rect = np.repeat(np.repeat(tile, rside // th, axis=0), rside // tw, axis=1)
            assert np.array_equal(atlas_im[ry:ry + rside, rx:rx + rside], expected_rect), slot

            bi, tc = atom["base_index"] // 3, atom["tri_count"]
            tri_idx = src_faces[bi:bi + tc]
            c_src = (src_uv[tri_idx].mean(axis=1) * (1.0, -1.0)) % 1.0
            c_dst = (dst_uv[tri_idx].mean(axis=1) * (1.0, -1.0)) % 1.0
            mapped_px = c_dst * (aw, ah)
            expected_px = c_src * rside + (rx, ry)
            assert np.max(np.abs(mapped_px - expected_px)) < 1e-3, slot

        # Hips-local vertex parity on both TPP and FPS units.
        src_hips = next(src_worlds[i][3, :3] for i, o in src_objs.items() if o["name_hash"] == hips_hash)
        dst_hips = next(dst_worlds[i][3, :3] for i, o in dst_objs.items() if o["name_hash"] == hips_hash)
        assert np.max(np.abs((np.asarray(src_geo["verts"]) - src_hips) - (np.asarray(dst_geo["verts"]) - dst_hips))) < 1e-4

        mf_src_fps = dm.ModelFile.read(src.read("OfficeSuite/assets/units/officesuite/skins/officesuite/fps_officesuite.model"))
        mf_dst_fps = dm.ModelFile.read(zf.read(f"{PREFIX}{UNIT_ROOT}/{FPS_UNIT}/{FPS_UNIT}.model"))
        sf_objs, sf_worlds = _worlds(mf_src_fps)
        df_objs, df_worlds = _worlds(mf_dst_fps)
        sf_md = next(
            dm.decode_model_data(s.payload) for s in mf_src_fps.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == g_body_hash
        )
        df_md = next(
            dm.decode_model_data(s.payload) for s in mf_dst_fps.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == g_arms_hash
        )
        sf_geo = dm.decode_geometry(
            mf_src_fps.by_id(dm.decode_passthroughgp(mf_src_fps.by_id(sf_md["passthroughgp"]).payload)["geometry"]).payload
        )
        df_geo = dm.decode_geometry(
            mf_dst_fps.by_id(dm.decode_passthroughgp(mf_dst_fps.by_id(df_md["passthroughgp"]).payload)["geometry"]).payload
        )
        sf_hips = next(sf_worlds[i][3, :3] for i, o in sf_objs.items() if o["name_hash"] == hips_hash)
        df_hips = next(df_worlds[i][3, :3] for i, o in df_objs.items() if o["name_hash"] == hips_hash)
        assert np.max(np.abs((np.asarray(sf_geo["verts"]) - sf_hips) - (np.asarray(df_geo["verts"]) - df_hips))) < 1e-4


def test_glb_skin_export_reports_no_missing_textures_or_warnings(tmp_path: Path):
    src = mtg.Source(PACK)
    cfg = mtg.read_material_configs(src)
    for model_name in ("ccmt_acc_bunny_female_average.model", f"{FPS_UNIT}.model"):
        rel = next(iter(mtg.models_in(src, model_name)))
        unit = mtg.read_unit(src, rel, cfg)
        rep = mtg.export_glb(src, unit, cfg, tmp_path / f"{model_name}.glb", skin=True)
        assert rep["missing"] == []
        assert rep["warnings"] == []


def test_tangents_sbody_headers_and_bc3_mip_chain_invariants():
    import struct

    with zipfile.ZipFile(PACK) as zf, zipfile.ZipFile(SOURCE) as src:
        mf_src = dm.ModelFile.read(src.read("OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite.model"))
        mf_dst = dm.ModelFile.read(
            zf.read(f"{PREFIX}{UNIT_ROOT}/ccmt_acc_bunny_female_average/ccmt_acc_bunny_female_average.model")
        )
        g_body_md_src = next(
            dm.decode_model_data(s.payload) for s in mf_src.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("g_body")
        )
        g_body_md_dst = next(
            dm.decode_model_data(s.payload) for s in mf_dst.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("g_body")
        )
        s_body_md_dst = next(
            dm.decode_model_data(s.payload) for s in mf_dst.by_type(dm.MODEL_DATA)
            if dm.decode_model_data(s.payload)["version"] != 6
            and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("s_body")
        )
        src_geo = dm.decode_geometry(
            mf_src.by_id(dm.decode_passthroughgp(mf_src.by_id(g_body_md_src["passthroughgp"]).payload)["geometry"]).payload
        )
        dst_geo = dm.decode_geometry(
            mf_dst.by_id(dm.decode_passthroughgp(mf_dst.by_id(g_body_md_dst["passthroughgp"]).payload)["geometry"]).payload
        )
        s_geo = dm.decode_geometry(
            mf_dst.by_id(dm.decode_passthroughgp(mf_dst.by_id(s_body_md_dst["passthroughgp"]).payload)["geometry"]).payload
        )

        # Stored tangent vectors must survive atlas UV affine remap unflipped.
        for key in ("normals", "uvdir_u", "uvdir_v"):
            a = np.asarray(src_geo[key], dtype=np.float64)
            b = np.asarray(dst_geo[key], dtype=np.float64)
            cos = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
            assert float(cos.min()) > 0.9999, (key, float(cos.min()))

        # Shadow caster geometry keeps vanilla legacy header stream layout (pos, blendindices, blendweights).
        assert [(h["enum_type"], h["disk_type"]) for h in s_geo["headers"]] == [(1, 1), (17, 15), (19, 17)]
        assert s_geo["normals"] == [] and s_geo["uv0"] == []

        # Full BC3 mip chain (13 mips for 4096x2048) has matte diffuse alpha and DXT5nm (R=255, B=0) normal encoding.
        for tex_name, is_nm in (("acc_bunny_df.texture", False), ("acc_bunny_nm.texture", True)):
            raw = zf.read(f"{PREFIX}{UNIT_ROOT}/{tex_name}")
            h, w = struct.unpack_from("<II", raw, 12)
            mips = struct.unpack_from("<I", raw, 28)[0]
            assert (w, h, mips) == (4096, 2048, 13)
            hdr_1 = bytearray(raw[:128])
            struct.pack_into("<I", hdr_1, 28, 1)
            off = 128
            for level in range(mips):
                mw, mh = max(1, w >> level), max(1, h >> level)
                size = max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * 16
                struct.pack_into("<II", hdr_1, 12, mh, mw)
                struct.pack_into("<I", hdr_1, 20, size)
                arr = np.asarray(Image.open(io.BytesIO(bytes(hdr_1) + raw[off:off + size])).convert("RGBA"))
                off += size
                if is_nm:
                    assert int(arr[..., 0].min()) == 255 and int(arr[..., 2].max()) == 0
                else:
                    assert int(arr[..., 3].max()) <= 24
            assert off == len(raw)
