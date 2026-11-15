"""Tests for the DOAXVV ``.TMC`` reader (Honoka "Secret Report" outfit).

The TMC lives inside the tracked third-party source archive
``references/Outfit for Honoka-109-1-1-1628020933.zip`` and is extracted to a
``tmp_path`` once per session. The reader must:

* decode the per-mesh skin palettes inline in the ``WGT_*`` ``NodeLay``
  records (2026-11-15: vertex bone indices are SLOTS into these palettes,
  not node indices — see docs/pd2-las/honoka-tmc-format.md);
* produce normal-consistent winding for every mesh (2026-11-15 later:
  ``_align_winding_to_normals``; absolute strip parity is not one rule);
* remap ``JOINTS_0`` through the palette in the glTF export helper.
"""
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

ZIP = REPO / "references" / "Outfit for Honoka-109-1-1-1628020933.zip"
TMC_NAME = "Honoka_DOAXVV_Secret_Report.TMC"


@pytest.fixture(scope="module")
def tmc_path(tmp_path_factory):
    if not ZIP.is_file():
        pytest.skip("Honoka TMC source archive is not present")
    dst = tmp_path_factory.mktemp("honoka") / TMC_NAME
    with zipfile.ZipFile(ZIP) as z:
        dst.write_bytes(z.read(TMC_NAME))
    return dst


@pytest.fixture(scope="module")
def tmc(tmc_path):
    import tmc as tmc_mod

    return tmc_mod.TmcFile(str(tmc_path))


@pytest.fixture(scope="module")
def meshes(tmc):
    return {m.group: m for m in tmc.load_meshes()}


EXPECTED_PALETTES = {
    "WGT_cap2": 41,
    "WGT_headdress2": 43,
    "WGT_new_aya_body_decl0": 85,
    "WGT_new_aya_body_decl1": 85,  # shares the new_aya_body mesh palette
    "WGT_sweat_chest": 9,
    "WGT_body_feather": None,      # no palette; slots are coherent as raw node indices
}


def test_mesh_palettes_decoded(meshes):
    assert set(EXPECTED_PALETTES) <= set(meshes)
    for group, size in EXPECTED_PALETTES.items():
        pal = meshes[group].palette
        if size is None:
            assert pal is None, group
            continue
        assert pal is not None and len(pal) == size, group
        assert len(set(pal)) == size, f"{group}: duplicate palette entries"
        assert all(0 <= p < 171 for p in pal), f"{group}: palette entry out of range"


def test_every_mesh_winds_consistently_with_stored_normals(meshes):
    for group, m in meshes.items():
        pos = np.asarray(m.positions, dtype=np.float64)
        nrm = np.asarray(m.normals, dtype=np.float64)
        idx = np.asarray(m.indices).reshape(-1, 3).astype(np.int64)
        fn = np.cross(pos[idx[:, 1]] - pos[idx[:, 0]], pos[idx[:, 2]] - pos[idx[:, 0]])
        vn = nrm[idx[:, 0]] + nrm[idx[:, 1]] + nrm[idx[:, 2]]
        denom = np.linalg.norm(vn, axis=1)
        alive = denom > 1e-6
        agree = ((fn[alive] * vn[alive]).sum(axis=1) > 0).mean()
        assert agree == pytest.approx(1.0), f"{group}: {agree:.4f} of triangles agree with vertex normals"


def test_weights_sum_to_one_or_are_unweighted_placeholders(meshes):
    for group, m in meshes.items():
        w = np.asarray(m.weights)
        sums = w.sum(axis=1)
        unweighted = np.asarray(m.unweighted)
        bad = (~unweighted) & (np.abs(sums - 1.0) > 1e-4)
        assert not bad.any(), f"{group}: {bad.sum()} rows whose weights do not sum to 1"
        if unweighted.any():
            assert (sums[unweighted] == 0).all()


def test_palette_remap_makes_skinning_anatomically_coherent(tmc, meshes):
    """Breast-bound verts must sit at the chest, not at the hips or feet."""
    m = meshes["WGT_new_aya_body_decl0"]
    pal = np.asarray(m.palette)
    gbi = pal[np.asarray(m.bone_indices, dtype=np.int64)]
    w = np.asarray(m.weights)
    names = tmc.node_names
    pos = np.asarray(m.positions) / 100.0  # cm -> raw units
    target = {i for i, n in enumerate(names) if n in ("OPT_Breast_Left_tip", "OPT_Breast_Right_tip")}
    mask = np.zeros(len(gbi), dtype=bool)
    for k in range(4):
        mask |= np.isin(gbi[:, k], list(target)) & (w[:, k] > 0.5)
    assert mask.any(), "expected breast-bound vertices in the body mesh"
    ys = pos[mask, 1]
    assert ys.mean() > 0.15, f"breast-bound verts average height {ys.mean():.3f} (raw units)"
