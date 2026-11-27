"""A bad value in a source asset is an error that names it, not a default that hides it.

Two readers used to swallow the failure and carry on: `model_to_glb.read_material_configs`
dropped an `alpha_ref` it could not parse (the material then shipped opaque), and
`rw_dff` dropped a frame-name extension whose chunks did not parse (the rig then had no
bone names). Both failed far away from the cause, in a render or a bone lookup, with no
mention of the file. These tests pin the message to the file and the value.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import model_to_glb  # noqa: E402
import rw_dff  # noqa: E402

MATERIAL_CONFIG = """<?xml version="1.0"?>
<material_config>
  <material name="g_head" render_template="shd_singleton">
    <diffuse_texture file="old_hoxton_head_df"/>
    <variable name="alpha_ref" value="{value}"/>
  </material>
</material_config>
"""


def _source_with(tmp_path: Path, value: str) -> model_to_glb.Source:
    unit = tmp_path / "units" / "pd2" / "characters" / "suit"
    unit.mkdir(parents=True)
    (unit / "suit.material_config").write_text(MATERIAL_CONFIG.format(value=value))
    return model_to_glb.Source(tmp_path)


def test_alpha_ref_is_read(tmp_path):
    info = model_to_glb.read_material_configs(_source_with(tmp_path, "0.42"))["g_head"]
    assert info.alpha_ref == pytest.approx(0.42)


def test_an_unparseable_alpha_ref_names_the_file_and_the_value(tmp_path):
    with pytest.raises(ValueError) as excinfo:
        model_to_glb.read_material_configs(_source_with(tmp_path, "half"))
    message = str(excinfo.value)
    assert "suit.material_config" in message, message
    assert "'g_head'" in message, message
    assert "'half'" in message, message


def _chunk(ctype: int, body: bytes) -> bytes:
    return struct.pack("<III", ctype, len(body), 0x36003) + body


def test_frame_names_are_read_in_frame_order():
    plugin = _chunk(rw_dff.FRAME_NAME_PLUGIN, b" Pelvis")
    frame_list = _chunk(rw_dff.ID_FRAMELIST, _chunk(rw_dff.ID_EXTENSION, plugin) * 2)
    frame_c = rw_dff.one(memoryview(frame_list), rw_dff.ID_FRAMELIST)
    assert rw_dff.frame_names(frame_c, 2) == [" Pelvis", " Pelvis"]


def test_a_name_count_that_disagrees_leaves_the_frames_unnamed():
    plugin = _chunk(rw_dff.FRAME_NAME_PLUGIN, b" Pelvis")
    frame_list = _chunk(rw_dff.ID_FRAMELIST, _chunk(rw_dff.ID_EXTENSION, plugin))
    frame_c = rw_dff.one(memoryview(frame_list), rw_dff.ID_FRAMELIST)
    assert rw_dff.frame_names(frame_c, 3) == []


def test_an_unreadable_frame_extension_names_the_frame():
    overrun = struct.pack("<III", rw_dff.FRAME_NAME_PLUGIN, 999, 0) + b"\0\0"
    frame_list = _chunk(rw_dff.ID_FRAMELIST, _chunk(rw_dff.ID_EXTENSION, overrun))
    frame_c = rw_dff.one(memoryview(frame_list), rw_dff.ID_FRAMELIST)
    with pytest.raises(ValueError) as excinfo:
        rw_dff.frame_names(frame_c, 1)
    assert "frame 0" in str(excinfo.value), str(excinfo.value)
