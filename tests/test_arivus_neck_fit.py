"""The Arivus head must meet Old Hoxton's collar from every angle (D72).

The Random4 ped's neck is cut at z ~ 159 cm, and its front surface used to show through
the back of the shared suit's collar opening as a strip of skin with a jagged top edge.
The builder lowers the cut edge below the opening and shortens the neck above it, so no
surface is left inside the opening at the back and no gap opens at the throat. These are
measurements on the shipped models (heist, menu and Safe House), not on a render.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import diesel_model as dm  # noqa: E402
from dist_paths import dist_path  # noqa: E402

PACK = dist_path(ROOT, "Arivus_over_Hoxton.zip")
PREFIX = "Arivus over Hoxton"
MODELS = (
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_1.model",
    "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_menu_1.model",
    "units/pd2_dlc_chill/characters/shared_character/npc_criminals_suit_chill.model",
)


def head_vertices(model_bytes: bytes) -> np.ndarray:
    mf = dm.ModelFile.read(model_bytes)
    model_data = {
        dm.decode_model_data(s.payload)["name_hash"]: dm.decode_model_data(s.payload)
        for s in mf.by_type(dm.MODEL_DATA)
    }
    md = model_data[dm.hash64("g_head_old_hoxton")]
    pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
    return np.asarray(geo["verts"], np.float32)


@pytest.mark.parametrize("model_rel", MODELS)
def test_the_neck_edge_and_back_surface_are_hidden_by_the_collar(model_rel: str) -> None:
    with zipfile.ZipFile(PACK) as zf:
        verts = head_vertices(zf.read(f"{PREFIX}/{model_rel}"))

    # The cut edge sits below the collar's rim (the suit's back rim starts near z 159),
    # so the jagged bottom of the ped's neck is not on show.
    assert float(verts[:, 2].min()) < 158.5
    # Nothing of the neck's back half lives inside the opening: from behind, the only
    # vertices down there are the front of the neck, which is hidden by the suit.
    in_opening = (np.abs(verts[:, 0]) < 8.0) & (verts[:, 1] < 1.0) & (verts[:, 2] < 164.0)
    assert int(in_opening.sum()) == 0, f"{int(in_opening.sum())} back neck vertices in the opening"
    # ... while the throat still reaches the collar, so the front has no gap.
    throat = (np.abs(verts[:, 0]) < 8.0) & (verts[:, 1] > 5.0) & (verts[:, 2] < 160.0)
    assert int(throat.sum()) >= 3, "the neck stops above the front of the collar"
