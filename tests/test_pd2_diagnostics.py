"""Offline probes should read the inputs they say they measure."""
from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))

import audit_metrics  # noqa: E402
import extract_2b  # noqa: E402
import uv_check  # noqa: E402


@pytest.mark.skipif(not extract_2b.present(), reason=extract_2b.MISSING)
def test_default_uv_probe_renders_the_pack_and_its_own_textures(tmp_path):
    assert uv_check.main(["--size", "96", "--out", str(tmp_path)]) == 0
    renders = {p.name for p in tmp_path.glob("*.png")}
    assert len(renders) == 14
    assert "uvcheck_ours_g_body_mtr_body_front.png" in renders
    assert "uvcheck_ours_g_head_mtr_eyes_iso.png" in renders


def test_atlas_density_uses_actual_diffuse_width_and_height(tmp_path, monkeypatch, capsys):
    template = tmp_path / "template"
    template.mkdir()
    (template / "2b.model").touch()
    # Triangle area is 0.5 cm², so 8 x 4 texels has nominal density 8 texels/cm.
    Image.new("RGB", (8, 4)).save(template / "base_df.texture", format="PNG")
    monkeypatch.setattr(audit_metrics, "_drawable", lambda _: (
        {"verts": [(0, 0, 0), (1, 0, 0), (0, 1, 0)], "normals": [(0, 0, 1)] * 3},
        {"indices": [0, 1, 2]},
    ))
    assert audit_metrics.main(["--template", str(template), "--dist", str(tmp_path)]) == 0
    row = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("2B reference"))
    assert row.removeprefix("2B reference (PD2)").split()[4] == "8.00"
