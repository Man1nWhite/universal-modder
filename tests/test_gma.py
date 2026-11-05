"""The `.gma` reader: a subscribed addon must be inspectable without gmad.

`tools/pd2-las/gma.py` exists so that "what is inside the Fruitcake Christie
addon?" can be answered from the file the user already has, instead of from a
workshop description. These tests build a real GMAD archive byte-for-byte from
the published layout (Facepunch `gmad/src/create_gmad.cpp`) and read it back, so
the parser is pinned to the format and not to a sample only this repo has.

They also pin the two behaviours a hand-rolled reader gets wrong: the
LZMA-wrapped payload Steam sometimes serves, and the JSON-in-the-description
field that `gmad` uses for type and tags.
"""
from __future__ import annotations

import json
import lzma
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))

import gma  # noqa: E402


def _cstr(text: str) -> bytes:
    return text.encode() + b"\x00"


def build_gma(
    files: dict[str, bytes],
    *,
    version: int = 3,
    title: str = "Test Addon",
    description: str = "Hand-written description",
    author: str = "Author Name",
    tags: tuple[str, ...] = ("fun", "realism"),
    addon_type: str = "model",
    required_content: tuple[str, ...] = (),
    description_json: bool = True,
    steamid: int = 0,
    timestamp: int = 1_569_000_000,
) -> bytes:
    """Assemble an uncompressed GMAD v3 exactly as `gmad create` writes one."""
    if description_json:
        description = json.dumps(
            {"description": description, "type": addon_type, "tags": list(tags)}
        )
    out = bytearray()
    out += b"GMAD"
    out += struct.pack("<B", version)
    out += struct.pack("<Q", steamid)
    out += struct.pack("<Q", timestamp)
    if version > 1:
        for item in required_content:
            out += _cstr(item)
        out += b"\x00"  # empty string closes the required-content list
    out += _cstr(title)
    out += _cstr(description)
    out += _cstr(author)
    out += struct.pack("<I", 1)  # addon version, unused
    for number, (path, body) in enumerate(files.items(), start=1):
        out += struct.pack("<I", number)
        out += _cstr(path.lower())
        out += struct.pack("<q", len(body))
        out += struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)
    out += struct.pack("<I", 0)  # zero file number closes the index
    for body in files.values():
        out += body
    return bytes(out)


FILES = {
    "models/player/christie.mdl": b"MDL-body" * 10,
    "models/player/christie.vvd": b"VVD-body" * 10,
    "models/player/christie.dx90.vtx": b"VTX-body" * 10,
    "materials/models/christie/body.vmt": b'"VertexLitGeneric" {}',
}


def test_reads_a_plain_gma():
    arc = gma.GmaArchive(build_gma(FILES))
    assert arc.version == 3
    assert (arc.title, arc.author) == ("Test Addon", "Author Name")
    assert arc.read("models/player/christie.vvd") == FILES["models/player/christie.vvd"]
    assert arc.read("MODELS/player/christie.MDL") == FILES["models/player/christie.mdl"]


def test_the_description_is_json_and_is_unpacked():
    arc = gma.GmaArchive(build_gma(FILES, description="Her suit and dress."))
    assert arc.description == "Her suit and dress."
    assert arc.addon_type == "model"
    assert arc.tags == ("fun", "realism")


def test_a_plain_text_description_survives():
    arc = gma.GmaArchive(build_gma(FILES, description="raw text", description_json=False))
    assert arc.description == "raw text"
    assert arc.addon_type == ""
    assert arc.tags == ()


def test_lzma_wrapped_payload_is_unwrapped():
    """Steam serves some older items LZMA-wrapped with no header of their own."""
    plain = build_gma(FILES)
    for wrapped in (
        lzma.compress(plain, format=lzma.FORMAT_ALONE),
        lzma.compress(plain, format=lzma.FORMAT_XZ),
    ):
        assert gma.GmaArchive(wrapped).read("models/player/christie.vvd") == (
            FILES["models/player/christie.vvd"]
        )


def test_crc_mismatch_is_reported_not_ignored():
    blob = bytearray(build_gma(FILES))
    blob[-1] ^= 0xFF  # corrupt the last body byte of the last file
    arc = gma.GmaArchive(bytes(blob))
    with pytest.raises(gma.GmaError, match="CRC mismatch"):
        arc.read("materials/models/christie/body.vmt")


def test_a_truncated_archive_is_refused_up_front():
    blob = build_gma(FILES)[:-32]
    with pytest.raises(gma.GmaError, match="file bodies need"):
        gma.GmaArchive(blob)


def test_traversal_in_a_file_name_is_refused():
    with pytest.raises(gma.GmaError, match="unsafe entry path"):
        gma.GmaArchive(build_gma({"../../evil.dll": b"x"}))


def test_v1_has_no_required_content_list():
    arc = gma.GmaArchive(build_gma(FILES, version=1, required_content=("ignored",)))
    assert arc.title == "Test Addon"
    assert len(arc.entries) == len(FILES)


def test_model_triples_prefer_the_dx90_vtx():
    files = dict(FILES)
    files["models/player/christie.vtx"] = b"old-vtx"
    triples = gma.GmaArchive(build_gma(files)).model_paths()
    assert triples == [
        (
            "models/player/christie.mdl",
            "models/player/christie.vvd",
            "models/player/christie.dx90.vtx",
        )
    ]


def test_a_mdl_without_a_vvd_is_not_a_model_triple():
    files = {"models/x.mdl": b"mdl", "models/x.vtx": b"vtx"}
    assert gma.GmaArchive(build_gma(files)).model_paths() == []


def test_summary_names_the_files_that_matter():
    text = gma.GmaArchive(build_gma(FILES)).summary()
    assert "Test Addon" in text
    assert "4 files" in text
    assert "mdl x1" in text and "vmt x1" in text
    assert "models/player/christie.mdl" in text


def test_a_non_gma_file_is_a_clean_error():
    with pytest.raises(gma.GmaError, match="not a GMAD archive"):
        gma.GmaArchive(b"PK\x03\x04 not an addon")
