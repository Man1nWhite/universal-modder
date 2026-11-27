"""Unit tests for the build-path modules nothing else exercised.

`tmc_export` writes the glTF the Arivus GLB pack ships, `segment_fit` measures a built mesh
against the rig and `trace_run` records the checkpoints `fresh.py matrix --trace` compares.
All three ran only inside a label-gated rebuild: a break showed up as `packs` failing on main half an hour later, with
the cause buried in the build log. These are small synthetic inputs, not the real packs.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import segment_fit  # noqa: E402
import tmc_export  # noqa: E402
import trace_run  # noqa: E402


# ------------------------------------------------------------------ tmc_export

def test_identity_is_the_identity_quaternion():
    assert tmc_export.quat_from_rot(np.eye(3)) == pytest.approx([0.0, 0.0, 0.0, 1.0], abs=1e-12)


def test_a_quarter_turn_about_z_is_normalised_and_has_the_right_signs():
    angle = np.pi / 2
    rot = np.array([[np.cos(angle), -np.sin(angle), 0],
                    [np.sin(angle), np.cos(angle), 0],
                    [0, 0, 1]], dtype=float)
    x, y, z, w = tmc_export.quat_from_rot(rot)
    assert (x, y) == pytest.approx((0.0, 0.0), abs=1e-12)
    assert z == pytest.approx(np.sqrt(0.5), abs=1e-9)
    assert w == pytest.approx(np.sqrt(0.5), abs=1e-9)
    assert x * x + y * y + z * z + w * w == pytest.approx(1.0, abs=1e-12)


def test_the_glb_container_is_a_valid_two_chunk_file():
    glb = tmc_export.Glb()
    verts = np.array([[0, 0, 0], [1, 0, 0], [0, 2, 0]], dtype=np.float32)
    glb.add_accessor(verts, tmc_export.FLOAT, "VEC3", tmc_export.ARRAY_BUFFER, 3)
    data = glb.build({"asset": {"version": "2.0"}})

    magic, version, total = struct.unpack_from("<4sII", data, 0)
    assert (magic, version, total) == (b"glTF", 2, len(data))
    json_len, json_type = struct.unpack_from("<II", data, 12)
    assert json_type == 0x4E4F534A and json_len % 4 == 0
    document = json.loads(data[20:20 + json_len])
    assert document["accessors"][0]["min"] == [0.0, 0.0, 0.0]
    assert document["accessors"][0]["max"] == [1.0, 2.0, 0.0]
    bin_len, bin_type = struct.unpack_from("<II", data, 20 + json_len)
    assert bin_type == 0x004E4942 and bin_len % 4 == 0
    assert document["buffers"][0]["byteLength"] <= bin_len


# ------------------------------------------------------------------- trace_run

def _digest(pair) -> tuple[str, str]:
    return tuple(h.hexdigest() for h in pair)  # type: ignore[return-value]


def test_float64_moves_the_whole_checksum_but_not_the_exact_one(tmp_path):
    trace = trace_run.Trace(str(tmp_path / "trace.log"), ROOT)
    try:
        a = trace_run._pair()
        b = trace_run._pair()
        trace.feed(np.array([1.0, 2.0], dtype=np.float64), a)
        trace.feed(np.array([1.0, 2.0000000000000004], dtype=np.float64), b)
        whole_a, exact_a = _digest(a)
        whole_b, exact_b = _digest(b)
        assert whole_a != whole_b, "a last-bit float64 difference has to show in the whole digest"
        assert exact_a == exact_b, "float64 values are left out of the exact digest by design"
    finally:
        trace.out.close()


def test_an_uint8_difference_moves_both_checksums(tmp_path):
    trace = trace_run.Trace(str(tmp_path / "trace.log"), ROOT)
    try:
        a, b = trace_run._pair(), trace_run._pair()
        trace.feed(np.array([1, 2], dtype=np.uint8), a)
        trace.feed(np.array([1, 3], dtype=np.uint8), b)
        assert _digest(a) != _digest(b)
    finally:
        trace.out.close()


def test_the_root_is_hashed_as_a_placeholder_not_as_a_path(tmp_path):
    """Two checkouts at different paths must produce the same trace."""
    first = trace_run.Trace(str(tmp_path / "a.log"), tmp_path)
    second = trace_run.Trace(str(tmp_path / "b.log"), Path("/somewhere/else"))
    try:
        a, b = trace_run._pair(), trace_run._pair()
        first.feed(str(tmp_path / "dist" / "x.zip"), a)
        second.feed("/somewhere/else/dist/x.zip", b)
        assert _digest(a) == _digest(b)
    finally:
        first.out.close()
        second.out.close()


def test_a_code_object_outside_tools_is_not_named(tmp_path):
    trace = trace_run.Trace(str(tmp_path / "trace.log"), ROOT)
    try:
        assert trace.name((lambda: None).__code__) is None
        assert trace.name(trace_run.Trace.name.__code__) is None      # trace_run itself is skipped
    finally:
        trace.out.close()


# ----------------------------------------------------------------- segment_fit

def test_the_circle_fit_ignores_uneven_spacing_around_the_ring():
    """The point of the Kasa fit: clustered verts must not pull the centre off the bone."""
    angle = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    ring = np.column_stack([5 * np.cos(angle) + 3, 5 * np.sin(angle) - 7])
    clustered = np.vstack([ring, ring[:5] + 1e-9])        # five of them counted twice
    for points in (ring, clustered):
        (cx, cy), radius, rms = segment_fit._kasa_circle(points)
        assert (cx, cy) == pytest.approx((3.0, -7.0), abs=1e-6)
        assert radius == pytest.approx(5.0, abs=1e-6)
        assert rms < 1e-6


def test_the_fit_report_lists_every_segment_it_was_given():
    report = {"segments": {"ForeArm": {"max": 1.25, "rms": 0.5, "d_proximal": 0.1,
                                      "d_distal": 0.2, "drift": 0.3}},
              "joints": {"Elbow": 0.4}}
    text = segment_fit.format_report("probe", report)
    assert "[probe] mesh-vs-skeleton fit (cm, PD2 bind space)" in text
    assert "ForeArm" in text and "1.25" in text
    assert "Elbow 0.40" in text
