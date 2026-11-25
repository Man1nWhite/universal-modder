"""Property probes for malformed bytes at binary/text reader boundaries."""
from __future__ import annotations

import struct
import sys
import zipfile
import zlib

import pytest
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / "pd2-las"), str(ROOT / "tests")]

import dds_encode  # noqa: E402
import diesel_model as dm  # noqa: E402
import gma  # noqa: E402
import smd  # noqa: E402
import vpk  # noqa: E402
import vtf  # noqa: E402
from extract_2b import MISSING, TEMPLATE_FILES, TEMPLATES  # noqa: E402
import wwise_ima  # noqa: E402
from test_gma import FILES as GMA_FILES, build_gma  # noqa: E402
from test_inspect_textures import _vtf  # noqa: E402
from test_smd import HAND_WRITTEN  # noqa: E402


GMA_BLOB = build_gma(GMA_FILES)
def _fixture_vpk() -> bytes:
    payload = (ROOT / "tests/fixtures/las_loader_4.1.9.lua").read_bytes()
    name = b"las_loader_4.1.9"
    tree = (b"lua\0 \0" + name + b"\0"
            + struct.pack("<IHHIIH", zlib.crc32(payload), 0, vpk.INLINE_ARCHIVE,
                          0, len(payload), 0xFFFF)
            + b"\0\0\0")
    return struct.pack("<III", vpk.VPK_SIGNATURE, 1, len(tree)) + tree + payload


VPK_BLOB = _fixture_vpk()
VTF_BLOB = _vtf()
SMD_BLOB = HAND_WRITTEN.encode("utf-8")
WWISE_BLOB = wwise_ima.header(1, 36) + bytes(36)
def _tracked_model() -> bytes:
    for archive in sorted((ROOT / "dist").rglob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            member = next((name for name in zf.namelist() if name.endswith(".model")), None)
            if member:
                return zf.read(member)
    raise RuntimeError("no tracked pack contains a .model fixture")


MODEL_BLOB = _tracked_model()
DDS_BLOB = dds_encode._dds_header(4, 4, b"DXT5") + bytes(16)


def _damaged(blob: bytes, cut: int, flip: int) -> bytes:
    # Corrupt a format discriminator so each generated sample is malformed,
    # rather than occasionally mutating payload data into another valid file.
    # SMD has no strict file header; damage a vertex's required integer field.
    if b"\ntriangles\n" in blob:
        data = bytearray(blob)
        section = data.index(b"\ntriangles\n") + len(b"\ntriangles\n")
        material_end = data.index(b"\n", section) + 1
        data[material_end] = ord("x")
        if material_end + 1 < len(data):
            other = material_end + 1 + flip % (len(data) - material_end - 1)
            data[other] ^= 0xFF
        return bytes(data)
    data = bytearray(blob[:cut])
    if data:
        data[0] ^= 0xFF
        if len(data) > 1:
            other = flip % len(data)
            if other:
                data[other] ^= 0xFF
    return bytes(data)


def _check(parser, expected_error, blob: bytes, cut: int, flip: int) -> None:
    try:
        result = parser(_damaged(blob, cut, flip))
        if isinstance(result, gma.GmaArchive):
            for entry in result.entries:
                result.read(entry.path)
        elif isinstance(result, vpk.VpkArchive):
            for entry in result.entries:
                result.read(entry.path)
    except expected_error:
        return
    raise AssertionError(f"{parser!r} accepted corrupted input")


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(GMA_BLOB)), flip=st.integers(min_value=0, max_value=len(GMA_BLOB)))
def test_gma_corruption_uses_gma_error(cut, flip):
    _check(gma.GmaArchive, gma.GmaError, GMA_BLOB, cut, flip)


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(VPK_BLOB)), flip=st.integers(min_value=0, max_value=len(VPK_BLOB)))
def test_vpk_corruption_uses_vpk_error(cut, flip):
    _check(vpk.VpkArchive, vpk.VpkError, VPK_BLOB, cut, flip)


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(VTF_BLOB)), flip=st.integers(min_value=0, max_value=len(VTF_BLOB)))
def test_vtf_corruption_uses_vtf_error(cut, flip):
    _check(vtf.parse_vtf, vtf.VtfError, VTF_BLOB, cut, flip)


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(SMD_BLOB)), flip=st.integers(min_value=0, max_value=len(SMD_BLOB)))
def test_smd_corruption_uses_smd_error(cut, flip):
    _check(lambda data: smd.parse_smd(data.decode("latin1")), smd.SmdError, SMD_BLOB, cut, flip)


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(WWISE_BLOB)), flip=st.integers(min_value=0, max_value=len(WWISE_BLOB)))
def test_wwise_corruption_uses_format_error(cut, flip):
    _check(wwise_ima.read, wwise_ima.FormatError, WWISE_BLOB, cut, flip)


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(MODEL_BLOB)), flip=st.integers(min_value=0, max_value=len(MODEL_BLOB)))
def test_diesel_model_corruption_uses_model_error(cut, flip):
    _check(dm.ModelFile.read, dm.ModelFormatError, MODEL_BLOB, cut, flip)


@settings(max_examples=120, deadline=None)
@given(cut=st.integers(min_value=1, max_value=len(DDS_BLOB)), flip=st.integers(min_value=0, max_value=len(DDS_BLOB)))
def test_dds_corruption_uses_value_error(cut, flip):
    _check(dds_encode.bc3_levels, ValueError, DDS_BLOB, cut, flip)


def test_model_reader_accepts_every_distributed_model_and_recovered_2b_template():
    models = []
    for archive in sorted((ROOT / "dist").rglob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            models.extend((f"{archive.name}:{name}", zf.read(name))
                          for name in zf.namelist() if name.endswith(".model"))
    if not all((TEMPLATES / name).is_file() for name in TEMPLATE_FILES):
        pytest.skip(MISSING)
    models.extend((str(path), path.read_bytes()) for path in TEMPLATES.rglob("*.model"))
    assert models, "expected distributed or recovered .model fixtures"
    for label, blob in models:
        try:
            dm.ModelFile.read(blob)
        except dm.ModelFormatError as exc:
            raise AssertionError(f"ModelFile.read rejected {label}: {exc}") from exc
