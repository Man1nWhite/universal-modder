#!/usr/bin/env python3
"""Build the tracked Arivus head interchange pack: one ``.glb`` and its ``.dds``.

    .venv/bin/python tools/pd2-las/build_arivus_glb_pack.py

Reads the tracked ``dist/Arivus/Arivus_over_Hoxton.zip`` — no game install and no 2B
templates — and exports only ``g_head_old_hoxton`` with its bind-pose skin, plus
every ``.texture`` in that pack as a DDS byte copy. ``model_to_glb.py`` does the
conversion; this script is the packaging step that makes the result shippable: a
fixed member order, fixed timestamps and the tree's one zip writer (D16), then a
repo-relative ``.sha256`` sidecar.

The owner authorized committing these game-derived bytes (D74), so unlike a
scratch export the output is tracked in ``dist/Arivus/`` and rebuilt by
``make -sC tools/pd2-las glb`` / ``fresh.py check``. It is a viewer/interchange
export, not an installable mod: ``runtime_verified`` stays false.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import model_to_glb as mtg  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from las_outfit_pack import zip_bytes  # noqa: E402
from pack_checksum import write_pack_checksum  # noqa: E402

SOURCE = ROOT / "dist/Arivus/Arivus_over_Hoxton.zip"
PACK = dist_path(ROOT, "Arivus_Head_over_Old_Hoxton_GLB.zip")
INTERNAL = "Arivus Head GLB/"
MODEL = "npc_criminals_suit_1.model"
DRAWABLE = "g_head_old_hoxton"
GLB_NAME = "arivus_head_over_old_hoxton.glb"
STAMP = (2020, 1, 1, 0, 0, 0)

README = """Arivus head over Old Hoxton — glTF / DDS interchange export

Contents: arivus_head_over_old_hoxton.glb (the g_head_old_hoxton drawable of
npc_criminals_suit_1.model, bind-pose skin, alpha-masked hair) and the five
DDS textures of the Arivus_over_Hoxton pack. The GLB embeds PNG copies of the
two textures its material uses; the .dds files are the pack's raw .texture
bytes, renamed by extension only.

This is not a PAYDAY 2 mod to install. It is a viewer/interchange export for
Blender, three.js or a phone: runtime_verified is false, the exporter is not a
runtime oracle, and the source pack's own bytes are untouched.

Rebuild from the repository root with `make -sC tools/pd2-las glb`. The output
is byte-reproducible in the pinned environment; `make -sC tools/pd2-las fresh`
proves it. Provenance and per-file digests: manifest.json.
"""


def members() -> tuple[dict[str, bytes], dict]:
    """The export's files and its manifest, both derived from the tracked pack."""
    src = mtg.Source(SOURCE)
    cfg = mtg.read_material_configs(src)
    rel = next(k for k in mtg.models_in(src, MODEL))
    unit = mtg.read_unit(src, rel, cfg)
    scratch = ROOT / "build/pd2-las/arivus_glb_pack"
    report = mtg.export_glb(
        src, unit, cfg, scratch / GLB_NAME,
        only={DRAWABLE}, skin=True, write_dds=True, write_png=False,
        all_textures=True,
    )
    if report["drawables"] != [DRAWABLE] or report["meshes"] != 1:
        raise SystemExit(f"unexpected export: {report['drawables']}")
    glb = (scratch / GLB_NAME).read_bytes()
    textures = {p.name: p.read_bytes() for p in sorted((scratch / "textures").glob("*.dds"))}
    if not textures:
        raise SystemExit("no .dds written beside the .glb")
    files = {GLB_NAME: glb, **textures}
    manifest = {
        "source_pack": SOURCE.relative_to(ROOT).as_posix(),
        "source_model": MODEL,
        "drawable": DRAWABLE,
        "converter": "tools/pd2-las/model_to_glb.py",
        "builder": "tools/pd2-las/build_arivus_glb_pack.py",
        "runtime_verified": False,
        "warnings": report["warnings"],
        "files": {name: {"bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(files.items())},
    }
    files["README.txt"] = README.encode("utf-8")
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return files, manifest


def main() -> int:
    files, manifest = members()
    data = zip_bytes([(INTERNAL + name, payload) for name, payload in sorted(files.items())],
                     stamp=STAMP)
    PACK.parent.mkdir(parents=True, exist_ok=True)
    PACK.write_bytes(data)
    write_pack_checksum(PACK, ROOT)
    print(f"wrote {PACK.relative_to(ROOT).as_posix()}: "
          f"{len(manifest['files'])} export files, {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
