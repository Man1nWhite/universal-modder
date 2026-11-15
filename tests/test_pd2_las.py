"""Tests for the pd2-las pipeline against the tracked L4D2 source zip.

These are offline structural tests: they prove the VPK/MDL/VVD/VTX/VTF readers
work on the real source assets and that the LAS scaffold matches the 2B
registration contract. They are not an engine test.
"""
from __future__ import annotations

import hashlib
import struct
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE_ZIP = REPO / "models" / "l4d2_miranda_lawson_1.zip"
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

pytestmark = pytest.mark.skipif(
    not SOURCE_ZIP.is_file(), reason="source zip l4d2_miranda_lawson_1.zip not present"
)

VPK_INNER = "miranda_rochelle.vpk"


@pytest.fixture(scope="module")
def arc():
    from vpk import VpkArchive

    return VpkArchive.from_zip(SOURCE_ZIP, VPK_INNER)


@pytest.fixture(scope="module")
def tpp(arc):
    from source_model import load_model

    return load_model(
        arc.read("models/survivors/survivor_producer.mdl"),
        arc.read("models/survivors/survivor_producer.vvd"),
        arc.read("models/survivors/survivor_producer.dx90.vtx"),
    )


@pytest.fixture(scope="module")
def fps(arc):
    from source_model import load_model

    return load_model(
        arc.read("models/weapons/arms/v_arms_producer_new.mdl"),
        arc.read("models/weapons/arms/v_arms_producer_new.vvd"),
        arc.read("models/weapons/arms/v_arms_producer_new.dx90.vtx"),
    )


class TestVpk:
    def test_entry_inventory(self, arc):
        paths = {e.path for e in arc.entries}
        assert len(paths) == 25
        assert "addoninfo.txt" in paths
        assert "models/survivors/survivor_producer.mdl" in paths
        assert "models/weapons/arms/v_arms_producer_new.mdl" in paths
        assert "materials/models/miranda/miranda_body.vmt" in paths

    def test_read_crc_checked(self, arc):
        data = arc.read("addoninfo.txt")
        assert data.startswith(b'"AddonInfo"')

    def test_missing_entry_rejected(self, arc):
        from vpk import VpkError

        with pytest.raises(VpkError):
            arc.read("no/such/file.txt")

    def test_traversal_rejected(self, arc):
        from vpk import VpkError, _safe_rel_path

        with pytest.raises(VpkError):
            _safe_rel_path("../evil")
        with pytest.raises(VpkError):
            _safe_rel_path("/abs/path")
        with pytest.raises(VpkError):
            _safe_rel_path("C:/windows/path")

    def test_a_truncated_tree_is_a_vpk_error_not_a_valueerror(self):
        """Corrupt input must land in the same handler as every other failure."""
        from vpk import VPK_SIGNATURE, VpkArchive, VpkError

        blob = struct.pack("<III", VPK_SIGNATURE, 1, 8) + b"vmt\x00mode"
        with pytest.raises(VpkError, match="unterminated string"):
            VpkArchive(blob)

    def test_extract_layout(self, arc, tmp_path):
        written = arc.extract(tmp_path / "out")
        assert len(written) == 25
        assert (tmp_path / "out" / "models/survivors/survivor_producer.mdl").is_file()
        with open(tmp_path / "out" / "addoninfo.txt", "rb") as fh:
            assert fh.read().startswith(b'"AddonInfo"')


class TestSourceModel:
    def test_body_bones_and_geometry(self, tpp):
        assert tpp.name == "miranda.smd"
        assert len(tpp.bones) == 104
        assert tpp.bones[0].name == "ValveBiped.Bip01_Pelvis"
        assert tpp.bones[0].parent == -1
        names = {b.name for b in tpp.bones}
        assert {"ValveBiped.Bip01_Spine", "ValveBiped.Bip01_Head1"} <= names or \
            {"ValveBiped.Bip01_Spine", "ValveBiped.Bip01_Head"} <= names
        assert len(tpp.vertices) == 9874
        assert tpp.triangle_count > 15000
        assert tpp.skipped_bodygroup_models == 0  # this model has no alternates
        assert tpp.materials == [
            "miranda_hair",
            "eyeball_r",
            "eyeball_l",
            "miranda_face",
            "miranda_head",
            "miranda_body",
            "phy",
        ]

    def test_a_v44_header_is_not_rejected(self, arc, tpp):
        """HL2-era ragdolls are MDL 44; the offsets this reader uses are shared.

        The bytes are the same model with its version field rewritten, so this
        pins the *gate* (and documents the assumption), not a real v44 file.
        """
        from source_model import load_model

        mdl = bytearray(arc.read("models/survivors/survivor_producer.mdl"))
        struct.pack_into("<i", mdl, 4, 44)
        model = load_model(
            bytes(mdl),
            arc.read("models/survivors/survivor_producer.vvd"),
            arc.read("models/survivors/survivor_producer.dx90.vtx"),
        )
        assert (len(model.vertices), model.triangle_count) == (
            len(tpp.vertices),
            tpp.triangle_count,
        )

    def test_an_unsupported_mdl_version_names_the_readable_range(self, tpp):
        from source_model import load_model, SourceModelError

        with pytest.raises(SourceModelError, match="44-49"):
            load_model(b"IDST" + struct.pack("<i", 2531) + b"\x00" * 200, b"", b"")

    def test_mesh_material_coverage(self, tpp):
        by_mat = {m.material: len(m.triangle_indices) // 3 for m in tpp.meshes}
        assert set(by_mat) == {
            "miranda_hair",
            "eyeball_r",
            "eyeball_l",
            "miranda_face",
            "miranda_head",
            "miranda_body",
        }
        assert by_mat["miranda_body"] > 5000

    def test_vertex_weights_valid(self, tpp):
        for v in tpp.vertices[::500]:
            assert 1 <= len(v.weights) <= 3
            total = sum(w for _, w in v.weights)
            assert 0.99 <= total <= 1.01
            for bone, w in v.weights:
                assert 0 <= bone < len(tpp.bones)
                assert 0.0 < w <= 1.0

    def test_parent_indices_in_range(self, tpp):
        for i, b in enumerate(tpp.bones):
            assert b.parent == -1 or 0 <= b.parent < i

    def test_arms_model(self, fps):
        assert fps.name == "miranda_arms.smd"
        assert len(fps.bones) > 30
        assert fps.triangle_count > 2000
        assert fps.materials == ["miranda_body"]

    def test_triangle_indices_in_range(self, tpp, fps):
        for model in (tpp, fps):
            n = len(model.vertices)
            for mesh in model.meshes:
                assert all(0 <= i < n for i in mesh.triangle_indices)


class TestVtf:
    STEMS = [
        "miranda_body_color",
        "miranda_body_normal",
        "miranda_face_color",
        "miranda_face_normal",
        "miranda_head_color",
        "miranda_head_normal",
        "miranda_eyes",
    ]

    def test_all_material_textures_parse(self, arc):
        from vtf import parse_vtf

        for stem in self.STEMS:
            img = parse_vtf(arc.read(f"materials/models/miranda/{stem}.vtf"))
            assert img.format_name == "DXT5"
            assert img.mipmap_count >= 8
            assert img.width == img.height

    def test_dds_sizes_and_magic(self, arc):
        from vtf import parse_vtf, to_dds

        img = parse_vtf(arc.read("materials/models/miranda/miranda_body_color.vtf"))
        assert (img.width, img.height, img.mipmap_count) == (1024, 1024, 11)
        dds = to_dds(img)
        assert dds[:4] == b"DDS "
        expected = 128 + 1024 * 1024 + 262144 + 65536 + 16384 + 4096 + 1024 + 256 + 64 + 16 + 16 + 16
        assert len(dds) == expected

    def test_mip_order_largest_first(self, arc):
        """The clean mip 0 must be the file-tail slice (VTF stores smallest first)."""
        from vtf import parse_vtf, to_dds

        img = parse_vtf(arc.read("materials/models/miranda/miranda_face_color.vtf"))
        dds = to_dds(img)
        body = dds[128:]
        mip0 = body[: 1024 * 1024]
        assert mip0 == img.data[-1024 * 1024 :]

    def test_png_preview(self, arc):
        from vtf import parse_vtf, to_png

        img = parse_vtf(arc.read("materials/models/miranda/miranda_eyes.vtf"))
        png = to_png(img)
        assert png.startswith(b"\x89PNG")
        assert (img.width, img.height) == (128, 128)


class TestDdsEncode:
    def test_bc3_roundtrip_solid(self):
        import numpy as np

        from dds_encode import rgba_to_bc3_dds

        rgba = np.zeros((8, 8, 4), dtype=np.uint8)
        rgba[..., 0] = 200
        rgba[..., 1] = 120
        rgba[..., 2] = 90
        rgba[..., 3] = 255
        dds = rgba_to_bc3_dds(rgba)
        assert dds[:4] == b"DDS "
        assert len(dds) == 128 + 4 * 16  # 2x2 blocks

        import io

        from PIL import Image

        im = Image.open(io.BytesIO(dds))
        im.load()
        out = np.asarray(im.convert("RGBA"))
        # naive endpoints quantize to 565; allow ~8 per channel
        assert abs(int(out[0, 0, 0]) - 200) <= 8
        assert abs(int(out[0, 0, 1]) - 120) <= 8
        assert abs(int(out[0, 0, 3]) - 255) <= 2

    def test_bc3_alpha_codes_are_written_in_the_order_of_the_format(self):
        """Code 0 is alpha_0, code 1 is alpha_1, codes 2 to 7 run from the one to the other.

        `rgba_to_bc3_dds` used to write a texel's position on the ramp as its
        code. A decoder then read the texels meant to be the minimum one step
        above it, and the ones meant for the step below the maximum as the
        minimum. Nothing showed it, because the only test encoded a flat image:
        the face diffuse shipped with its gloss scrambled inside 80 % of its
        blocks (3.9 % of the texels off by two or more, the worst by 29 of 255).
        A ramp has every code in it.
        """
        import numpy as np

        import dds_encode

        ramp = np.zeros((4, 4, 4), dtype=np.uint8)
        ramp[..., :3] = (120, 90, 60)
        ramp[..., 3] = np.arange(16, dtype=np.uint8).reshape(4, 4) * 16          # 0, 16, ... 240
        for name, dds in (
            ("rgba_to_bc3_dds", dds_encode.rgba_to_bc3_dds(ramp)),
            ("encode_bc3_texels", dds_encode._dds_header(4, 4, b"DXT5")
             + dds_encode.encode_bc3_texels(dds_encode.image_to_texels(ramp)).tobytes()),
        ):
            assert (dds[128], dds[129]) == (240, 0), name                         # alpha_0 > alpha_1
            alpha = dds_encode.decode_bc3_level(dds)[..., 3].astype(int).ravel()
            # eight values 34 apart: nearest is at most 17 away, and the order survives
            assert np.abs(alpha - ramp[..., 3].ravel()).max() <= 17, (name, alpha.tolist())
            assert (np.diff(alpha) >= 0).all(), (name, alpha.tolist())
            assert (alpha[0], alpha[-1]) == (0, 240), (name, alpha.tolist())

    def test_fitted_encoder_keeps_the_colour_most_of_a_block_has(self):
        """A block with three hues: the endpoints have to be two of its colours.

        Nine texels of blue iris, three of black pupil, four of grey sclera: what
        a 16x16 level of the eye texture is made of. The corners of the bounding
        box are a dark and a light grey, and the iris comes out grey; that is how
        the first mip levels made for this texture looked from three metres. The
        pair search keeps the iris and the pupil and gives up the sclera.
        """
        import numpy as np

        import dds_encode

        blue, black, grey = (19, 54, 111), (2, 3, 5), (100, 92, 88)
        block = np.zeros((4, 4, 4), dtype=np.uint8)
        block[..., :3] = np.array([black] * 3 + [blue] * 9 + [grey] * 4, dtype=np.uint8).reshape(4, 4, 3)
        block[..., 3] = 9

        def decoded(payload: bytes) -> np.ndarray:
            return dds_encode.decode_bc3_level(dds_encode._dds_header(4, 4, b"DXT5") + payload).astype(int)

        fitted = dds_encode.encode_bc3_texels(dds_encode.image_to_texels(block))
        iris = decoded(fitted.tobytes())[..., :3].reshape(16, 3)[3:12]
        assert np.abs(iris - blue).max() <= 8, iris[0]
        naive = decoded(dds_encode.rgba_to_bc3_dds(block)[128:])[..., :3].reshape(16, 3)[3:12]
        assert np.abs(naive - blue).max() > 40, "the bounding box no longer loses the iris: update this test"

        c0 = fitted[:, 8].astype(int) | (fitted[:, 9].astype(int) << 8)
        c1 = fitted[:, 10].astype(int) | (fitted[:, 11].astype(int) << 8)
        assert (c0 >= c1).all()
        # one colour: both endpoints are it and every code is 0
        flat = np.zeros((8, 8, 4), dtype=np.uint8)
        flat[...] = (200, 120, 88, 9)
        blocks = dds_encode.encode_bc3_texels(dds_encode.image_to_texels(flat))
        assert len(blocks) == 4 and len({bytes(b) for b in blocks}) == 1
        assert bytes(blocks[0][2:8]) == bytes(6) and bytes(blocks[0][12:]) == bytes(4)
        assert np.abs(decoded(blocks[:1].tobytes())[0, 0] - (200, 120, 88, 9)).max() <= 4
        # the same input gives the same bytes, and the shape is checked
        assert np.array_equal(fitted, dds_encode.encode_bc3_texels(dds_encode.image_to_texels(block)))
        with pytest.raises(ValueError):
            dds_encode.encode_bc3_texels(np.zeros((3, 15, 4), dtype=np.uint8))
        with pytest.raises(ValueError):
            dds_encode.image_to_texels(np.zeros((6, 8, 4), dtype=np.uint8))

    def test_weights_say_which_texels_a_block_has_to_keep(self):
        """Thirteen texels of sclera, two of iris, one of pupil: an 8x8 level of the eye.

        Every texel counting the same, the block spends its line on the sclera
        and the iris comes out grey. With the iris and the pupil counting sixteen
        times as much, it keeps them.
        """
        import numpy as np

        import dds_encode

        blue, black = (25, 60, 120), (2, 3, 5)
        sclera = [(150 - 6 * k, 137 - 6 * k, 131 - 6 * k) for k in range(13)]      # the lid's shadow across it
        block = np.zeros((4, 4, 4), dtype=np.uint8)
        block[..., :3] = np.array([black, blue, blue] + sclera, dtype=np.uint8).reshape(4, 4, 3)
        block[..., 3] = 9
        texels = dds_encode.image_to_texels(block)

        def iris(blocks) -> np.ndarray:
            dds = dds_encode._dds_header(4, 4, b"DXT5") + blocks.tobytes()
            return dds_encode.decode_bc3_level(dds).astype(int)[0, 1, :3]

        even = iris(dds_encode.encode_bc3_texels(texels))
        assert even[2] - even[0] < 30, even                                         # greyish
        weights = np.ones((1, 16), dtype=np.int64)
        weights[0, :3] = 16
        kept = iris(dds_encode.encode_bc3_texels(texels, weights))
        assert np.abs(kept - blue).max() <= 8, kept
        assert np.array_equal(dds_encode.encode_bc3_texels(texels, np.ones((1, 16), dtype=np.int64)),
                              dds_encode.encode_bc3_texels(texels))
        # alpha does not depend on the weights
        assert np.array_equal(dds_encode.encode_bc3_texels(texels, weights)[:, :8],
                              dds_encode.encode_bc3_texels(texels)[:, :8])
        for bad in (np.ones((1, 15), dtype=np.int64), np.ones((1, 16)), -np.ones((1, 16), dtype=np.int64)):
            with pytest.raises(ValueError):
                dds_encode.encode_bc3_texels(texels, bad)
        with pytest.raises(ValueError):
            dds_encode.bc3_dds_from_levels([block, block[:2, :2], block[:1, :1]], [np.ones((4, 4), dtype=np.int64)])

    def test_mip_levels_average_light_and_leave_gloss_as_data(self):
        """Black beside white is mid grey as light, which is 188 stored, not 128.

        Averaging the stored values darkens whatever has contrast. Gloss is not
        light: it is averaged as the number it is.
        """
        import numpy as np

        import build_las
        import dds_encode

        image = np.zeros((4, 4, 4), dtype=np.uint8)
        image[:, ::2] = (255, 255, 255, 200)                    # white columns, gloss 200; black ones, gloss 0
        levels = build_las.mip_levels(image)
        assert [level.shape for level in levels] == [(4, 4, 4), (2, 2, 4), (1, 1, 4)]
        assert levels[0] is image
        for level in levels[1:]:
            assert level.dtype == np.uint8
            assert (level[..., :3] == 188).all() and (level[..., 3] == 100).all(), level[0, 0]
        # each level is the average of level 0, not of the level above: no rounding piles up
        rng = np.random.default_rng(3)
        noise = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
        light = dds_encode.srgb_to_linear(noise[..., :3] / 255.0).mean(axis=(0, 1))
        last = build_las.mip_levels(noise)[-1][0, 0]
        assert np.array_equal(last[:3], np.rint(dds_encode.linear_to_srgb(light) * 255.0))
        assert last[3] == np.rint(noise[..., 3].mean())
        # the two conversions undo each other on every stored value
        stored = np.arange(256) / 255.0
        assert np.array_equal(np.rint(dds_encode.linear_to_srgb(dds_encode.srgb_to_linear(stored)) * 255.0),
                              np.arange(256))
        for shape in ((4, 8, 4), (6, 6, 4), (4, 4, 3)):
            with pytest.raises(ValueError):
                build_las.mip_levels(np.zeros(shape, dtype=np.uint8))
        with pytest.raises(ValueError):
            dds_encode.box_reduce(np.zeros((6, 6, 4)), 4)

    def test_bc3_dds_from_levels_is_the_full_chain_in_the_header_shape_of_the_game(self):
        """What the eye texture is written with: every level, the game's header, no black borders."""
        import numpy as np

        import build_las
        import dds_encode

        yy, xx = np.mgrid[0:32, 0:32]
        shade = (xx + yy) * 2 + 40                # one ramp: the colours of a block lie on a line
        image = np.stack([shade, shade // 2 + 40, 255 - shade, xx + 9], axis=-1).astype(np.uint8)
        levels = build_las.mip_levels(image)
        dds = dds_encode.bc3_dds_from_levels(levels)
        flags, height, width, pitch, _depth, count = struct.unpack_from("<6I", dds, 8)
        # CAPS | HEIGHT | WIDTH | PIXELFORMAT | MIPMAPCOUNT | LINEARSIZE; TEXTURE | COMPLEX | MIPMAP
        assert (flags, struct.unpack_from("<I", dds, 108)[0]) == (0x000A1007, 0x00401008)
        assert (width, height, count, pitch) == (32, 32, 6, 64 * 16)
        layout = dds_encode.bc3_levels(dds)                      # raises unless the payload is the declared chain
        assert [(w, h) for _offset, w, h in layout] == [(32, 32), (16, 16), (8, 8), (4, 4), (2, 2), (1, 1)]
        assert [offset for offset, _w, _h in layout] == [128, 1152, 1408, 1472, 1488, 1504] and len(dds) == 1520
        for level, reference in enumerate(levels):
            got = dds_encode.decode_bc3_level(dds, level).astype(int)
            assert got.shape == reference.shape
            # measured: 0.7 to 6.0 of 255 (the 4x4 level holds the whole ramp in one block)
            assert np.abs(got[..., :3] - reference[..., :3]).mean() < 8, level
            assert np.abs(got[..., 3] - reference[..., 3]).max() <= 2, level
        # a level smaller than a block repeats its edge: a flat image is the same block all the way down
        flat = np.zeros((8, 8, 4), dtype=np.uint8)
        flat[...] = (200, 120, 88, 9)
        payload = dds_encode.bc3_dds_from_levels(build_las.mip_levels(flat))[128:]
        assert len({payload[i:i + 16] for i in range(0, len(payload), 16)}) == 1
        # the chain has to be whole, and a file that is not what its header says is refused
        with pytest.raises(ValueError):
            dds_encode.bc3_dds_from_levels(levels[:-1])
        with pytest.raises(ValueError):
            dds_encode.bc3_dds_from_levels([levels[0], levels[2]])
        with pytest.raises(ValueError):
            dds_encode.bc3_levels(dds[:-16])
        with pytest.raises(ValueError):
            dds_encode.bc3_levels(b"DDS " + bytes(200))


@pytest.fixture(scope="module")
def miranda_textures(tmp_path_factory):
    """The textures stage, run once: pack texture name -> the file it wrote."""
    import build_las

    out = tmp_path_factory.mktemp("miranda_textures")
    assert build_las.main(["--stage", "textures", "--out", str(out)]) == 0
    return {path.stem: path.read_bytes() for path in (out / "textures").glob("*.texture")}


class TestMirandaTextures:
    """The two unit textures the build does not simply convert: the face and the eyes."""

    def test_every_unit_texture_leaves_the_stage_with_the_full_pyramid(self, miranda_textures):
        """Five are converted and bring the source's levels; the two made here must not have fewer.

        The repainted face and the drawn eyes used to be encoded as one level
        each, and shipped like that.
        """
        import build_las
        import dds_encode

        assert sorted(miranda_textures) == sorted(build_las.VTF_TO_PACK.values())
        for name, raw in sorted(miranda_textures.items()):
            layout = dds_encode.bc3_levels(raw)                  # DXT5, and the payload is the declared chain
            width, height = layout[0][1:]
            assert width == height and len(layout) == width.bit_length(), (
                f"{name}: {len(layout)} mip levels for {width}x{height}")
            assert (struct.unpack_from("<I", raw, 8)[0], struct.unpack_from("<I", raw, 108)[0]) == (
                0x000A1007, 0x00401008), name

    def test_repaint_touches_only_the_eye_sockets_and_the_lash_lines(self, arc):
        import numpy as np

        import build_las
        import dds_encode

        before = dds_encode.decode_bc3_level(build_las.converted_face_diffuse(arc))
        kept = before.copy()
        after = build_las.repaint_face(before)
        assert np.array_equal(before, kept), "the input was painted on"
        rows, cols = np.nonzero((after != before).any(axis=2))
        u, v = (cols + 0.5) / before.shape[1], (rows + 0.5) / before.shape[0]
        sockets = (np.abs(v - 0.472) < 0.03) & ((np.abs(u - 0.454) < 0.025) | (np.abs(u - 0.559) < 0.025))
        lashes = (v > 0.25) & (v < 0.31) & (((u > 0.18) & (u < 0.33)) | ((u > 0.67) & (u < 0.82)))
        waterlines = (np.abs(v - 0.926) < 0.03) & ((u < 0.14) | (u > 0.86))
        assert (sockets | lashes | waterlines).all(), "the repaint reaches outside the areas it is meant for"
        # measured: 18,289 texels, 1.74 % of the texture
        assert 0.010 < len(rows) / before[..., 0].size < 0.025
        assert (after[..., 3] <= before[..., 3]).all(), "the repaint raised gloss somewhere"
        changed = after[rows, cols, :3].astype(int).sum(axis=1) < before[rows, cols, :3].astype(int).sum(axis=1)
        assert changed.mean() > 0.95, "the repaint is meant to darken"

    def test_face_levels_are_the_source_levels_plus_the_repaint(self, arc):
        """Every level gets the repaint; nothing else about the source's levels changes.

        The amount of light the repaint takes away is the same at every level,
        because a level's texel carries the average of what it covers (up to
        what eight bits can hold: the faint edge of the lash shading moves a
        texel of a lower level by less than half a step and is rounded away).
        And gloss stays under the ceiling at every level, which the converted
        texture does not: ten texels of its level 1 are at 255.
        """
        import numpy as np

        import build_las
        import dds_encode

        converted = build_las.converted_face_diffuse(arc)
        levels, changed = build_las.face_levels(converted)
        source = [dds_encode.decode_bc3_level(converted, k) for k in range(len(levels))]
        assert len(levels) == 11 and [level.shape[0] for level in levels] == [1024 >> k for k in range(11)]
        assert np.array_equal(levels[0], build_las.repaint_face(source[0]))

        ceiling = build_las.DF_SPECULAR_FROM_NORMAL["miranda_face_color"][2]
        assert int(source[1][..., 3].max()) == 255, "the converted texture no longer has the 255s: update this test"
        assert int((source[1][..., 3] > ceiling).sum()) == 10
        assert max(int(level[..., 3].max()) for level in levels) <= ceiling

        def light(image):
            return dds_encode.srgb_to_linear(image[..., :3] / 255.0).mean()

        taken = light(source[0]) - light(levels[0])
        assert taken > 0.0002                                    # measured: 0.00038 of full white
        for k in range(1, 9):                                    # measured: within 12 % down to 4x4
            assert abs((light(source[k]) - light(levels[k])) - taken) < 0.15 * taken, k

        reached = changed[0].any(axis=2)
        for k, (level, before, differs) in enumerate(zip(levels, source, changed)):
            assert differs.shape == level.shape[:2] + (2,)
            assert np.array_equal(differs[..., 0], (level[..., :3] != before[..., :3]).any(axis=2))
            assert np.array_equal(differs[..., 1], level[..., 3] != before[..., 3])
            # a texel changes only if the repaint reaches the area it covers, or its gloss was over the ceiling
            covers = dds_encode.box_reduce(reached, 1 << k)[..., 0] > 0
            assert not (differs.any(axis=2) & ~covers & (before[..., 3] <= ceiling)).any(), k
        assert not changed[9].any() and not changed[10].any()    # 2x2 and 1x1: the repaint is under one step

    def test_repainted_face_encodes_again_only_what_the_repaint_changed(self, arc, miranda_textures):
        """Every other byte is the source's: its blocks, at every level.

        The build used to decode the whole face, repaint 2 % of it and encode
        all of it again with the naive encoder: a second lossy pass over every
        block, and the source's own mip levels thrown away.
        """
        import numpy as np

        import build_las
        import dds_encode

        converted = build_las.converted_face_diffuse(arc)
        face = miranda_textures["miranda_face_df"]
        assert face == build_las.repainted_face_texture(converted)
        assert face[:128] == converted[:128] and len(face) == len(converted)
        levels, changed = build_las.face_levels(converted)
        total = touched = 0
        for k, ((offset, width, height), level, differs) in enumerate(
                zip(dds_encode.bc3_levels(converted), levels, changed)):
            count = ((width + 3) // 4) * ((height + 3) // 4)
            old = np.frombuffer(converted, dtype=np.uint8, count=count * 16, offset=offset).reshape(-1, 16)
            new = np.frombuffer(face, dtype=np.uint8, count=count * 16, offset=offset).reshape(-1, 16)
            across = (width + 3) // 4
            mask = dds_encode.pad_to_blocks(differs).reshape(-1, 4, across, 4, 2).any(axis=(1, 3)).reshape(-1, 2)
            assert np.array_equal(old[~mask[:, 0], 8:], new[~mask[:, 0], 8:]), f"level {k}: a colour block changed"
            assert np.array_equal(old[~mask[:, 1], :8], new[~mask[:, 1], :8]), f"level {k}: an alpha block changed"
            total += count
            touched += int((old != new).any(axis=1).sum())
            # and what was encoded again shows the picture it was meant to
            got = dds_encode.decode_bc3_level(face, k).astype(int)
            where = differs.any(axis=2)
            if where.any():
                # measured: colour 0.3 to 6.6 of 255 on average, gloss at most 3
                assert np.abs(got[where][:, :3] - level[where][:, :3]).mean() < 8, k
                assert np.abs(got[where][:, 3] - level[where][:, 3]).max() <= 4, k
            c0 = new[:, 8].astype(int) | (new[:, 9].astype(int) << 8)
            c1 = new[:, 10].astype(int) | (new[:, 11].astype(int) << 8)
            assert (c0 >= c1).all(), k
        # measured: 1,731 of 87,383 blocks, 1.98 %
        assert total == 87383 and 0.015 < touched / total < 0.025, (touched, total)

    def test_eye_keeps_a_blue_iris_at_every_size(self, miranda_textures):
        """The eye is drawn from the 16x16 and 8x8 levels a few steps away.

        The first mip levels made for this texture had a grey iris there:
        (61, 55, 52) at 16x16, where the picture has (25, 57, 117). The format
        cannot hold three hues in a block and the encoder kept the wrong two.
        The pair search keeps the iris where it is most of a block; `eye_weights`
        makes it keep the iris where it is three texels of sixteen.
        """
        import numpy as np

        import build_las
        import dds_encode

        eyes = miranda_textures["miranda_eyes"]
        reference = build_las.mip_levels(build_las.draw_eye())
        assert len(dds_encode.bc3_levels(eyes)) == len(reference) == 10
        weights = build_las.eye_weights()
        assert [w.shape for w in weights] == [level.shape[:2] for level in reference]
        assert all(w.dtype == np.int64 and w.min() >= 1 and w.max() <= build_las.EYE_IRIS_WEIGHT for w in weights)
        assert weights[0][256, 256] == build_las.EYE_IRIS_WEIGHT and weights[0][0, 0] == 1

        def iris(image):
            side = image.shape[0]
            centre = (np.arange(side) + 0.5) / side - 0.5
            radius = np.hypot(centre[None, :], centre[:, None])
            ring = (radius > 0.14) & (radius < 0.24)
            light = dds_encode.srgb_to_linear(image[..., :3][ring] / 255.0).mean(axis=0)
            return dds_encode.linear_to_srgb(light) * 255.0

        for level in range(8):                                   # 512x512 down to 4x4; below that there is no ring
            want, got = iris(reference[level]), iris(dds_encode.decode_bc3_level(eyes, level))
            assert want[2] - want[0] > 50, (level, want)         # the picture itself: blue
            # blue minus red, measured: 104 of 104 at level 0, 93 of 92 at 16x16, 93 of 94 at 8x8,
            # 50 of 56 at 4x4. Without `eye_weights` the 8x8 level has 43 of 94.
            assert got[2] - got[0] > 0.8 * (want[2] - want[0]), (
                f"level {level}: the iris is {np.rint(got).astype(int).tolist()}, "
                f"the picture has {np.rint(want).astype(int).tolist()}")
            gloss = dds_encode.decode_bc3_level(eyes, level)[..., 3].astype(int)
            assert np.abs(gloss - reference[level][..., 3]).max() <= 2, level


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    import numpy as np

    from dds_encode import rgba_to_bc3_dds
    from las_pack import write_pack

    out = tmp_path_factory.mktemp("packout")
    textures = {
        "miranda_body_df.texture": b"DDS fake",
        "miranda_body_nm.texture": b"DDS fake",
    }
    icon = rgba_to_bc3_dds(np.zeros((16, 16, 4), dtype=np.uint8))
    return write_pack(out, textures, icon, {"note": "test"}, models_present=False)


class TestLasScaffold:
    def test_layout(self, pack):
        assert (pack / "main.xml").is_file()
        assert (pack / "hooks" / "miranda_las.lua").is_file()
        assert (pack / "localization" / "english.txt").is_file()
        assert (pack / "WIP_DO_NOT_INSTALL.txt").is_file()
        assert (
            pack / "assets/units/miranda/skins/miranda/miranda.unit"
        ).is_file()
        assert (
            pack / "assets/units/miranda/skins/miranda/fps_miranda.object"
        ).is_file()

    def test_hook_matches_2b_contract(self, pack):
        lua = (pack / "hooks" / "miranda_las.lua").read_text()
        assert "LegendaryArmours = LegendaryArmours or {}" in lua
        assert "la.miranda = {" in lua
        assert 'unit = "units/miranda/skins/miranda/miranda"' in lua
        assert 'fps_unit = "units/miranda/skins/miranda/fps_miranda"' in lua
        for flag in (
            "hide_mask",
            "hide_armor",
            "replace_all",
            "fps_hide_armor",
            "fps_replace_body",
        ):
            assert f"{flag} = true" in lua

    def test_main_xml_registration(self, pack):
        xml = (pack / "main.xml").read_text()
        assert 'source_file="lib/tweak_data/armorskinstweakdata"' in xml
        assert '<hook file="miranda_las.lua"' in xml
        assert '<df_nm path="units/miranda/skins/miranda/miranda_body"/>' in xml
        assert '<texture path="units/miranda/skins/miranda/miranda_eyes"/>' in xml
        assert '<unit_mat path="units/miranda/skins/miranda/miranda"/>' in xml
        assert '<unit_mat path="units/miranda/skins/miranda/fps_miranda"/>' in xml
        assert 'image="guis/dlcs/miranda/armor_skins/miranda"' in xml

    def test_localization_keys(self, pack):
        loc = json.loads((pack / "localization" / "english.txt").read_text())
        assert loc["bm_menu_miranda_armor_skins"] == "Miranda Lawson"
        assert loc["bm_askn_miranda"] == "Miranda Lawson"
        assert "bm_askn_miranda_desc" in loc

    def test_build_info_hashes(self, pack):
        info = json.loads((pack / "BUILD_INFO.json").read_text())
        assert info["models_present"] is False
        assert info["runtime_verified"] is False
        assert info["registration"]["table"] == "LegendaryArmours.miranda"
        digest = hashlib.sha256((pack / "main.xml").read_bytes()).hexdigest()
        assert info["payload_sha256"]["main.xml"] == digest

    def test_build_info_records_template_hashes(self, pack):
        """Build-input hashes must persist in BUILD_INFO (override merge)."""
        import las_pack

        las_pack.refresh_build_info(
            pack, templates={"2b.model": "a" * 64, "fps_2b.model": "b" * 64}
        )
        info = json.loads((pack / "BUILD_INFO.json").read_text())
        assert info["templates"] == {"2b.model": "a" * 64, "fps_2b.model": "b" * 64}
        digest = hashlib.sha256((pack / "main.xml").read_bytes()).hexdigest()
        assert info["payload_sha256"]["main.xml"] == digest

    def test_source_zip_hash_recorded(self):
        """The tracked source inventory describes the source zip that is in the repo.

        It used to read the last build's copy under build/ and skip without one,
        which is every CI run. The record is tracked now, so this always runs.
        """
        import build_las

        inv = json.loads(build_las.RECORD.read_text())
        digest = hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
        assert inv["source_zip"] == SOURCE_ZIP.name
        assert inv["source_zip_sha256"] == digest

    def test_inventory_stage_always_persists(self, tmp_path):
        """--stage inventory must write source_inventory.json (with models),
        not only dump JSON to stdout — otherwise the build leaves no record."""
        import build_las

        rc = build_las.main(["--stage", "inventory", "--out", str(tmp_path)])
        assert rc == 0
        inv = json.loads((tmp_path / "source_inventory.json").read_text())
        assert inv["source_zip_sha256"] == hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
        assert "third_person" in inv["models"]
        assert inv["models"]["third_person"]["triangles"] > 0

    def test_tracked_source_inventory_is_current(self, tmp_path):
        """`tools/pd2-las/source_inventory.json` is what the inventory stage writes today.

        The record is in git so that the source can be read without building: bone
        names, mesh and triangle counts, texture formats. It is only worth reading
        while it is true. If this fails after a change to the source archive or to
        a reader, look at the diff and run `make -sC tools/pd2-las inventory`.
        """
        import build_las

        assert build_las.main(["--stage", "inventory", "--out", str(tmp_path)]) == 0
        fresh = (tmp_path / "source_inventory.json").read_text()
        assert json.loads(fresh) == json.loads(build_las.RECORD.read_text())
        assert fresh == build_las.RECORD.read_text(), "same content, different formatting"

    def test_source_inventory_does_not_depend_on_the_stage(self, tmp_path, monkeypatch):
        """Every stage writes the same record.

        `textures` used to be added by the stages that convert them, so the file
        said more or less depending on the command that ran last, and the quick
        `--stage inventory` replaced a full record with a shorter one. A tracked
        file cannot behave like that: the record now holds source facts only, and
        the hashes of the converted textures go to the pack's BUILD_INFO.json.
        """
        import build_las

        # encoding the eye texture is the slow part of the textures stage and
        # has no bearing on the record
        monkeypatch.setattr(build_las, "eye_texture", lambda: b"DDS stub")
        records = {}
        for stage in ("inventory", "extract", "textures"):
            out = tmp_path / stage
            assert build_las.main(["--stage", stage, "--out", str(out)]) == 0
            records[stage] = (out / "source_inventory.json").read_bytes()
        assert (tmp_path / "textures" / "textures" / "miranda_face_df.texture").is_file()
        assert records["extract"] == records["inventory"]
        assert records["textures"] == records["inventory"]
        record = json.loads(records["inventory"])
        assert sorted(record["textures"]) == sorted(build_las.VTF_TO_PACK)
        for facts in record["textures"].values():
            assert sorted(facts) == ["format", "mips", "pack_texture", "size"], (
                "a build result in the source inventory makes it depend on the stage")

    def test_inventory_stage_prints_only_json(self, tmp_path):
        """`--stage inventory` is for scripts: stdout is one JSON document, the record.

        Two progress lines used to come first, so nothing could parse it.
        """
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(REPO / "tools" / "pd2-las" / "build_las.py"),
             "--stage", "inventory", "--out", str(tmp_path)],
            capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == json.loads((tmp_path / "source_inventory.json").read_text())
        assert "vpk:" in proc.stderr, "the progress lines belong on stderr"

    def test_tracked_pack_embeds_the_tracked_source_inventory(self):
        """BUILD_INFO.json of the tracked pack carries this record plus each texture's hash.

        That ties the three together without building anything: the record in git,
        the record the shipped pack was built from, and the texture files inside it.
        """
        import build_las

        record = json.loads(build_las.RECORD.read_text())
        dist_zip = REPO / "dist" / "Miranda_LAS.zip"
        assert dist_zip.is_file(), f"missing tracked deliverable: {dist_zip}"
        with zipfile.ZipFile(dist_zip) as z:
            embedded = json.loads(z.read("Miranda_LAS/BUILD_INFO.json"))["source_inventory"]
            hashes = {}
            for stem, facts in embedded["textures"].items():
                hashes[stem] = facts.pop("dds_sha256")
                shipped = z.read(f"Miranda_LAS/assets/units/miranda/skins/miranda/{facts['pack_texture']}")
                assert hashlib.sha256(shipped).hexdigest() == hashes[stem], stem
        assert len(hashes) == len(build_las.VTF_TO_PACK)
        assert embedded == record

    def test_material_config_weight_classes(self, pack):
        """Guide contract: contour template + unique on TPP skins, fps depth scaling."""
        tpp_cfg = (
            pack / "assets/units/miranda/skins/miranda/miranda.material_config"
        ).read_text()
        fps_cfg = (
            pack / "assets/units/miranda/skins/miranda/fps_miranda.material_config"
        ).read_text()
        # root header per guide: version="3" + group
        for cfg in (tpp_cfg, fps_cfg):
            assert cfg.startswith('<materials version="3" group="')
        # third-person skins: CONTOUR template, unique="true", contour variables
        for name in ("mtr_body", "mtr_face", "mtr_head", "mtr_hair"):
            assert f'name="{name}" unique="true"' in tpp_cfg, name
        assert tpp_cfg.count(
            'render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"'
        ) == 4
        assert tpp_cfg.count('name="contour_color"') == 4
        assert tpp_cfg.count('name="contour_opacity"') == 4
        # eyes: diffuse-only 3 weights; shadow: 2B contract
        assert 'name="mtr_eyes" render_template="generic:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS"' in tpp_cfg
        assert 'name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT"' in tpp_cfg
        # fps: guide fps example exactly, no contour
        assert (
            'name="mtr_body" render_template="generic:DEPTH_SCALING:DIFFUSE_TEXTURE:'
            'NORMALMAP:SKINNED_3WEIGHTS"' in fps_cfg
        )
        assert "CONTOUR" not in fps_cfg
        # texture paths carry no file extension (guide)
        for cfg in (tpp_cfg, fps_cfg):
            for line in cfg.splitlines():
                if "_texture file=" in line:
                    assert ".texture" not in line and ".dds" not in line, line

    def test_object_xml_lists_only_the_objects_its_model_has(self):
        """A `.object` line with no object behind it is what the busty pack shipped.

        Its first-person model has no head slots and its `.object` listed both,
        because the file was the fixed 2B list. Given the model's drawables the
        writer lists the ones that exist, and nothing but the lines changes.
        """
        import re

        from las_pack import render_object_xml

        def lines(text):
            return re.findall(r'<object name="(\w+)" enabled="(true|false)" />', text)

        base = "units/x/skins/x/fps_x"
        two_b_fps = [("g_body", "true"), ("g_head", "false"),
                     ("g_head_lod1", "false"), ("g_body_lod1", "false")]
        two_b_tpp = [("g_body_lod1", "false"), ("g_body", "true"),
                     ("g_head_lod1", "false"), ("g_head", "true")]
        # no model yet (a scaffold): the 2B list
        assert lines(render_object_xml(base, fps=True)) == two_b_fps
        assert lines(render_object_xml(base, fps=False)) == two_b_tpp
        # a model with all four: the same bytes
        everything = ["c_block", "g_body", "g_body_lod1", "g_head", "g_head_lod1", "s_body"]
        for fps in (False, True):
            assert render_object_xml(base, fps, everything) == render_object_xml(base, fps)
        # a model without the head slots: their lines go, the order and the rest stay
        text = render_object_xml(base, True, ["c_block", "g_body", "g_body_lod1", "s_body"])
        assert lines(text) == [("g_body", "true"), ("g_body_lod1", "false")]
        kept = [line for line in render_object_xml(base, True).splitlines(keepends=True)
                if "g_head" not in line]
        assert text == "".join(kept)
        # a drawable the writer has no line for, or no body at all, is an error
        with pytest.raises(ValueError, match="g_extra"):
            render_object_xml(base, True, ["g_body", "g_extra"])
        with pytest.raises(ValueError, match="g_body"):
            render_object_xml(base, True, ["g_body_lod1", "s_body"])

    @pytest.mark.parametrize("pack_name", ["Miranda_LAS", "Miranda_Busty_LAS"])
    def test_install_models_writes_each_object_from_its_model(self, tmp_path, pack_name):
        """The step both Miranda builders end on, run on the tracked models.

        It needs no templates: the two models come out of the tracked pack, go into
        a fresh scaffold, and the `.object` files that result have to be the tracked
        ones, byte for byte. For the busty pack that is the first-person file with
        no head lines.
        """
        import las_pack

        if pack_name == "Miranda_LAS":
            identity = las_pack.BASE_IDENTITY
        else:
            import build_busty_variant

            identity = build_busty_variant.IDENTITY
        assert identity.pack_dir_name == pack_name
        item = identity.item_id
        unit = f"{pack_name}/assets/{identity.unit_base}"
        models = {}
        with zipfile.ZipFile(REPO / "dist" / f"{pack_name}.zip") as tracked:
            for stem in (item, f"fps_{item}"):
                models[stem] = tmp_path / f"{stem}.model"
                models[stem].write_bytes(tracked.read(f"{unit}/{stem}.model"))
            objects = {stem: tracked.read(f"{unit}/{stem}.object") for stem in models}

        scaffold = las_pack.write_pack(tmp_path / "out", {}, b"DDS icon", {"note": "test"},
                                       models_present=False, identity=identity)
        unit_dir = scaffold / "assets" / identity.unit_base
        assert (scaffold / "WIP_DO_NOT_INSTALL.txt").is_file()
        assert (unit_dir / f"fps_{item}.object").read_text().count("<object ") == 4
        las_pack.install_models(scaffold, models[item], models[f"fps_{item}"], identity)
        assert not (scaffold / "WIP_DO_NOT_INSTALL.txt").exists()
        for stem, path in models.items():
            assert (unit_dir / f"{stem}.model").read_bytes() == path.read_bytes()
            assert (unit_dir / f"{stem}.object").read_bytes() == objects[stem], (
                f"{stem}.object is not the tracked file")
        fps_lines = (unit_dir / f"fps_{item}.object").read_text().count("<object ")
        assert fps_lines == (4 if pack_name == "Miranda_LAS" else 2)

    def test_refresh_build_info_sees_models(self, pack, tmp_path):
        """refresh_build_info flips models_present and re-hashes the tree."""
        import shutil

        from las_pack import refresh_build_info

        clone = tmp_path / "Miranda_LAS"
        shutil.copytree(pack, clone)
        unit = clone / "assets/units/miranda/skins/miranda"
        (unit / "miranda.model").write_bytes(b"fake model")
        (unit / "fps_miranda.model").write_bytes(b"fake fps model")
        (clone / "WIP_DO_NOT_INSTALL.txt").unlink()
        refresh_build_info(clone)
        info = json.loads((clone / "BUILD_INFO.json").read_text())
        assert info["models_present"] is True
        assert "WIP_DO_NOT_INSTALL.txt" not in info["payload_sha256"]
        for rel in (
            "assets/units/miranda/skins/miranda/miranda.model",
            "assets/units/miranda/skins/miranda/fps_miranda.model",
        ):
            digest = hashlib.sha256((clone / rel).read_bytes()).hexdigest()
            assert info["payload_sha256"][rel] == digest

    def test_zip_pack_layout(self, pack, tmp_path):
        import shutil
        import zipfile

        from las_pack import refresh_build_info
        from las_outfit_pack import zip_pack

        clone = tmp_path / "Miranda_LAS"
        shutil.copytree(pack, clone)
        refresh_build_info(clone)
        out = zip_pack(clone)
        assert out.name == "Miranda_LAS.zip"
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        assert "Miranda_LAS/main.xml" in names
        assert "Miranda_LAS/BUILD_INFO.json" in names
        assert all(n.startswith("Miranda_LAS/") for n in names)
        # reproducible: a second pack of identical content is byte-identical
        clone2 = tmp_path / "copy" / "Miranda_LAS"
        clone2.parent.mkdir()
        shutil.copytree(clone, clone2)
        out2 = zip_pack(clone2)
        assert out.read_bytes() == out2.read_bytes()

    def test_reference_archive_untouched(self):
        ref = REPO / "references" / "2b.rar"
        if ref.is_file():
            # 2b.rar is the contract reference; the pipeline must not rewrite it.
            assert zipfile.is_zipfile(ref) is False

    def test_tracked_miranda_las_pack(self):
        """The built Miranda_LAS.zip deliverable is tracked in dist/ and self-consistent."""
        build_zip = REPO / "build" / "pd2-las" / "Miranda_LAS.zip"
        dist_zip = REPO / "dist" / "Miranda_LAS.zip"
        build_sha = REPO / "build" / "pd2-las" / "Miranda_LAS.zip.sha256"
        dist_sha = REPO / "dist" / "Miranda_LAS.zip.sha256"
        for p in (build_zip, dist_zip, build_sha, dist_sha):
            assert p.is_file(), f"missing tracked deliverable: {p}"
        raw = dist_zip.read_bytes()
        assert build_zip.read_bytes() == raw
        digest = hashlib.sha256(raw).hexdigest()
        assert build_sha.read_text().split()[0] == digest
        assert dist_sha.read_text().split()[0] == digest
        with zipfile.ZipFile(dist_zip) as z:
            info = json.loads(z.read("Miranda_LAS/BUILD_INFO.json"))
            assert info["models_present"] is True
            assert "WIP_DO_NOT_INSTALL.txt" not in info["payload_sha256"]
            assert len(info["payload_sha256"]) == 19
            for rel, expected in info["payload_sha256"].items():
                actual = hashlib.sha256(z.read(f"Miranda_LAS/{rel}")).hexdigest()
                assert actual == expected, rel

    def test_tracked_joy_head_replacement_packs(self):
        """Both Joy head-replacement mod_overrides packs in dist/ are tracked and valid."""
        import diesel_model as dm

        for zip_name, prefix in (
            ("Miranda_L4D2_over_Joy.zip", "Miranda L4D2 over Joy"),
            ("Miranda_Romance_over_Joy.zip", "Miranda Romance over Joy"),
        ):
            zp = REPO / "dist" / zip_name
            sp = REPO / "dist" / f"{zip_name}.sha256"
            assert zp.is_file(), f"missing {zp}"
            assert sp.is_file(), f"missing {sp}"
            raw = zp.read_bytes()
            assert sp.read_text().split()[0] == hashlib.sha256(raw).hexdigest()
            unit_dir = f"{prefix}/units/pd2_dlc_joy/characters/npc_criminals_joy_1"
            icon_path = f"{prefix}/guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture"
            with zipfile.ZipFile(zp) as z:
                names = set(z.namelist())
                assert icon_path in names
                assert len(z.read(icon_path)) == 65664
                m_bytes = z.read(f"{unit_dir}/npc_criminal_joy_1.model")
                assert m_bytes == z.read(f"{unit_dir}/npc_criminal_joy_1_menu.model")
                mf = dm.ModelFile.read(m_bytes)
                for did, gid, tid in ((120, 228, 229), (121, 233, 234)):
                    md = dm.decode_model_data(mf.by_id(did).payload)
                    geo = dm.decode_geometry(mf.by_id(gid).payload)
                    topo = dm.decode_topology(mf.by_id(tid).payload)
                    assert len(md["atoms"]) == 2
                    assert geo["vert_count"] > 4000
                    assert len(topo["indices"]) == sum(a["tri_count"] for a in md["atoms"]) * 3

    def test_tracked_clover_bonnie_sydney_head_replacement_packs(self):
        """Clover, Bonnie, and Sydney head-replacement mod_overrides packs in dist/ are tracked and valid."""
        import diesel_model as dm

        specs = [
            (
                "Miranda_L4D2_over_Clover.zip",
                "Miranda L4D2 over Clover",
                "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
                "g_head_fem1",
                "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture",
            ),
            (
                "Miranda_Romance_over_Clover.zip",
                "Miranda Romance over Clover",
                "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
                "g_head_fem1",
                "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture",
            ),
            (
                "Miranda_L4D2_over_Bonnie.zip",
                "Miranda L4D2 over Bonnie",
                "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
                "g_head",
                "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture",
            ),
            (
                "Miranda_Romance_over_Bonnie.zip",
                "Miranda Romance over Bonnie",
                "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
                "g_head",
                "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture",
            ),
            (
                "Miranda_L4D2_over_Sydney.zip",
                "Miranda L4D2 over Sydney",
                "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
                "g_head",
                "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture",
            ),
            (
                "Miranda_Romance_over_Sydney.zip",
                "Miranda Romance over Sydney",
                "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
                "g_head",
                "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture",
            ),
        ]
        for zip_name, prefix, model_rel, head_draw, icon_rel in specs:
            zp = REPO / "dist" / zip_name
            sp = REPO / "dist" / f"{zip_name}.sha256"
            assert zp.is_file(), f"missing {zp}"
            assert sp.is_file(), f"missing {sp}"
            raw = zp.read_bytes()
            assert sp.read_text().split()[0] == hashlib.sha256(raw).hexdigest()
            with zipfile.ZipFile(zp) as z:
                names = set(z.namelist())
                assert f"{prefix}/{icon_rel}" in names
                assert len(z.read(f"{prefix}/{icon_rel}")) == 65664
                mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
                md_by_hash = {
                    dm.decode_model_data(s.payload)["name_hash"]: s
                    for s in mf.by_type(dm.MODEL_DATA)
                }
                md = dm.decode_model_data(md_by_hash[dm.hash64(head_draw)].payload)
                pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
                topo = dm.decode_topology(mf.by_id(pg["topology"]).payload)
                mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
                sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
                assert len(md["atoms"]) == 2
                assert len(mg["material_ids"]) == 2
                assert len(sb["maps"]) == 3
                assert geo["vert_count"] > 4000
                assert len(topo["indices"]) == sum(a["tri_count"] for a in md["atoms"]) * 3

    def test_neck_skirt_is_on_the_l4d2_heads_and_not_on_the_romance_ones(self):
        """The skirt is a L4D2-path change; the Romance path must not carry it.

        On the Romance rig the neck skin is part of the "Hair" mesh, together
        with the hair cap and the 1.5 mm flyaway wire strips, so the rim filter
        catches 741 hair-sheet edges instead of the neck's ~145. The wire pass
        that follows then squashes the new ring into the head (it is not in
        `best_comp`): +340 verts at z 168-170 and 2,318 triangles, where the
        L4D2 packs get +113 verts at z 143 and 212 triangles. That shipped once
        - the previews showed a pale lump under the chin - so the counts and the
        lowest vertex are pinned here. Diagnosis §10.3.
        """
        import numpy as np

        import neck_junction as nj

        specs = [
            ("Miranda_L4D2_over_Joy.zip", 4515, 7321, 142.98),
            ("Miranda_L4D2_over_Clover.zip", 4508, 7305, 142.98),
            ("Miranda_L4D2_over_Bonnie.zip", 4508, 7305, 142.98),
            ("Miranda_L4D2_over_Sydney.zip", 4508, 7305, 142.98),
            ("Miranda_Romance_over_Joy.zip", 4454, 7070, 148.90),
            ("Miranda_Romance_over_Clover.zip", 4454, 7070, 148.90),
            ("Miranda_Romance_over_Bonnie.zip", 4454, 7070, 148.90),
            ("Miranda_Romance_over_Sydney.zip", 4454, 7070, 148.90),
        ]
        for name, verts, tris, min_z in specs:
            zp = REPO / "dist" / name
            assert zp.is_file(), f"missing {zp}"
            v, f = nj._head_mesh(zp)
            assert len(v) == verts, f"{name}: {len(v)} verts, expected {verts}"
            assert len(f) == tris, f"{name}: {len(f)} tris, expected {tris}"
            assert float(np.min(v[:, 2])) == pytest.approx(min_z, abs=0.1), (
                f"{name}: lowest head vertex z {np.min(v[:, 2]):.2f}, expected {min_z} "
                f"- a Romance head below 148.9 means its skirt was squashed into the head"
            )

    def test_tracked_pack_specular_alpha_and_pd2_normal_layout(self):
        """Diffuse alpha carries attenuated specular (< 80) and normal maps use PD2 layout."""
        import numpy as np

        build_zip = REPO / "build" / "pd2-las" / "Miranda_LAS.zip"
        with zipfile.ZipFile(build_zip) as z:
            for stem in ("miranda_body_df", "miranda_face_df", "miranda_head_df", "miranda_eyes"):
                raw = z.read(f"Miranda_LAS/assets/units/miranda/skins/miranda/{stem}.texture")
                blocks = np.frombuffer(raw[128:], dtype=np.uint8).reshape(-1, 16)
                assert int(blocks[:, 0].max()) <= 72, f"{stem} alpha too glossy: {blocks[:, 0].max()}"
                assert float(blocks[:, 0].mean()) < 35.0, f"{stem} mean alpha too high"
            for stem in ("miranda_body_nm", "miranda_face_nm", "miranda_head_nm"):
                raw = z.read(f"Miranda_LAS/assets/units/miranda/skins/miranda/{stem}.texture")
                blocks = np.frombuffer(raw[128:], dtype=np.uint8).reshape(-1, 16)
                c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
                c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
                assert np.all(((c0 >> 11) & 31) == 31), f"{stem} red channel not 255"
                assert np.all((c0 & 31) == 0), f"{stem} blue channel not 0"
                assert np.all(c0 >= c1), f"{stem} has c0 < c1"
                assert int(blocks[:, 0].max()) - int(blocks[:, 1].min()) > 16, f"{stem} alpha flat"

    def test_l4d2_head_diffuse_alpha_follows_the_las_face(self):
        """The four L4D2 head packs build `*_head_df.texture` from dist/Miranda_LAS.zip's face diffuse:
        face-quadrant alpha = min(source alpha, 18), i.e. an attenuated specular mask (PD2 reads diffuse
        alpha as specular). The packs once shipped a *scrambled* alpha plane (a face quadrant whose values
        had the right distribution but no spatial relation to the source: correlation +0.03), because they
        had been built against an older LAS zip and never rebuilt. Guard the correlation, not the bytes."""
        import io

        import numpy as np
        from PIL import Image

        with zipfile.ZipFile(REPO / "dist" / "Miranda_LAS.zip") as z:
            face = np.asarray(
                Image.open(
                    io.BytesIO(
                        z.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_df.texture")
                    )
                ).convert("RGBA")
            )
        expected = np.minimum(face[..., 3].astype(np.float32), 18.0)

        specs = [
            ("Miranda_L4D2_over_Joy.zip", "Miranda L4D2 over Joy", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_df.texture"),
            ("Miranda_L4D2_over_Clover.zip", "Miranda L4D2 over Clover", "units/payday2/characters/shared_textures/clover_head_df.texture"),
            ("Miranda_L4D2_over_Bonnie.zip", "Miranda L4D2 over Bonnie", "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie_head_df.texture"),
            ("Miranda_L4D2_over_Sydney.zip", "Miranda L4D2 over Sydney", "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_head_df.texture"),
        ]
        for zip_name, prefix, df_rel in specs:
            with zipfile.ZipFile(REPO / "dist" / zip_name) as z:
                head = np.asarray(Image.open(io.BytesIO(z.read(f"{prefix}/{df_rel}"))).convert("RGBA"))
            got = head[0:1024, 0:1024, 3].astype(np.float32)
            corr = float(np.corrcoef(got.ravel(), expected.ravel())[0, 1])
            assert corr > 0.99, f"{zip_name}: face-quadrant alpha is not the LAS face gloss (corr {corr:+.3f})"
            assert got.max() <= 18.0, f"{zip_name}: face-quadrant alpha not attenuated (max {got.max():.0f})"

    def test_ingame_visual_artifact_regressions(self):
        """Guard against the 5 in-game visual artifacts:
        1. Corrupted right-cheek/mouth-corner skin boundary normals.
        2. Non-orthogonal or un-welded tangent basis vectors (uvdir_u, uvdir_v).
        3. Duplicate eyeball triangles in Atom 1 (causing Z-fighting black eyes).
        4. Untinted white / slit eyeballs in head_df quadrant (1, 1).
        5. Lower front hair poking through the front throat skin (z < 161.5).
        """
        import io
        import numpy as np
        from PIL import Image
        import diesel_model as dm

        specs = [
            ("Miranda_L4D2_over_Joy.zip", "Miranda L4D2 over Joy", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_df.texture", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_nm.texture", "g_head"),
            ("Miranda_Romance_over_Joy.zip", "Miranda Romance over Joy", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_df.texture", "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_nm.texture", "g_head"),
            ("Miranda_L4D2_over_Clover.zip", "Miranda L4D2 over Clover", "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model", "units/payday2/characters/shared_textures/clover_head_df.texture", "units/payday2/characters/shared_textures/clover_head_nm.texture", "g_head_fem1"),
            ("Miranda_Romance_over_Clover.zip", "Miranda Romance over Clover", "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model", "units/payday2/characters/shared_textures/clover_head_df.texture", "units/payday2/characters/shared_textures/clover_head_nm.texture", "g_head_fem1"),
        ]
        for zip_name, prefix, model_rel, df_rel, nm_rel, head_draw in specs:
            with zipfile.ZipFile(REPO / "dist" / zip_name) as z:
                mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
                md_by_hash = {
                    dm.decode_model_data(s.payload)["name_hash"]: s
                    for s in mf.by_type(dm.MODEL_DATA)
                }
                md = dm.decode_model_data(md_by_hash[dm.hash64(head_draw)].payload)
                pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
                a0, a1 = md["atoms"][0], md["atoms"][1]
                # 1. Atom 1 is 3D eyelashes only (never duplicated eyeballs)
                assert a1["tri_count"] == 224, f"{zip_name}: expected 224 eyelash tris in Atom 1, got {a1['tri_count']}"
                # 2. Orthonormal tangent basis
                nrm = np.asarray(geo["normals"], dtype=np.float64)
                tu = np.asarray(geo["uvdir_u"], dtype=np.float64)
                tv = np.asarray(geo["uvdir_v"], dtype=np.float64)
                assert float(np.abs(np.sum(nrm * tu, axis=1)).max()) < 1e-4
                assert float(np.abs(np.sum(nrm * tv, axis=1)).max()) < 1e-4
                # 3. Lower front hair (z < 161.5) stays strictly behind front throat skin
                p0 = np.asarray(geo["verts"], dtype=np.float64)[: a0["slice_len"]]
                uv0 = np.asarray(geo["uv0"], dtype=np.float64)[: a0["slice_len"]]
                uv_img_y = 1.0 - uv0[:, 1]
                # Hair in quadrant (1, 0) has u in [0.5, 1.0], v_img in [0.0, 0.5] with local v_img <= 0.41
                is_hair = (uv0[:, 0] > 0.5) & (uv_img_y < 0.41)
                low_hair = is_hair & (p0[:, 2] < 161.5)
                assert float(p0[low_hair, 1].max()) < 5.0, f"{zip_name}: low hair pokes forward to y={p0[low_hair, 1].max():.2f}"
                # 4. Crisp sapphire iris in quadrant (1, 1) of head_df
                df_im = np.asarray(Image.open(io.BytesIO(z.read(f"{prefix}/{df_rel}"))).convert("RGBA"))
                eye_quad = df_im[1024:2048, 1024:2048]
                yy, xx = np.mgrid[0:1024, 0:1024].astype(np.float32)
                r = np.hypot((xx - 511.5) / 1024.0, (yy - 511.5) / 1024.0)
                iris_ring = (r > 0.11) & (r < 0.21)
                mean_r = float(eye_quad[iris_ring, 0].mean())
                mean_b = float(eye_quad[iris_ring, 2].mean())
                assert mean_b > mean_r + 40.0, f"{zip_name}: eye iris not sapphire blue (R={mean_r:.1f}, B={mean_b:.1f})"
                upper_iris = iris_ring & (yy < 512)
                lower_iris = iris_ring & (yy >= 512)
                assert abs(float(eye_quad[upper_iris, 2].mean()) - float(eye_quad[lower_iris, 2].mean())) < 25.0, (
                    f"{zip_name}: top/bottom iris asymmetry detected"
                )
                assert float(eye_quad[r > 0.32, 0].mean()) < 185.0, f"{zip_name}: sclera too bright (bloom risk)"
                # 5. PD2 DXT5nm normal map layout in head_nm
                nm_raw = z.read(f"{prefix}/{nm_rel}")
                nm_blocks = np.frombuffer(nm_raw[128:], dtype=np.uint8).reshape(-1, 16)
                c0 = nm_blocks[:, 8].astype(np.int32) | (nm_blocks[:, 9].astype(np.int32) << 8)
                assert np.all(((c0 >> 11) & 31) == 31), f"{zip_name}: head_nm red channel not 255"
                assert np.all((c0 & 31) == 0), f"{zip_name}: head_nm blue channel not 0"

        # 6. Verify lawson_las.zip has unified bone weights and welded normals across the Face <-> Hair under-chin seam
        sys.path.insert(0, str(REPO / "tools" / "pd2-port"))
        import dmodel

        with zipfile.ZipFile(REPO / "dist" / "lawson_las.zip") as z:
            m_tpp = dmodel.DieselModel.from_bytes(z.read("Lawson_LAS/assets/units/lawson/skins/lawson/lawson.model"))
            md_h = m_tpp.by_id[75].obj
            geo_h = m_tpp.by_id[82].obj
            topo_h = np.asarray(m_tpp.by_id[83].obj.faces, dtype=np.int32)
            a_face, a_hair = md_h.render_atoms[0], md_h.render_atoms[1]
            s0 = np.unique(topo_h[a_face["base_index"] // 3 : a_face["base_index"] // 3 + a_face["tri_count"]])
            s1 = np.unique(topo_h[a_hair["base_index"] // 3 : a_hair["base_index"] // 3 + a_hair["tri_count"]])
            v0 = np.asarray(geo_h.positions, dtype=np.float64)[s0]
            v1 = np.asarray(geo_h.positions, dtype=np.float64)[s1]
            n0 = np.asarray(geo_h.normals, dtype=np.float64)[s0]
            n1 = np.asarray(geo_h.normals, dtype=np.float64)[s1]
            w0 = np.asarray(geo_h.weights3, dtype=np.float64)[s0]
            w1 = np.asarray(geo_h.weights3, dtype=np.float64)[s1]
            bi0 = np.asarray(geo_h.joints, dtype=np.int32)[s0]
            bi1 = np.asarray(geo_h.joints, dtype=np.int32)[s1]
            k0 = {tuple( row ): idx for idx, row in enumerate(np.round(v0, 3))}
            ii, jj = [], []
            for idx1, row1 in enumerate(np.round(v1, 3)):
                idx0 = k0.get(tuple(row1))
                if idx0 is not None:
                    ii.append(idx0)
                    jj.append(idx1)
            assert len(ii) >= 100
            assert np.array_equal(bi0[ii], bi1[jj]), "Face <-> Hair seam has bone index mismatch"
            assert float(np.abs(w0[ii] - w1[jj]).max()) < 1e-5, "Face <-> Hair seam has bone weight mismatch"
            chin = v0[ii, 2] < 160.0
            assert int(chin.sum()) >= 15
            assert float(np.abs(n0[ii][chin] - n1[jj][chin]).max()) < 1e-5, "Under-chin seam has normal mismatch"

    def test_geralt_over_rust_package(self):
        """Verify dist/Geralt_over_Rust.zip geometry, CCW winding, single-atom ALPHA_MASKED mtr_head, textures, and preview."""
        import io
        import diesel_model as dm
        import numpy as np
        from PIL import Image

        zp = REPO / "dist" / "Geralt_over_Rust.zip"
        sp = REPO / "dist" / "Geralt_over_Rust.zip.sha256"
        assert zp.is_file() and sp.is_file()
        assert sp.read_text().split()[0] == hashlib.sha256(zp.read_bytes()).hexdigest()

        prefix = "Geralt over Rust"
        wild_dir = f"{prefix}/units/pd2_dlc_wild/characters/npc_criminals_wild_1"
        with zipfile.ZipFile(zp) as z:
            names = set(z.namelist())
            assert f"{prefix}/guis/dlcs/wild/textures/pd2/blackmarket/icons/characters/wild.texture" in names
            assert f"{wild_dir}/npc_criminal_wild_1.model" in names
            assert f"{wild_dir}/npc_criminal_wild_1_menu.model" in names

            mf = dm.ModelFile.read(z.read(f"{wild_dir}/npc_criminal_wild_1.model"))
            mat_by_hash = {
                dm.decode_material(s.payload)["name_hash"]: s.id
                for s in mf.by_type(dm.MATERIAL)
            }
            assert dm.hash64("mtr_head") in mat_by_hash

            md_by_hash = {
                dm.decode_model_data(s.payload)["name_hash"]: s
                for s in mf.by_type(dm.MODEL_DATA)
            }
            md = dm.decode_model_data(md_by_hash[dm.hash64("g_head")].payload)
            assert len(md["atoms"]) == 1
            mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
            assert mg["material_ids"] == [mat_by_hash[dm.hash64("mtr_head")]]

            pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
            topo = np.asarray(dm.decode_topology(mf.by_id(pg["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
            verts = np.asarray(geo["verts"], dtype=np.float64)
            nrm = np.asarray(geo["normals"], dtype=np.float64)
            uv0 = np.asarray(geo["uv0"], dtype=np.float64)
            tu = np.asarray(geo["uvdir_u"], dtype=np.float64)
            tv = np.asarray(geo["uvdir_v"], dtype=np.float64)
            assert float(np.abs(np.sum(nrm * tu, axis=1)).max()) < 1e-4
            assert float(np.abs(np.sum(nrm * tv, axis=1)).max()) < 1e-4

            # Verify 100% CCW triangle winding on opaque head/eyes/teeth (uv_diesel.y >= 0.5)
            opaque_tri_mask = uv0[topo[:, 0], 1] >= 0.5
            t_op = topo[opaque_tri_mask]
            fn = np.cross(verts[t_op[:, 1]] - verts[t_op[:, 0]], verts[t_op[:, 2]] - verts[t_op[:, 0]])
            vn = nrm[t_op[:, 0]] + nrm[t_op[:, 1]] + nrm[t_op[:, 2]]
            dot = np.sum(fn * vn, axis=1)
            assert float((dot > 0).mean()) > 0.999, "Head triangles must have CCW outward winding"

            # Verify double-sided hair/beard/eyelash cards (uv_diesel.y < 0.5): equal + and - winding counts
            cut_tri_mask = uv0[topo[:, 0], 1] < 0.5
            t_cut = topo[cut_tri_mask]
            fn_c = np.cross(verts[t_cut[:, 1]] - verts[t_cut[:, 0]], verts[t_cut[:, 2]] - verts[t_cut[:, 0]])
            vn_c = nrm[t_cut[:, 0]] + nrm[t_cut[:, 1]] + nrm[t_cut[:, 2]]
            dot_c = np.sum(fn_c * vn_c, axis=1)
            assert int((dot_c > 0).sum()) == int((dot_c < 0).sum())

            low_front = (verts[:, 2] < 157.5) & (verts[:, 1] > 5.0)
            assert float(verts[low_front, 1].max()) <= 10.36

            for mcfg in (
                f"{wild_dir}/mtr_criminal_wild_1.material_config",
                f"{wild_dir}/mtr_criminal_wild_1_cc.material_config",
                f"{prefix}/units/pd2_dlc_chill/characters/shared_character/mtr_criminal_wild_1.material_config",
            ):
                txt = z.read(mcfg).decode("utf-8")
                assert 'name="mtr_head"' in txt
                assert 'ALPHA_MASKED' in txt
                assert 'value="0.05"' in txt
                assert 'npc_criminal_wild_1_head_df' in txt

            for tex_name in (
                "npc_criminal_wild_1_head_df.texture",
                "npc_criminal_wild_1_head_nm.texture",
            ):
                raw = z.read(f"{wild_dir}/{tex_name}")
                assert raw[:4] == b"DDS "
                im = Image.open(io.BytesIO(raw))
                assert im.size == (2048, 2048)

            df_arr = np.asarray(
                Image.open(io.BytesIO(z.read(f"{wild_dir}/npc_criminal_wild_1_head_df.texture"))).convert("RGBA")
            )
            assert np.all(
                (df_arr[0:1024, 0:1536, 3] >= 16) & (df_arr[0:1024, 0:1536, 3] <= 32)
            ), "Top half of head_df must be 100% opaque (>13) with low natural specular (<=32)"
            hair_tile = df_arr[1024:2048, 0:1024]
            assert int(hair_tile[:, :, 3].max()) <= 26, "Hair cutout alpha must keep low specular (<=26)"
            hair_sat = hair_tile[:, :, :3].max(axis=2).astype(int) - hair_tile[:, :, :3].min(axis=2).astype(int)
            assert int(hair_sat.max()) <= 30, f"Unexpected color saturation artifact in hair_d tile: {hair_sat.max()}"

            # Verify coverage-preserving mipmaps keep beard_d visible across mip 0..3
            sys.path.insert(0, str(REPO / "tools" / "pd2-port"))
            import dds as pd2_dds

            raw_df = z.read(f"{wild_dir}/npc_criminal_wild_1_head_df.texture")
            off_mip = 128
            for mip_i in range(4):
                mw = 2048 >> mip_i
                mh = 2048 >> mip_i
                msz = (mw // 4) * (mh // 4) * 16
                dec_mip = pd2_dds.decode_dxt5(raw_df[off_mip : off_mip + msz], mw, mh)
                off_mip += msz
                beard_mip = dec_mip[mh // 2 : (mh * 5) // 8, (mw * 7) // 8 : mw]
                surv = float((beard_mip[:, :, 3] > 13).mean())
                assert surv >= 0.22, f"Beard mip {mip_i} alpha survival dropped too low: {surv:.3f}"

            # Verify side neck skin stays strictly inside side hair curtain (no poking through below ears)
            is_head_v = (uv0[:, 0] < 0.5) & (uv0[:, 1] >= 0.5)
            is_hair_v = (uv0[:, 0] < 0.5) & (uv0[:, 1] < 0.5)
            neck_band = is_head_v & (verts[:, 2] >= 160.0) & (verts[:, 2] < 164.0) & (verts[:, 1] >= -2.0) & (verts[:, 1] <= 5.0)
            hair_band = is_hair_v & (verts[:, 2] >= 160.0) & (verts[:, 2] < 164.0) & (verts[:, 1] >= -2.0) & (verts[:, 1] <= 5.0)
            assert float(np.abs(verts[neck_band, 0]).max()) + 0.5 < float(np.abs(verts[hair_band, 0]).min())

        prev = REPO / "docs" / "previews" / "11_Geralt_over_Rust.png"
        assert prev.is_file()
        with Image.open(prev) as pim:
            assert pim.size == (1440, 538)

    def test_miranda_nostril_shadow_and_upper_lash_liner(self):
        """Regression check: inner nostrils are dark + low-specular across all Miranda packs, and Miranda_LAS has upper lash liner."""
        import io
        import numpy as np
        from PIL import Image

        for zip_name, tex_suffix, uv_scale in (
            ("lawson_las.zip", "/face_df.texture", 1.0),
            ("Miranda_LAS.zip", "/miranda_face_df.texture", 1.0),
            ("Miranda_L4D2_over_Joy.zip", "/npc_criminal_joy_1_head_df.texture", 0.5),
            ("Miranda_Romance_over_Joy.zip", "/npc_criminal_joy_1_head_df.texture", 0.5),
        ):
            zp = REPO / "dist" / zip_name
            if not zp.is_file():
                pytest.skip(f"{zip_name} not built")
            with zipfile.ZipFile(zp) as z:
                entry = next(n for n in z.namelist() if n.endswith(tex_suffix))
                arr = np.asarray(Image.open(io.BytesIO(z.read(entry))).convert("RGBA"))
            H, W = arr.shape[:2]
            for uc, vc in ((0.454 * uv_scale, 0.472 * uv_scale), (0.559 * uv_scale, 0.472 * uv_scale)):
                px, py = int(uc * W), int(vc * H)
                patch = arr[py - 3 : py + 4, px - 3 : px + 4]
                assert float(patch[:, :, :3].mean()) < 40.0, f"{zip_name}: nostril RGB too bright ({patch[:, :, :3].mean():.1f})"
                assert int(patch[:, :, 3].max()) <= 5, f"{zip_name}: nostril specular alpha too high ({patch[:, :, 3].max()})"
            for uc, vc in ((0.260 * uv_scale, 0.293 * uv_scale), (0.747 * uv_scale, 0.293 * uv_scale)):
                px, py = int(uc * W), int(vc * H)
                if zip_name != "lawson_las.zip":
                    lash_patch = arr[py - 2 : py + 3, px - 4 : px + 5, :3]
                    assert float(lash_patch.mean()) < 48.0, f"{zip_name}: upper lash liner missing ({lash_patch.mean():.1f})"


def test_our_packs_have_an_orthonormal_tangent_basis():
    """N.U, N.V *and* U.V must all be zero; U and V must be unit length.

    The existing assertions in test_ingame_visual_artifact_regressions only
    cover N.U and N.V, which a plain projection satisfies exactly - that is how
    a 5-20 degree shear shipped in every pack this repo builds. U.V is the
    missing gate, and it is checked here on the packs this repo actually builds
    (the Miranda packs, TPP and FPS).
    """
    import zipfile

    import numpy as np

    import diesel_model as dm

    specs = [
        ("Miranda_LAS.zip", "Miranda_LAS",
         "assets/units/miranda/skins/miranda/miranda.model"),
        ("Miranda_LAS.zip", "Miranda_LAS",
         "assets/units/miranda/skins/miranda/fps_miranda.model"),
        ("Miranda_Busty_LAS.zip", "Miranda_Busty_LAS",
         "assets/units/miranda_busty/skins/miranda_busty/miranda_busty.model"),
        ("Miranda_Busty_LAS.zip", "Miranda_Busty_LAS",
         "assets/units/miranda_busty/skins/miranda_busty/fps_miranda_busty.model"),
    ]
    for zip_name, prefix, model_rel in specs:
        zp = REPO / "dist" / zip_name
        if not zp.is_file():
            pytest.skip(f"{zip_name} not built")
        with zipfile.ZipFile(zp) as z:
            mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
        for si, sec in enumerate(mf.by_type(dm.GEOMETRY)):
            geo = dm.decode_geometry(sec.payload)
            n = np.asarray(geo["normals"], dtype=np.float64)
            u = np.asarray(geo["uvdir_u"], dtype=np.float64)
            v = np.asarray(geo["uvdir_v"], dtype=np.float64)
            tag = f"{zip_name}:{model_rel}[{si}]"
            assert np.abs(np.linalg.norm(u, axis=1) - 1.0).max() < 1e-4, \
                f"{tag}: U not unit"
            assert np.abs(np.linalg.norm(v, axis=1) - 1.0).max() < 1e-4, \
                f"{tag}: V not unit"
            assert np.abs((n * u).sum(1)).max() < 1e-4, f"{tag}: N.U"
            assert np.abs((n * v).sum(1)).max() < 1e-4, f"{tag}: N.V"
            assert np.abs((u * v).sum(1)).max() < 1e-4, \
                f"{tag}: U.V  <- the missing gate"





