"""What keeps the tracked bytes independent of the machine that builds them.

One test, at least, for each place that was fixed on 2026-11-12
(docs/audits/2026-11-12-cpu-independence.md): each fails when the old behaviour
is put back.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_christie_las  # noqa: E402
import build_las  # noqa: E402
import determinism  # noqa: E402
import diesel_model as dm  # noqa: E402
import fresh  # noqa: E402
import tangents  # noqa: E402

LAS_PACKS = (("Miranda_LAS", "miranda"), ("Miranda_Busty_LAS", "miranda_busty"),
             ("Christie_LAS", "christie"), ("Christie_LAS_Slim", "christie_slim"))

#: an eight-vertex box in every first-person model, copied from fps_2b.model as it is
TEMPLATE_BOX = 777890663

pytestmark = pytest.mark.skipif(not (REPO / "dist" / "Miranda_LAS.zip").is_file(),
                                reason="pack not built in this checkout")


# ------------------------------------------------------------------ rounding


def test_what_is_drawn_is_cut_off_below_a_nudged_boundary_and_stops_at_it():
    values = np.array([199.6, 199.4, 200.0, 199.9995, 199.99999999999997, -3.0, 300.0])
    assert determinism.floor8(values, "x").tolist() == [199, 199, 200, 200, 200, 0, 255]
    boundary = 8.0 - determinism.NUDGE
    for value in (boundary, boundary + 4e-10, boundary - 4e-10):
        with pytest.raises(determinism.TooClose):
            determinism.floor8(np.array([1.0, value]), "x")
    assert determinism.floor8(np.array([boundary + 3e-9, boundary - 3e-9]), "x").tolist() == [8, 7]
    assert determinism.floor8(np.array([boundary]), "x", check=False).tolist() == [8]
    with pytest.raises(determinism.TooClose):
        determinism.floor8(np.array([np.nan]), "x")
    assert determinism.MARGIN == 1e-9 and determinism.NUDGE == 2.0 ** -10


def test_a_mean_is_rounded_to_the_nearest_and_a_half_goes_up_on_every_machine():
    assert determinism.rounded(np.array([2.5, 3.5, 3.4, 3.6]), "x").tolist() == [3.0, 4.0, 3.0, 4.0]
    # 8.5 as one math library leaves it and as another does: the same whole number, and no stop
    assert determinism.rounded(np.array([8.5, 8.5 - 5e-15, 8.5 + 5e-15]), "x").tolist() == [9.0, 9.0, 9.0]
    assert np.rint(np.array([8.5 - 5e-15, 8.5, 8.5 + 5e-15])).tolist() == [8.0, 8.0, 9.0]       # what numpy's own rounding does
    boundary = 7.5 - determinism.SHIFT
    for value in (boundary, boundary + 4e-10, boundary - 4e-10):
        with pytest.raises(determinism.TooClose):
            determinism.rounded(np.array([1.0, value]), "x")
    assert determinism.rounded(np.array([boundary + 3e-9, boundary - 3e-9]), "x").tolist() == [8.0, 7.0]
    dark = np.zeros((2, 2, 4), dtype=np.uint8)
    dark[..., :3] = [[[5, 5, 5], [5, 5, 5]], [[6, 6, 6], [6, 6, 6]]]
    assert build_las.mip_levels(dark)[1][0, 0].tolist() == [6, 6, 6, 0]
    assert determinism.above(np.array([0.0, 0.5, 1.0]), 0.02, "x").tolist() == [False, True, True]
    with pytest.raises(determinism.TooClose):
        determinism.above(np.array([0.0, 0.02 + 5e-10]), 0.02, "x")
    assert determinism.SHIFT == 2.0 ** -25


def test_the_eye_is_the_same_under_another_math_library():
    """Values that differ as two math libraries do round to the same bytes; cut off, as before, they do not."""
    values = build_las.eye_values()
    drawn = build_las.draw_eye()
    assert values.dtype == np.float64 and np.array_equal(drawn, determinism.floor8(values, "eye"))
    noise = np.random.default_rng(7).uniform(-1e-12, 1e-12, values.shape)
    assert np.array_equal(determinism.floor8(values * (1.0 + noise), "eye", check=False), drawn)
    # the pupil is (2, 3, 5) exactly and its gloss 4: one bit less and cutting off gives (1, 2, 4) and 3
    cut = lambda image: np.clip(image, 0, 255).astype(np.uint8)        # noqa: E731
    assert not np.array_equal(cut(values * (1.0 - 1e-12)), cut(values))
    assert drawn[256, 256].tolist() == [2, 3, 5, 4]


def _function(path: str, name: str) -> str:
    text = (REPO / path).read_text(encoding="utf-8")
    start = text.index(f"\ndef {name}(")
    return text[start:text.index("\ndef ", start + 1)]


def test_what_the_build_draws_is_float64_and_cut_off_with_the_margin():
    """The paint functions: no float32, no hypot, no power for a square, and every cut through determinism."""
    drawn = {"tools/pd2-las/build_las.py": {"eye_values": (), "draw_eye": ("floor8(",), "eye_weights": (),
                                            "repaint_face": ("floor8(", "above(")},
             "tools/build_joy_head_mods.py": {"build_crisp_miranda_eye_texture": ("determinism.floor8(",),
                                              "shade_nostril_cavities": ("determinism.floor8(",)}}
    for path, functions in drawn.items():
        for name, needs in functions.items():
            source = _function(path, name)
            for old in ("float32", "np.hypot", "** 2", "** 4"):
                assert old not in source, f"{name} in {path}: {old} is back"
            for call in needs:
                assert call in source, f"{name} in {path} does not round with {call}"
    # the casts that are left are of whole numbers: gloss chosen by a comparison
    assert _function("tools/build_joy_head_mods.py", "build_crisp_miranda_eye_texture").count(".astype(np.uint8)") == 1
    assert _function("tools/build_joy_head_mods.py", "shade_nostril_cavities").count(".astype(np.uint8)") == 1
    assert ".astype(np.uint8)" not in _function("tools/pd2-las/build_las.py", "repaint_face")


def test_the_repaint_paints_the_sockets_and_the_lash_lines_and_nothing_else():
    flat = np.full((1024, 1024, 4), 200, dtype=np.uint8)
    flat[..., 3] = 30
    painted = build_las.repaint_face(flat)
    moved = (painted[..., :3] != flat[..., :3]).any(axis=2)
    assert 0.004 < moved.mean() < 0.03, moved.mean()                  # the sockets and the lash lines
    assert not moved[:200].any() and not moved[600:900].any()         # nowhere else
    assert int(painted[..., :3][moved].max()) <= 199
    assert set(np.unique(painted[..., 3]).tolist()) == {2, 4, 30}


# ------------------------------------------------------------ tangent frames


def _mesh(mirrored: bool):
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (2, 0.5, 0), (5, 5, 0), (6, 5, 0), (5, 6, 0)]
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    if mirrored:
        uvs = [(1.0 - u, v) for u, v in uvs]
    uvs.append(((uvs[1][0] + uvs[2][0]) / 2, (uvs[1][1] + uvs[2][1]) / 2))     # on the line 1-2: no UV area
    uvs += [(0.25, 0.25)] * 3                                               # an island on one point of the texture
    return verts, [(0, 0, 1)] * 8, uvs, [(0, 1, 2), (0, 2, 3), (1, 4, 2), (5, 6, 7)]


def _hands(normals, u, v) -> list[int]:
    return [int(round(float(np.dot(np.cross(n, a), b)))) for n, a, b in zip(normals, u, v)]


def test_a_vertex_without_uv_area_takes_its_handedness_from_a_rule():
    seen = {}
    for mirrored in (False, True):
        verts, normals, uvs, faces = _mesh(mirrored)
        u, v, ruled = tangents.tangent_frames(verts, normals, uvs, faces, details=True)
        hands = _hands(normals, u, v)
        assert ruled == [4, 5, 6, 7]
        assert hands[4] == hands[1] == hands[2] == hands[0], hands          # taken from the corners it shares a triangle with
        assert hands[5:] == [int(tangents.UNMIRRORED)] * 3, hands           # nobody to take it from
        seen[mirrored] = hands[0]
        # the same from float64 values that round to these float32 values, and from the triangles in another order
        nudged = lambda rows: [tuple(x * (1 + 1e-10) for x in row) for row in rows]      # noqa: E731
        assert tangents.tangent_frames(nudged(verts), nudged(normals), nudged(uvs), faces) == (u, v)
        assert tangents.tangent_frames(verts, normals, uvs, faces[::-1]) == (u, v)
    assert seen == {False: -seen[True], True: seen[True]} and seen[False] == int(tangents.UNMIRRORED)


def _geometries(data: bytes):
    model = dm.ModelFile.read(data)
    by_id = {section.id: section for section in model.sections}
    uses: dict = {}
    for section in model.sections:
        if section.type == dm.PASSTHROUGH_GP:
            gp = dm.decode_passthroughgp(section.payload)
            indices = dm.decode_topology(by_id[gp["topology"]].payload)["indices"]
            uses.setdefault(gp["geometry"], []).append(list(zip(indices[0::3], indices[1::3], indices[2::3])))
    for geometry, face_lists in uses.items():
        yield geometry, dm.decode_geometry(by_id[geometry].payload), face_lists


def test_tangent_frames_in_the_tracked_models_follow_from_the_file():
    """Every U and V direction of the eight tracked models, bit for bit, from the positions, normals and UVs beside it.

    That is what makes them independent of the machine: this test computes them
    again on whatever CPU runs it. Before 2026-11-12 they came from the float64
    values of the build, and 1,484 of them had a sign that rounding had chosen.
    """
    checked = ruled = 0
    for pack, unit in LAS_PACKS:
        with zipfile.ZipFile(REPO / "dist" / f"{pack}.zip") as z:
            for name in (f"{unit}.model", f"fps_{unit}.model"):
                for geometry, geo, face_lists in _geometries(z.read(f"{pack}/assets/units/{unit}/skins/{unit}/{name}")):
                    if not geo["uvdir_u"]:
                        continue
                    if geometry == TEMPLATE_BOX:                  # not made here: byte for byte the 2B template's
                        assert geo["vert_count"] == 8
                        continue
                    stored = [np.asarray(geo[key], np.float32).tobytes() for key in ("uvdir_u", "uvdir_v")]
                    for faces in face_lists:
                        u, v, by_rule = tangents.tangent_frames(geo["verts"], geo["normals"], geo["uv0"], faces, details=True)
                        if [np.asarray(u, np.float32).tobytes(), np.asarray(v, np.float32).tobytes()] == stored:
                            break
                    else:
                        raise AssertionError(f"{pack} {name} geometry {geometry}: the frames do not follow from the file")
                    checked += 1
                    ruled += len(by_rule)
    assert checked == 18 and ruled >= 1000, (checked, ruled)


# -------------------------------------------------------- the Christie sites


def test_a_fan_is_not_replaced_by_the_same_triangles_from_another_corner(monkeypatch):
    """A quad's two fans along one diagonal are the same triangles; rounding must not pick between them."""
    monkeypatch.setattr(build_christie_las, "_closable", lambda cand, count, dirn: True)
    monkeypatch.setattr(build_christie_las, "_tri_area", lambda v, t: 1.0)
    for noise in (2e-16, -2e-16):
        def alignment(v, n, t, noise=noise):
            along_0_2 = (1 in t) != (3 in t)                    # a triangle of the diagonal 0-2 has one of 1 and 3
            return (0.5 if along_0_2 else 0.1) + (noise if t[0] == 2 else 0.0)
        monkeypatch.setattr(build_christie_las, "_face_vn_dot", alignment)
        assert build_christie_las._fill_ring([0, 1, 2, 3], set(), None, None, None, None, 0.0) == [(0, 2, 1), (0, 3, 2)]
    monkeypatch.setattr(build_christie_las, "_face_vn_dot", lambda v, n, t: 0.9 if (0 in t) != (2 in t) else 0.1)
    assert build_christie_las._fill_ring([0, 1, 2, 3], set(), None, None, None, None, 0.0) == [(1, 3, 2), (1, 0, 3)]


def test_fit_figures_are_written_to_six_decimals():
    assert build_christie_las._figures({"a": 0.12345678912, "b": [1.00000049, {"c": 2, "d": "x"}], "e": None}) == {
        "a": 0.123457, "b": [1.0, {"c": 2, "d": "x"}], "e": None}

    def floats(node):
        if isinstance(node, float):
            yield node
        elif isinstance(node, dict):
            for value in node.values():
                yield from floats(value)
        elif isinstance(node, list):
            for value in node:
                yield from floats(value)

    for pack in ("Christie_LAS", "Christie_LAS_Slim"):
        with zipfile.ZipFile(REPO / "dist" / f"{pack}.zip") as z:
            info = json.loads(z.read(f"{pack}/BUILD_INFO.json"))
        numbers = list(floats(info["fit_tpp"])) + list(floats(info["fit_fps"]))
        assert len(numbers) > 100 and all(number == round(number, 6) for number in numbers), pack


# ------------------------------------------------------------- the code path


def _plain_env(**extra) -> dict:
    env = {key: value for key, value in os.environ.items() if key not in determinism.CODE_PATH and key != "PD2_CODEPATH"}
    return {**env, **extra}


def test_every_builder_enters_the_declared_code_path():
    for rel in ("tools/pd2-las/build_models.py", "tools/pd2-las/build_busty_variant.py", "tools/pd2-las/build_las.py",
                "tools/pd2-las/build_christie_las.py", "tools/build_joy_head_mods.py"):
        main = (REPO / rel).read_text(encoding="utf-8").split("\ndef main(", 1)[1]
        assert "    determinism.enter(__file__)\n" in main[:main.index("\n\n\n") if "\n\n\n" in main else len(main)], rel
    assert determinism.CODE_PATH == {
        "OPENBLAS_CORETYPE": "Nehalem", "OPENBLAS_NUM_THREADS": "1",
        "NPY_DISABLE_CPU_FEATURES": "X86_V3 X86_V4 AVX512_ICL AVX512_SPR", "GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2,-FMA"}


def test_the_declared_code_path_is_what_gets_loaded():
    """Started with nothing set, determinism.py starts again with the code path and reports what was loaded."""
    if platform.machine() != "x86_64" or not sys.platform.startswith("linux"):
        return                                                    # the declared code path is an x86-64 Linux one
    script = str(REPO / "tools" / "pd2-las" / "determinism.py")
    declared = subprocess.run([sys.executable, script], env=_plain_env(), capture_output=True, text=True)
    assert declared.returncode == 0, declared.stderr
    assert "dispatching to X86_V2;" in declared.stdout and "OpenBLAS Nehalem kernels on 1 thread(s)" in declared.stdout
    free = subprocess.run([sys.executable, script], env=_plain_env(PD2_CODEPATH="free"), capture_output=True, text=True)
    assert free.returncode == 0 and "left to the machine" in free.stderr
    # a process that loaded other kernels is told so: that is what stops a builder
    probe = "import sys; sys.path.insert(0, sys.argv[1]); import determinism; print(determinism.loaded())"
    other = subprocess.run([sys.executable, "-c", probe, str(REPO / "tools" / "pd2-las")], capture_output=True, text=True,
                           env=_plain_env(OPENBLAS_CORETYPE="Prescott", OPENBLAS_NUM_THREADS="2"))
    assert other.returncode == 0 and ("OpenBLAS runs its" in other.stdout or "numpy dispatches to" in other.stdout), other.stdout


# ------------------------------------------------------------ the instruments


def test_two_traces_are_compared_by_function(tmp_path):
    first = ["C a.f#1 11 22 1 a:3", "R a.f#1 33 44 2", "R a.g#1 55 66 3", "S a.f 1 77 88 1 10", "S a.g 1 99 aa 3 10"]
    (tmp_path / "one.log").write_text("\n".join(first) + "\n")
    (tmp_path / "same.log").write_text("\n".join(first) + "\n")
    assert fresh.compare_traces(tmp_path / "one.log", tmp_path / "same.log") == ["the two traces are the same"]
    other = [first[0], "R a.f#1 3x 44 2", "R a.g#1 5x 6x 3", "S a.f 1 7x 88 1 10", "S a.g 1 9x ax 3 10"]
    (tmp_path / "other.log").write_text("\n".join(other) + "\n")
    lines = fresh.compare_traces(tmp_path / "one.log", tmp_path / "other.log")
    assert lines[0].startswith("first value that differs: return of a.f#1 (float64 only)")
    assert lines[1:] == ["exact: return of a.g#1"]
    assert len(fresh.tracked_zips()) == 16 and list(fresh.BUILDERS) == ["miranda", "busty", "christie", "slim", "lawson", "heads"]
