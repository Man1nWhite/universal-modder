"""The source texture sheet includes both alternate Honoko suit maps."""

import importlib.util
from pathlib import Path

from PIL import Image, ImageChops

REPO = Path(__file__).resolve().parents[1]


def test_contact_sheet_includes_alternate_suit_diffuses(tmp_path, monkeypatch):
    script = REPO / "tools/pd2-las/render_honoka.py"
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location("honoka_render_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.render_dds_sheet(tmp_path)
    sheet = Image.open(tmp_path / "honoka_dds_contact_sheet.png").convert("RGB")
    assert sheet.size == (6 * 240, 5 * 278 + 56)
    for index, name in enumerate(("Tex_07(L_7) 2.dds", "Tex_07(L_7)3.dds"), start=27):
        assert name in module.DDS_ROLE_NOTES
        source = Image.open(module.TEX_DIR / name).convert("RGB")
        source.thumbnail((220, 220), Image.Resampling.LANCZOS)
        row, col = divmod(index, 6)
        x = col * 240 + (240 - source.width) // 2
        y = 56 + row * 278 + 10 + (220 - source.height) // 2
        crop = sheet.crop((x, y, x + source.width, y + source.height))
        assert ImageChops.difference(crop, source).getbbox() is None
