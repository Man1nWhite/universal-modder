"""Checks on the installable ZIP, not just an overlay of the two donor models."""
from __future__ import annotations

from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_hila_body_mod as hila  # noqa: E402
import build_models as bm  # noqa: E402
import dds_encode as dds  # noqa: E402
import diesel_model as dm  # noqa: E402
import fresh  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from hila_texture_atlas import BLOCK_LEVELS, GUTTER, HEIGHT, TILES, WIDTH, atlas_uvs  # noqa: E402

PACK = dist_path(ROOT, "OfficeSuite_Miranda_Romance_over_Hila.zip")
BODY = dist_path(ROOT, "OfficeSuite.zip")
HEAD = dist_path(ROOT, "Miranda_Romance_over_Hila.zip")
DONOR_UNIT = f"OfficeSuite/assets/{hila.OUTFIT_DIR}/officesuite"


def _read(path, prefix):
    with ZipFile(path) as z:
        names = z.namelist()
        assert len(names) == len(set(names)) and all(n.startswith(prefix) for n in names)
        return {n.removeprefix(prefix): z.read(n) for n in names}


@pytest.fixture(scope="module")
def files():
    return _read(PACK, hila.INSTALL + "/"), _read(HEAD, hila.HEAD_ROOT)


@pytest.fixture(scope="module")
def models(files):
    pack, head = files
    with ZipFile(BODY) as z:
        source = z.read(DONOR_UNIT + ".model")
    return tuple(dm.ModelFile.read(b) for b in (pack[hila.UNIT + ".model"], head[hila.UNIT + ".model"], source))


def test_native_install_paths_and_material_contract(files):
    new, old = files
    atlas_paths = {p + ".texture" for p in hila.ATLAS_ASSETS.values()}
    # All assets are on known Hila paths. No new unit, LAS/BeardLib manifest,
    # FPS overrides or loose donor assets are needed to install the pack.
    assert new.keys() - old.keys() == atlas_paths | {"README.txt"}
    assert not any(k.endswith((".lua", ".unit")) or k.startswith("assets/") for k in new)
    changed = {k for k in old if new[k] != old[k]}
    assert changed == {hila.UNIT + s + ".model" for s in ("", "_menu")} | {
        hila.MATERIAL + s + ".material_config" for s in ("", "_cc")}
    for suffix in ("", "_menu"):
        obj = ET.fromstring(new[hila.UNIT + suffix + ".object"])
        assert obj.find("diesel").get("materials") == hila.MATERIAL
        enabled = {elem.get("name"): elem for elem in obj.findall(".//graphics//object") if elem.get("enabled") == "true"}
        assert set(enabled) == {"g_body", "g_head", "g_hands", "s_body"}
        assert enabled["s_body"].get("shadow_caster") == "true"
    for suffix in ("", "_cc"):
        name = hila.MATERIAL + suffix + ".material_config"
        mats = ET.fromstring(new[name])
        before = ET.fromstring(old[name])
        assert mats.attrib == before.attrib
        assert [m.get("name") for m in mats] == [m.get("name") for m in before]
        for m, ref in zip(mats, before):
            if m.get("name") == "mtr_suite_body":
                assert m.get("render_template") == hila.SUIT_SHADER
                assert m.find("material_texture") is None
                assert {m.find(el).get("file") + ".texture" for el in hila.ATLAS_ASSETS} == atlas_paths
                assert all(m.find(el).attrib == ref.find(el).attrib for el in hila.ATLAS_ASSETS)
            else:
                assert ET.tostring(m) == ET.tostring(ref)
    assert new[hila.UNIT + ".model"] == new[hila.UNIT + "_menu.model"]


def _draws(m):
    return {name: hila.Drawable.read(m, name) for name in ("g_body", "s_body", "g_head", "g_hands")}


def test_only_the_two_mesh_blocks_change(models):
    output, native, donor = models
    assert [(s.id, s.type) for s in output.sections] == [(s.id, s.type) for s in native.sections]
    assert len({s.id for s in output.sections}) == len(output.sections)
    changed = {s.id for s in output.sections if s.payload != native.by_id(s.id).payload}
    new, old = _draws(output), _draws(native)
    assert changed == {s.id for name in ("g_body", "s_body") for s in
                       (new[name].section, new[name].geometry, new[name].topology, new[name].skin)}
    authored = hila.Drawable.read(donor, "g_body")
    assert new["g_body"].geo["vert_count"] == authored.geo["vert_count"]
    assert new["g_body"].top["indices"] == authored.top["indices"]
    # The caster includes the trimmed donor body, head without lashes, and Hila's gloves.
    shadow_tris = len(hila.Drawable.read(donor, "s_body").faces)
    assert len(new["s_body"].faces) == shadow_tris + old["g_head"].data["atoms"][0]["tri_count"] + len(old["g_hands"].faces)
    for name, part in new.items():
        assert not bm.atom_problems(part.geo, part.top, part.data["atoms"])
        assert part.geo["headers"] == old[name].geo["headers"]
        assert part.top["primitive"] == old[name].top["primitive"]
        assert part.material_hashes(output) == old[name].material_hashes(native)
        for key in ("name_hash", "parent", "matrix", "pos", "skinbones", "matgroup", "passthroughgp", "topologyip"):
            assert part.data[key] == old[name].data[key]
        v = np.asarray(part.geo["verts"])
        assert np.isfinite(v).all()
        np.testing.assert_allclose(v.min(0), part.data["bounds_min"], atol=1e-5)
        np.testing.assert_allclose(v.max(0), part.data["bounds_max"], atol=1e-5)


def test_body_weights_bind_to_the_native_rig_and_shadow_is_one_weight(models):
    output, _, _ = models
    _, worlds = bm._resolve_worlds(output)
    for name in ("g_body", "s_body"):
        draw = hila.Drawable.read(output, name)
        palette = draw.bind["objects"]
        assert draw.bind["maps"] == [list(range(len(palette)))] * (len(draw.data["atoms"]) + 1)
        root = dm.decode_object3d(output.by_id(draw.bind["root"]).payload)
        assert root["name_hash"] == dm.hash64("root_point")
        for sid, inv in zip(palette, draw.bind["rotations"]):
            np.testing.assert_allclose(dm.mat_mul(inv, worlds[sid]), dm.IDENTITY, atol=2e-4)
        indices = np.asarray(draw.geo["blendindices"])
        assert indices.min() >= 0 and indices.max() < len(palette)
        weights = np.asarray(draw.geo["blendweights"])
        assert (weights >= 0).all() and (weights <= 1).all()
        np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-6)
        if name == "s_body":
            assert (weights == [1., 0., 0.]).all()


@pytest.mark.parametrize("side", ["Left", "Right"])
def test_skin_rim_reaches_inside_the_stock_glove_and_follows_that_hand(models, side):
    output, _, donor = models
    body = hila.Drawable.read(output, "g_body")
    hands = hila.Drawable.read(output, "g_hands")
    orig = hila.Drawable.read(donor, "g_body")
    objs, worlds = bm._resolve_worlds(output)
    names = {obj["name_hash"]: sid for sid, obj in objs.items()}
    donor_skin = next(a for a in orig.data["atoms"] if orig.material_hashes(donor)[a["material_id"]] == dm.hash64("officesuite_body"))
    cuff = hila._measure_cuff(orig, donor_skin, hands, side, names, worlds)
    wrist = worlds[cuff.hand][12:15]
    raw_rim = hila._rim(orig, np.array(wrist), cuff.axis, -3.4, -1.9, hila._atom_faces(orig, donor_skin))
    tip = {tuple(p) for p in np.round(raw_rim, 4)}
    rows = [i for i, p in enumerate(np.round(orig.geo["verts"], 4)) if tuple(p) in tip]
    # Before fitting, the ring is ~2.5 cm behind the wrist; the glove lip is ~1.6 cm ahead.
    assert len(rows) >= len(tip)
    assert np.max((np.asarray(orig.geo["verts"])[rows] - wrist) @ cuff.axis) < -2
    axial = (np.asarray(body.geo["verts"])[rows] - wrist) @ cuff.axis
    assert np.min(axial) > 2.5 and np.max(axial) < 3.5
    b = np.asarray(body.geo["blendindices"])[rows, 0]
    assert (np.asarray(body.bind["objects"])[b] == cuff.hand).all()
    np.testing.assert_allclose(np.asarray(body.geo["blendweights"])[rows, 0], 1, atol=1e-6)


@pytest.mark.parametrize("channel,suffix", [("diffuse_texture", "df"), ("bump_normal_texture", "nm")])
def test_atlas_preserves_each_original_texture_and_mips_at_compatible_levels(files, channel, suffix):
    pack, _ = files
    atlas = pack[hila.ATLAS_ASSETS[channel] + ".texture"]
    levels = dds.bc3_levels(atlas)
    assert len(levels) == WIDTH.bit_length()
    assert levels[0][1:] == (WIDTH, HEIGHT) and levels[-1][1:] == (1, 1)
    with ZipFile(BODY) as z:
        tex = [dds.decode_bc3_level(atlas, level) for level in range(BLOCK_LEVELS)]
        for slot, (x, y, side) in TILES.items():
            source = z.read(f"{DONOR_UNIT}_{slot}_{suffix}.texture")
            shift = side.bit_length() - dds.bc3_levels(source)[0][1].bit_length()
            for level, image in enumerate(tex):
                src = dds.decode_bc3_level(source, max(0, level - shift))
                scale = 1 << max(0, shift - level)
                src = src.repeat(scale, axis=0).repeat(scale, axis=1)
                bx, by, span = x >> level, y >> level, side >> level
                pad = GUTTER >> level
                crop = image[by-pad:by+span+pad, bx-pad:bx+span+pad]
                np.testing.assert_array_equal(crop, np.pad(src, ((pad, pad), (pad, pad), (0, 0)), mode="wrap"),
                                              err_msg=f"{slot}_{suffix} mip {level}")


def test_atom_uvs_sample_the_same_texels_on_the_new_atlas(models):
    output, _, donor = models
    body = hila.Drawable.read(output, "g_body")
    orig = hila.Drawable.read(donor, "g_body")
    mats = orig.material_hashes(donor)
    slots_by_hash = {dm.hash64(f"officesuite_{slot}"): slot for slot in TILES}
    new_uv = np.asarray(body.geo["uv0"]) * (WIDTH, -HEIGHT)
    old_uv = (np.asarray(orig.geo["uv0"]) * (1, -1)) % 1
    for old_atom, new_atom in zip(orig.data["atoms"], body.data["atoms"], strict=True):
        x, y, side = TILES[slots_by_hash[mats[old_atom["material_id"]]]]
        assert new_atom == {**old_atom, "material_id": 0}
        used = np.unique(hila._atom_faces(body, new_atom))
        np.testing.assert_allclose((new_uv[used] - (x, y)) / side, old_uv[used], atol=5e-7)
    with pytest.raises(ValueError, match="crosses a texture repeat"):
        atlas_uvs(np.array([[0.1, 0.98], [0.2, 1.01], [0.1, 0.93]]), np.array([[0, 1, 2]]), "body")


def test_fresh_build_knows_its_donors_are_inputs_and_can_rebuild_them_first():
    zips = fresh.tracked_zips()
    expected = [PACK.relative_to(ROOT).as_posix()]
    assert fresh.build_plan("hila", zips) == {"hila": expected}
    all_builds = fresh.build_plan("", zips)
    assert all_builds["hila"] == expected
    assert list(all_builds).index("hila") > max(list(all_builds).index(t) for t in ("heads", "honokodae"))
    assert HEAD.relative_to(ROOT).as_posix() in all_builds["heads"]
    assert BODY.relative_to(ROOT).as_posix() in all_builds["honokodae"]
