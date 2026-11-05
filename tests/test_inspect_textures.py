"""The texture side of an addon: every material resolved, and every VTF decoded.

`inspect_gma.py` reports a model's geometry and rig. This covers the failure
mode that costs the most time after that: a bodygroup whose material is missing,
or a VTF that parses but decodes to black. Tests here build small archives of
each kind and pin the answers, including the two things a naive resolver gets
wrong — `EyeRefract` materials name their colour map `$iris`, and a compiled
MDL always names a `phy` "material" that is not drawable.
"""
from __future__ import annotations

import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

import inspect_textures as itx  # noqa: E402
from test_gma import build_gma  # noqa: E402


# --------------------------------------------------------------------- VTF

def _vtf(width=8, height=8, mips=4) -> bytes:
    """A minimal VTF 7.4 holding one uncompressed BGRA8888 mip chain.

    DXT would be more realistic but needs a block encoder; the header layout and
    resource-table position are what the reader is being tested on, and
    uncompressed mips let the expected pixels be stated exactly.
    """
    header_size = 88            # 80-byte header + one resource entry (IMAGE)
    data = bytearray(header_size)
    data[0:4] = b"VTF\x00"
    struct.pack_into("<II", data, 4, 7, 4)          # version 7.4
    struct.pack_into("<I", data, 12, header_size)
    struct.pack_into("<HH", data, 16, width, height)
    struct.pack_into("<I", data, 20, 0x0004)        # flags: 8-bit alpha
    struct.pack_into("<HH", data, 24, 1, 0)         # frames, first frame
    struct.pack_into("<f", data, 48, 1.0)           # bumpmap scale
    struct.pack_into("<I", data, 52, 12)            # RGBA8888... see note below
    data[56] = mips
    struct.pack_into("<I", data, 57, 0xFFFFFFFF)    # low-res format: none
    data[61] = data[62] = 0                          # low-res size: none
    struct.pack_into("<H", data, 63, 1)              # depth
    # resource dictionary: one IMAGE entry (tag 0x30) pointing past the header
    data[80:83] = (0x30).to_bytes(3, "little")
    data[83] = 0
    struct.pack_into("<I", data, 84, header_size)
    for _ in range(mips):
        for y in range(height):
            for x in range(width):
                # B, G, R, A - a recognisable ramp in R so a decode is provable
                data += bytes((0, 0, (x * 31) % 256, 255))
        width, height = max(1, width // 2), max(1, height // 2)
    return bytes(data)


def _png(data: bytes) -> bytes:
    import vtf as vtfmod

    return vtfmod.to_png(vtfmod.parse_vtf(data))


def test_the_fixture_vtf_decodes_to_a_png():
    png = _png(_vtf())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_truncated_vtf_is_reported_not_crashed():
    broken = _vtf()[:-16]
    report = itx._decodes(broken)
    assert report is False


# ------------------------------------------------------------------ VMT text

def test_basetexture_is_found_inside_a_patch_block():
    text = b'patch { insert { $baseTexture "models\\miranda\\miranda_body_color" } }'.decode()
    assert itx.parse_basetexture(text) == "models/miranda/miranda_body_color"


def test_an_eye_material_resolves_through_iris():
    text = 'EyeRefract\r\n{\r\n$Iris "models/miranda/miranda_eyes"\r\n}'
    assert itx.parse_basetexture(text) == "models/miranda/miranda_eyes"


def test_every_texture_reference_is_collected_but_engine_paths_are_dropped():
    text = (
        '$basetexture "models/x/body_color"\n'
        '$bumpmap "models/x/body_normal"\n'
        '$envmap "Engine/eye-reflection-cubemap-"\n'
    )
    refs = itx.parse_texture_refs(text)
    assert "models/x/body_color" in refs
    assert "models/x/body_normal" in refs
    assert not any("engine/" in r.lower() for r in refs)


# --------------------------------------------------------------- containers

def _container(tmp_path: Path, files: dict[str, bytes]):
    gma = build_gma(files, title="texture fixture")
    path = tmp_path / "fixture.gma"
    path.write_bytes(gma)
    return itx.open_container(path)


VMT_BODY = b'patch { insert { $baseTexture "models/x/body_color" } }'


def test_a_textured_material_resolves_to_its_vtf(tmp_path):
    c = _container(tmp_path, {
        "materials/models/x/body.vmt": VMT_BODY,
        "materials/models/x/body_color.vtf": _vtf(),
    })
    rep = itx.resolve_texture(c, "materials/models/x/body.vmt")
    assert rep.present and rep.decodes
    assert rep.vtf_path == "materials/models/x/body_color.vtf"
    assert (rep.width, rep.height) == (8, 8)


def test_a_missing_texture_is_absent_not_an_exception(tmp_path):
    c = _container(tmp_path, {"materials/models/x/body.vmt": VMT_BODY})
    rep = itx.resolve_texture(c, "materials/models/x/body.vmt")
    assert not rep.present
    assert rep.vtf_path is None


def test_a_vmt_without_any_texture_key_says_so(tmp_path):
    c = _container(tmp_path, {"materials/models/x/plain.vmt": b'"VertexLitGeneric" {}'})
    rep = itx.resolve_texture(c, "materials/models/x/plain.vmt")
    assert rep.basetexture is None
    assert rep.error == "no $basetexture"


def test_the_engine_only_phy_material_is_not_a_missing_texture(tmp_path):
    """Every compiled MDL names `phy`; reporting it would cry wolf on all of them."""
    assert "phy" in itx._ENGINE_ONLY


def test_zip_with_one_gma_inside_is_opened_without_unpacking(tmp_path):
    gma = build_gma({"materials/models/x/body.vmt": VMT_BODY}, title="nested")
    zpath = tmp_path / "addon.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("addon.gma", gma)
        zf.writestr("readme.txt", "hi")
    c = itx.open_container(zpath)
    assert c.has("materials/models/x/body.vmt")
    assert c.read("materials/models/x/body.vmt") == VMT_BODY
    assert c.name.endswith("addon.gma")


SOURCE_PACK = (
    Path(__file__).resolve().parents[1] / "models" / "l4d2_miranda_lawson_1.zip"
)


@pytest.mark.skipif(not SOURCE_PACK.exists(), reason="tracked L4D2 pack is absent")
def test_sourcepp_agrees_on_a_real_vtf_from_the_tracked_pack():
    """Two independent decoders agreeing is the cheap proof either is right.

    The real texture also pins the important negative: the cross-check must
    return ``True`` here, so a later change that breaks the optional import
    cannot silently turn into "disagrees" everywhere.
    """
    pytest.importorskip("sourcepp", reason="sourcepp is an optional extra")
    import vtf as vtfmod
    from vpk import VpkArchive

    arc = VpkArchive.from_zip(str(SOURCE_PACK), "miranda_rochelle.vpk")
    raw = arc.read("materials/models/miranda/miranda_body_color.vtf")
    assert itx._sourcepp_check(raw, vtfmod.parse_vtf(raw)) is True


def test_sourcepp_cross_check_never_raises():
    """Absent, broken or disagreeing, the check reports rather than explodes."""
    import vtf as vtfmod

    raw = _vtf()
    assert itx._sourcepp_check(raw, vtfmod.parse_vtf(raw)) in (True, False, None)
    assert itx._sourcepp_check(b"not a vtf", vtfmod.parse_vtf(raw)) in (False, None)


def test_a_bad_archive_extension_is_refused(tmp_path):
    p = tmp_path / "addon.rar"
    p.write_bytes(b"Rar!")
    with pytest.raises(ValueError):
        itx.open_container(p)


def test_crc_of_the_fixture_archive_is_valid():
    """Guard the fixture builder itself: a bad CRC would make every test lie."""
    blob = build_gma({"a/x.vmt": VMT_BODY})
    assert zlib.crc32(VMT_BODY) & 0xFFFFFFFF == struct.unpack_from(
        "<I", blob, blob.index(b"a/x.vmt\0") + len("a/x.vmt\0") + 8
    )[0]
