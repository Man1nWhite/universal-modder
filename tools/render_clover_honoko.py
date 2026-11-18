#!/usr/bin/env python3
"""Render the updated Honoko5 and Christie Clover compiled LAS outfits.

Run the two pack builders first, then:
    .venv/bin/python tools/render_clover_honoko.py
These are offline bind-pose renders, not in-game captures.
"""
from pathlib import Path

import render_mod_previews as render

ROOT = Path(__file__).resolve().parents[1]


def main():
    specs = (
        ('dist/Honoka/Honoko5.zip', 'Honoko5', 'honoko5',
         'docs/renders/honoka/model/updated/honoko5_las_sheet.png',
         'Honoko5 — updated jewelry texture',
         'BODY_ONLY | suit: Tex_07(L_7)3 | jewelry: Tex_23(L_23)2 | offline bind pose', frozenset()),
        ('dist/Christie/Christie_Clover_LAS.zip', 'Christie_Clover_LAS', 'clover_christie',
         'docs/renders/christie/model/clover/christie_clover_las_sheet.png',
         'Christie Clover — experimental LAS outfit',
         'BODY_ONLY | no custom head, hands or FPS model | offline bind pose', frozenset({'clover_christie_3'})),
    )
    for archive, tag, prefix, output, title, subtitle, cutouts in specs:
        body, fps, icon = render.load_multi_mat_las_parts(
            ROOT / archive, tag, prefix, has_fps=False, cutout_materials=cutouts)
        render.render_las_sheet(title, subtitle, body, fps, icon, ROOT / output, has_head=False)


if __name__ == '__main__':
    main()
