"""The asset loader needs the correct install root, registration of new paths,
valid 0..N-1 local bone-palette indices in every SkinBones section, the vanilla
DODB container layout (contiguous 1..N section IDs in canonical order,
Topology index counts within uint16 limits), and full DXT5 mipmap pyramids in
every .texture.
"""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


metadata = _load("pd2_package_metadata", "tools/pd2-port/package_metadata.py")
skin_repair = _load("pd2_repair_skin_palettes", "tools/pd2-port/repair_skin_palettes.py")
dds = _load("pd2_dds", "tools/pd2-port/dds.py")
dmodel = _load("pd2_dmodel", "tools/pd2-port/dmodel.py")


# ------------------------------------------------------------------ fixtures
def _pack(*values, fmt="<I"):
    return b"".join(struct.pack(fmt, v) for v in values)


def make_model_bytes(
    *,
    material_names,
    atoms,
    faces,
    vert_count,
    bone_count=2,
    section_ids=None,
    order=None,
):
    """Build a minimal but complete DODB v1 .model buffer.

    atoms: list of (material_index, base_vertex, geo_len, tri_count, base_index)
    faces: list of (a, b, c) vertex indices
    section_ids: optional dict tag -> section id (default 1..N in canonical order)
    order: optional list of tags giving the on-disk section order
    """
    tags = [
        "animation_data",
        "author",
        "material_group",
        "materials",  # placeholder: one section per material name
        "object3D",
        "model_data",
        "skinbones",
        "geometry",
        "topology",
        "passthroughGP",
        "topologyIP",
    ]
    entries = ["animation_data", "author", "material_group"]
    entries += [f"material:{name}" for name in material_names]
    entries += ["object3D", "model_data", "skinbones", "geometry", "topology",
                "passthroughGP", "topologyIP"]

    if section_ids is None:
        section_ids = {e: i + 1 for i, e in enumerate(entries)}
    mat_ids = [section_ids[f"material:{name}"] for name in material_names]

    payloads = {}
    payloads["animation_data"] = struct.pack("<QII", 0x1234, 0, 0)
    payloads["author"] = b"test author"
    payloads["material_group"] = _pack(len(mat_ids), *mat_ids)
    for i, name in enumerate(material_names):
        payloads[f"material:{name}"] = (
            struct.pack("<Q", dmodel.hash_str(name)) + bytes(48) + _pack(0)
        )
    identity = b"".join(struct.pack("<f", 1.0 if i % 5 == 0 else 0.0) for i in range(16))
    payloads["object3D"] = (
        struct.pack("<Q", 0xAAAA) + _pack(0) + identity + _pack(3, 0, 0) + _pack(0)
    )
    gp_id = section_ids["passthroughGP"]
    tp_id = section_ids["topologyIP"]
    mg_id = section_ids["material_group"]
    sb_id = section_ids["skinbones"]
    model = (
        struct.pack("<Q", 0xBBBB)
        + _pack(0)
        + identity
        + _pack(0, 0, 0)
        + _pack(0)  # parent
        + _pack(3)  # version
        + _pack(gp_id, tp_id)
        + _pack(len(atoms))
    )
    for mat_index, base_vertex, geo_len, tri_count, base_index in atoms:
        model += _pack(base_vertex, tri_count, base_index, geo_len, mat_index)
    model += _pack(mg_id, 0, 0)  # matgroup, lightset, properties
    model += struct.pack("<6f", 0, 0, 0, 1, 1, 1)  # bounds
    model += struct.pack("<fI", 1.0, 0)  # bounding radius/int
    model += _pack(sb_id)
    payloads["model_data"] = model

    sets = len(atoms) + 1
    sb = _pack(sets)
    palette = _pack(*range(bone_count))
    for _ in range(sets):
        sb += _pack(bone_count) + palette
    sb += _pack(0)  # root bone id
    sb += _pack(bone_count)
    sb += _pack(*([0] * bone_count))  # object ids
    sb += identity * bone_count  # rotations
    sb += identity  # global skin transform
    payloads["skinbones"] = sb

    geo = _pack(vert_count, 3)
    geo += _pack(3, 1, 7, 17, 3, 19)  # POSITION, BLENDINDICES, BLENDWEIGHT0
    geo += struct.pack(f"<{vert_count * 3}f", *([0.0, 0.0, 0.0] * vert_count))
    geo += struct.pack(f"<{vert_count * 4}H", *([0, 0, 0, 0] * vert_count))
    geo += struct.pack(f"<{vert_count * 3}f", *([1.0, 0.0, 0.0] * vert_count))
    geo += struct.pack("<Q", 0)
    payloads["geometry"] = geo

    topo = _pack(3, len(faces) * 3)
    for a, b, c in faces:
        topo += struct.pack("<3H", a, b, c)
    topo += _pack(0) + struct.pack("<Q", 0)
    payloads["topology"] = topo

    payloads["passthroughGP"] = _pack(
        section_ids["geometry"], section_ids["topology"]
    )
    payloads["topologyIP"] = _pack(section_ids["topology"])

    if order is None:
        order = entries
    body = b""
    for entry in order:
        sid = section_ids[entry]
        type_tag = entry.split(":", 1)[0]
        type_id = dmodel.TAGS_INV[
            {"materials": "material"}.get(type_tag, type_tag)
        ]
        body += _pack(type_id, sid, len(payloads[entry]), fmt="<I")
        body += payloads[entry]
    header = _pack(0x42444F44, 1, 16 + len(body), len(order))
    return header + body


# ------------------------------------------------------------------ shipped packages
@pytest.mark.parametrize("character", metadata.CHARACTERS)
def test_shipped_package(character):
    with ZipFile(ROOT / "dist" / f"lawson_{character}.zip") as archive:
        assert archive.testzip() is None
        prefix = f"lawson_{character}/"
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(n.startswith(prefix) for n in names)
        textures = {n[len(prefix):] for n in names if n.endswith(".texture")}
        assert len(textures) == 19
        manifest = ET.fromstring(archive.read(prefix + "main.xml"))
        add = manifest.find("AddFiles")
        assert add is not None
        assert add.attrib == {"directory": ".", "force": "false"}
        registered = {node.attrib["path"] + ".texture" for node in add}
        assert all(node.tag == "texture" for node in add)
        assert len(add) == len(textures)
        assert registered == textures

        # Every custom texture referenced by either material config is registered.
        configs = [n for n in names if n.endswith(".material_config")]
        assert len(configs) == 2
        for name in configs:
            material = ET.fromstring(archive.read(name))
            custom = [node.attrib["file"] for node in material.iter()
                      if node.attrib.get("file", "").startswith(metadata.TEXTURE_DIR + "/")]
            assert custom
            assert all(path + ".texture" in registered for path in custom)
        models = [n for n in names if n.endswith(".model")]
        assert len(models) == 2
        for model_name in models:
            model_bytes = archive.read(model_name)
            assert skin_repair.inspect_model_skin_palettes(model_bytes) == []
            assert skin_repair.validate_model_skinning(model_bytes) == []
            # vanilla DODB layout: contiguous 1..N ids in canonical order
            assert skin_repair.validate_model_skinning(model_bytes, strict_layout=True) == []
            sections, _, _, _, by_id = skin_repair.parse_model_bytes(model_bytes)
            assert [s.id for s in sections] == list(range(1, len(sections) + 1))
            skin_sections = [s for s in sections if s.type == skin_repair.TAG_SKINBONES]
            assert skin_sections
            for sec in skin_sections:
                sb = sec.obj
                assert all(
                    list(mapping) == list(range(sb.count))
                    for mapping in sb.bone_mappings
                )

        # Every .texture carries a complete vanilla-shaped DXT5 pyramid.
        for texture in textures:
            assert dds.validate_dxt5_texture(archive.read(prefix + texture)) == []

        expected = metadata.package_metadata(character, list(textures))
        for name, data in expected.items():
            assert archive.read(prefix + name) == data
        readme = archive.read(prefix + "README.txt").decode()
        assert f"PAYDAY 2\\assets\\mod_overrides\\lawson_{character}\\main.xml" in readme
        assert "BeardLib is REQUIRED" in readme
        assert "NOT been verified" in readme
        assert "SkinBones" in readme
        assert "BeardLib optional" not in readme


def test_shared_textures_are_identical():
    """force=false is safe only if the three packages supply identical shared maps."""
    packs = []
    for char in metadata.CHARACTERS:
        with ZipFile(ROOT / "dist" / f"lawson_{char}.zip") as archive:
            packs.append({Path(n).name: hashlib.sha256(archive.read(n)).hexdigest()
                          for n in archive.namelist() if n.endswith(".texture")})
    assert packs[0] == packs[1] == packs[2]


def test_repair_preserves_assets_and_is_repeatable(tmp_path):
    archive = tmp_path / "lawson_clover.zip"
    prefix = "lawson_clover/"
    texture = metadata.TEXTURE_DIR + "/test.texture"
    assets = {prefix + texture: b"DDS test", prefix + "units/test.model": b"model bytes"}
    with ZipFile(archive, "w") as z:
        for name, data in assets.items():
            z.writestr(name, data)
        z.writestr(prefix + "README.txt", "wrong old instructions")
    for _ in range(2):
        metadata.repair_archive(archive)
        with ZipFile(archive) as z:
            assert set(z.namelist()) == set(assets) | {prefix + "main.xml", prefix + "README.txt"}
            for name, data in assets.items():
                assert z.read(name) == data
            assert z.read(prefix + "main.xml") == metadata.package_metadata("clover", [texture])["main.xml"]


def test_skin_palette_repair_fixes_corrupted_mappings_and_is_idempotent(tmp_path):
    with ZipFile(ROOT / "dist" / "lawson_bonnie.zip") as src:
        good_model = src.read(
            "lawson_bonnie/units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model"
        )
    sections, _, _, _, _ = skin_repair.parse_model_bytes(good_model)
    # the multi-atom g_body carries the largest SkinBones palette table
    target_sec = max(
        (s for s in sections if s.type == skin_repair.TAG_SKINBONES),
        key=lambda s: (len(s.obj.bone_mappings), s.obj.count),
    )
    sb = target_sec.obj
    corrupted = bytearray(good_model)
    bad_bones = bytearray(struct.pack("<I", len(sb.bone_mappings)))
    for _ in sb.bone_mappings:
        bad_bones += struct.pack("<I", sb.count)
        bad_bones += struct.pack(f"<{sb.count}I", *sb.object_ids)
    corrupted[target_sec.start : target_sec.start + len(bad_bones)] = bad_bones
    corrupted_bytes = bytes(corrupted)

    issues = skin_repair.inspect_model_skin_palettes(corrupted_bytes)
    assert len(issues) == 1
    assert issues[0].section_id == target_sec.id
    assert issues[0].matches_object_ids is True
    assert skin_repair.validate_model_skinning(corrupted_bytes)

    archive = tmp_path / "lawson_bonnie.zip"
    prefix = "lawson_bonnie/"
    texture = metadata.TEXTURE_DIR + "/test.texture"
    model_entry = prefix + "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model"
    with ZipFile(archive, "w") as zf:
        zf.writestr(prefix + texture, b"DDS test")
        zf.writestr(model_entry, corrupted_bytes)

    first_report = skin_repair.repair_archive_skin_palettes(archive)
    assert first_report == {model_entry: [target_sec.id]}
    second_report = skin_repair.repair_archive_skin_palettes(archive)
    assert second_report == {model_entry: []}

    with ZipFile(archive) as zf:
        assert zf.read(model_entry) == good_model
        assert zf.read(prefix + texture) == b"DDS test"


def test_staged_metadata_matches_archive_metadata(tmp_path):
    texture = tmp_path / metadata.TEXTURE_DIR / "test.texture"
    texture.parent.mkdir(parents=True)
    texture.write_bytes(b"DDS test")
    metadata.write_metadata(tmp_path, "bonnie")
    for name, data in metadata.package_metadata("bonnie", [texture.relative_to(tmp_path).as_posix()]).items():
        assert (tmp_path / name).read_bytes() == data


@pytest.mark.parametrize("paths", [[], ["../bad.texture"], [metadata.TEXTURE_DIR + "/bad.dds"]])
def test_bad_texture_paths_rejected(paths):
    with pytest.raises(ValueError):
        metadata.package_metadata("clover", paths)


def test_wrong_archive_root_left_untouched(tmp_path):
    archive = tmp_path / "lawson_bonnie.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("unexpected/README.txt", "do not change")
    before = archive.read_bytes()
    with pytest.raises(ValueError, match="Unexpected ZIP root"):
        metadata.repair_archive(archive)
    assert archive.read_bytes() == before
    assert list(tmp_path.iterdir()) == [archive]


# ------------------------------------------------------------------ DODB layout
def test_normalize_leaves_vanilla_models_untouched():
    """The canonical layout must reproduce vanilla files byte-identically."""
    for rel in (
        "clover/npc_criminal_female_1.model",
        "Bonie/npc_criminal_bonnie.model",
        "Sydney/npc_criminal_sydney.model",
    ):
        data = (ROOT / rel).read_bytes()
        assert skin_repair.validate_model_skinning(data, strict_layout=True) == []
        out, fixed = skin_repair.normalize_model_container(data)
        assert out == data
        assert fixed == []


def test_shipped_models_normalize_idempotently():
    for char in metadata.CHARACTERS:
        with ZipFile(ROOT / "dist" / f"lawson_{char}.zip") as archive:
            for name in (n for n in archive.namelist() if n.endswith(".model")):
                data = archive.read(name)
                out, fixed = skin_repair.normalize_model_container(data)
                assert out == data
                assert fixed == []


def test_normalize_renumbers_gapped_ids_and_reorders_sections():
    """ID holes and out-of-order sections must be normalized away."""
    faces = [(0, 1, 2)] * 4
    base = make_model_bytes(
        material_names=["lawson_body"],
        atoms=[(0, 0, 3, 4, 0)],
        faces=faces,
        vert_count=3,
    )
    assert skin_repair.validate_model_skinning(base, strict_layout=True) == []

    # rebuild with gapped ids (3, 5, 7, ...) and the mesh groups before the
    # model_data block — exactly what build_character.py used to emit
    entries = [
        "animation_data", "author", "material_group", "material:lawson_body",
        "object3D", "model_data", "skinbones", "geometry", "topology",
        "passthroughGP", "topologyIP",
    ]
    gapped_ids = {entry: (i + 1) * 2 + 1 for i, entry in enumerate(entries)}
    broken_order = sorted(
        entries,
        key=lambda entry: {
            "animation_data": 0, "author": 1, "skinbones": 2, "geometry": 3,
            "topology": 4, "passthroughGP": 5, "topologyIP": 6, "object3D": 7,
            "model_data": 8, "material_group": 9, "material:lawson_body": 10,
        }[entry],
    )
    broken = make_model_bytes(
        material_names=["lawson_body"],
        atoms=[(0, 0, 3, 4, 0)],
        faces=faces,
        vert_count=3,
        section_ids=gapped_ids,
        order=broken_order,
    )
    assert skin_repair.validate_model_skinning(broken, strict_layout=True) != []

    out, _ = skin_repair.normalize_model_container(broken)
    assert skin_repair.validate_model_skinning(out, strict_layout=True) == []
    out_sections, _, _, _, _ = skin_repair.parse_model_bytes(out)
    assert [s.id for s in out_sections] == list(range(1, len(entries) + 1))
    # normalization rebuilt exactly the canonical original
    assert out == base


def test_trim_drops_hidden_layers_over_index_limit():
    """g_body-style meshes lose their redundant swim/under atoms when over 65535."""
    n_tris = 15000  # two atoms -> 90,000 indices > 65,535; one atom -> 45,000
    faces = [(0, 1, 2)] * n_tris + [(3, 4, 5)] * n_tris
    data = make_model_bytes(
        material_names=["lawson_swim", "lawson_body"],
        atoms=[(0, 0, 3, n_tris, 0), (1, 3, 3, n_tris, n_tris * 3)],
        faces=faces,
        vert_count=6,
    )
    sections, _, _, _, _ = skin_repair.parse_model_bytes(data)
    model = next(s for s in sections if s.type == skin_repair.TAG_MODEL)
    assert len(model.obj.render_atoms) == 2
    topo = next(s for s in sections if s.type == skin_repair.TAG_TOPOLOGY)
    assert len(topo.obj.faces) * 3 == n_tris * 6
    assert skin_repair.validate_model_skinning(data, strict_layout=True) != []

    out, fixed = skin_repair.normalize_model_container(data)
    assert fixed == [model.id]
    assert skin_repair.validate_model_skinning(out, strict_layout=True) == []
    out_sections, _, _, _, out_by_id = skin_repair.parse_model_bytes(out)
    out_model = next(s for s in out_sections if s.type == skin_repair.TAG_MODEL)
    assert len(out_model.obj.render_atoms) == 1
    out_topo = next(s for s in out_sections if s.type == skin_repair.TAG_TOPOLOGY)
    assert len(out_topo.obj.faces) * 3 == n_tris * 3
    out_geo = next(s for s in out_sections if s.type == skin_repair.TAG_GEOMETRY)
    assert out_geo.obj.vert_count == 3


# ------------------------------------------------------------------ DDS textures
def test_texture_repair_builds_pyramid_and_fixes_endpoint_order():
    rng = np.random.default_rng(7)
    img = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    payloads = dds.mip_payloads_from_image(img)
    assert len(payloads) == 6  # 32..1

    # mip-0-only buffer as the old build_package2 wrote it
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x00081007)
    struct.pack_into("<II", header, 12, 32, 32)
    struct.pack_into("<I", header, 20, len(payloads[0]))
    struct.pack_into("<I", header, 28, 0)
    struct.pack_into("<II", header, 76, 32, 0x4)
    header[84:88] = b"DXT5"
    struct.pack_into("<I", header, 108, 0x1000)

    # one block encoded the way the old encoder mis-ordered endpoints (c0 < c1,
    # indices fit against that written 4-colour palette)
    e0, e1 = 0x001F, 0xF800  # deliberately written c0 < c1

    def expand(v):
        return ((v >> 11 & 31) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v & 31) * 255 // 31)

    pal = [expand(e0), expand(e1),
           tuple((2 * expand(e0)[i] + expand(e1)[i]) // 3 for i in range(3)),
           tuple((expand(e0)[i] + 2 * expand(e1)[i]) // 3 for i in range(3))]
    # pixels are exact palette endpoints, so the repair can round-trip them
    pixels = [(pal[0] if i % 2 == 0 else pal[1]) + (255,) for i in range(16)]
    bits = 0
    for px, c in enumerate(pixels):
        best = min(range(4), key=lambda k: sum((c[i] - pal[k][i]) ** 2 for i in range(3)))
        bits |= best << (2 * px)
    bad_block = bytes([255, 255]) + b"\x00" * 6  # solid alpha header
    bad_block += struct.pack("<HH", e0, e1) + bits.to_bytes(4, "little")
    mip0 = bad_block + payloads[0][16:]

    broken = bytes(header) + mip0
    problems = dds.validate_dxt5_texture(broken)
    assert problems

    fixed, changed = dds.repair_dxt5_texture(broken)
    assert changed is True
    assert dds.validate_dxt5_texture(fixed) == []
    magic, size, flags, h, w, pitch, depth, mips = struct.unpack_from("<4s7I", fixed, 0)
    assert flags == 0x000A1007
    assert mips == 6
    assert struct.unpack_from("<I", fixed, 108)[0] == 0x00401008
    assert len(fixed) == 128 + sum(max(1, (32 >> i) // 4) ** 2 * 16 for i in range(6))
    # the mis-ordered block was re-encoded with c0 > c1 and keeps its colours
    new_c0, new_c1 = struct.unpack_from("<HH", fixed, 128 + 8)
    assert new_c0 > new_c1
    kept = dds._decode_block(fixed[128:144])
    assert kept == pixels

    # idempotent
    again, changed_again = dds.repair_dxt5_texture(fixed)
    assert changed_again is False
    assert again == fixed


def test_texture_repair_is_noop_on_valid_texture():
    rng = np.random.default_rng(3)
    img = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
    good = dds.pack_dds(dds.mip_payloads_from_image(img), 16)
    assert dds.validate_dxt5_texture(good) == []
    assert dds.repair_dxt5_texture(good) == (good, False)
