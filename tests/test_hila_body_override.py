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
#: every bone a palm or a finger can be weighted to, by rig name
PALM_AND_FINGERS = tuple(f"Hand{finger}{joint}" for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky")
                         for joint in (1, 2, 3))
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
    # The two models and the two material configs change; the `.object`s are the
    # game's own now, because the glove drawable they switch on stays in use (D59).
    assert changed == ({hila.UNIT + s + ".model" for s in ("", "_menu")}
                       | {hila.MATERIAL + s + ".material_config" for s in ("", "_cc")})
    assert all(new[hila.UNIT + s + ".object"] == old[hila.UNIT + s + ".object"] for s in ("", "_menu"))
    for suffix in ("", "_menu"):
        obj = ET.fromstring(new[hila.UNIT + suffix + ".object"])
        assert obj.find("diesel").get("materials") == hila.MATERIAL
        enabled = {elem.get("name"): elem for elem in obj.findall(".//graphics//object") if elem.get("enabled") == "true"}
        # The glove drawable is load-bearing now: the outfit's hands are cut where
        # the palms begin (D59), so Hila's stock gloves are the hands that show.
        assert set(enabled) == {"g_body", "g_head", "s_body", hila.GLOVE}
        assert enabled["s_body"].get("shadow_caster") == "true"
        assert [elem.get("name") for elem in obj.iter("object")].count(hila.GLOVE) == 1
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
    return {name: hila.Drawable.read(m, name) for name in ("g_body", "s_body", "g_head")}


def test_only_the_two_mesh_blocks_change_and_the_gloves_stay(models):
    output, native, donor = models
    # Every section of the native unit survives, the stock glove block included:
    # it is the hand the pack now relies on (D59).
    assert len({s.id for s in output.sections}) == len(output.sections)
    assert [s.id for s in output.sections] == [s.id for s in native.sections]
    assert _glove_block(native) <= {s.id for s in output.sections}
    changed = {s.id for s in output.sections if s.payload != native.by_id(s.id).payload}
    new, old = _draws(output), _draws(native)
    assert changed == {s.id for name in ("g_body", "s_body") for s in
                       (new[name].section, new[name].geometry, new[name].topology, new[name].skin)}
    authored = hila.Drawable.read(donor, "g_body")
    assert new["g_body"].geo["vert_count"] == authored.geo["vert_count"]
    assert new["g_body"].top["indices"] == authored.top["indices"]
    # The caster is the donor's cut caster (no palms, D59) plus the solid head.
    shadow_tris = len(hila.Drawable.read(donor, "s_body").faces)
    assert len(new["s_body"].faces) == shadow_tris + old["g_head"].data["atoms"][0]["tri_count"]
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


def _orphans(model, gone):
    """Objects parented to a deleted node go with it (`assemble_model` prunes them)."""
    pruned, changed = set(gone), True
    while changed:
        changed = False
        for s in model.sections:
            if s.id in pruned:
                continue
            parent = (dm.decode_object3d(s.payload) if s.type == dm.OBJECT3D
                      else dm.decode_model_data(s.payload) if s.type == dm.MODEL_DATA else {}).get("parent")
            if parent in pruned:
                pruned.add(s.id)
                changed = True
    return pruned - gone


def _glove_block(model):
    """Section ids that belong only to the stock glove drawable."""
    draw = hila.Drawable.read(model, hila.GLOVE)
    ip = dm.decode_topologyip(model.by_id(draw.data["topologyip"]).payload)
    return {draw.section.id, draw.geometry.id, draw.topology.id, draw.skin.id,
            draw.data["passthroughgp"], draw.data["topologyip"], ip["topology"]}


@pytest.mark.parametrize("side", ["Left", "Right"])
def test_the_outfits_hands_end_where_the_palm_begins(models, side):
    """No finger survives in the body, and the cut is 4 cm past the palm line.

    The plane is `build_models.palm_planes`: through the rig's `Hand` joint, along
    the axis to the four knuckles. Since D62 the cut sits `PALM_EXTEND_CM` (4 cm)
    past it, inside the palm, so the arm ends inside the heister's glove; the body
    inherits that cut from `dist/Honoka/OfficeSuite.zip`.
    """
    output, native, _ = models
    body = hila.Drawable.read(output, "g_body")
    objs, worlds = bm._resolve_worlds(output)
    names = {obj["name_hash"]: sid for sid, obj in objs.items()}
    hand = names[dm.hash64(side + "Hand")]
    thenar = names[dm.hash64(side + "HandThumb1")]  # the palm's own proximal few cm
    fingers = [names[dm.hash64(side + joint)] for joint in PALM_AND_FINGERS
               if joint != "HandThumb1"]
    palette = np.asarray(body.bind["objects"])
    indices = np.asarray(body.geo["blendindices"])
    weights = np.asarray(body.geo["blendweights"])
    dominant = palette[indices[np.arange(len(indices)), weights.argmax(axis=1)]]
    # Not one vertex is *dominated* by a finger: the fingers are gone, and what the
    # 4 cm extension keeps is `Hand` and the thenar (`Thumb1`), which is the same
    # territory the palm line itself bounds (D62). The rim may also carry a hand bone
    # as a minor influence, which is why this looks at the dominant weight.
    assert not np.isin(dominant, fingers).any()
    assert np.isin(dominant, [hand, thenar]).any(), "the arm does not reach the palm"

    wrist = np.asarray(worlds[hand][12:15], dtype=np.float64)
    knuckles = np.mean([np.asarray(worlds[names[dm.hash64(side + k)]][12:15], dtype=np.float64)
                        for k in bm.PALM_KNUCKLES], axis=0)
    axis = knuckles - wrist
    axis /= np.linalg.norm(axis)
    verts = np.asarray(body.geo["verts"], dtype=np.float64)
    rel = verts - wrist
    axial = rel @ axis
    perp = np.linalg.norm(rel - np.outer(axial, axis), axis=1)
    near = perp < 28.0
    assert near.any()
    # The mesh reaches into the palm by the extension, and no further.
    assert axial[near].max() <= 4.05, "geometry survives past the palm extension"
    # ... and the sleeve does not stop at the crease, leaving the glove in mid-air.
    assert axial[near].max() > 3.8, "the mesh stops short of the palm extension"


def test_the_stock_gloves_are_shipped_and_enabled(models, files):
    """Hila's glove block survives and its node stays enabled: it is the hand that shows now."""
    pack, _ = files
    output, native, _ = models
    glove = _glove_block(native)
    assert glove <= {s.id for s in output.sections}
    assert hila.Drawable.read(output, hila.GLOVE).faces.size > 0
    for suffix in ("", "_menu"):
        text = pack[(hila.UNIT + suffix + ".object")].decode("utf-8")
        assert f'name="{hila.GLOVE}"' in text
        graphic_group = ET.fromstring(text).find(".//graphic_group")
        assert graphic_group.get("culling_object") == "g_body"


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
