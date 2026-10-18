#!/usr/bin/env python3
"""Write BeardLib metadata, or repair metadata in existing Lawson ZIPs.

Usage: python tools/pd2-port/package_metadata.py dist/lawson_*.zip
Only README.txt and main.xml are changed; asset payloads are preserved.
"""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

CHARACTERS = ("bonnie", "clover", "sydney")
TEXTURE_DIR = "units/payday2/characters/shared_textures/lawson"


def package_metadata(character: str, texture_paths: list[str]) -> dict[str, bytes]:
    """Paths are relative to the mod root, including the .texture suffix."""
    if character not in CHARACTERS:
        raise ValueError(f"Unknown character: {character}")
    if not texture_paths:
        raise ValueError("No Lawson textures found")
    root = ET.Element("table", name=f"Lawson - {character.title()}", version="1.1")
    # Existing models/material_configs are native overrides. Only the new DB
    # paths need AddFiles. force=false lets the three packs share identical maps.
    add = ET.SubElement(root, "AddFiles", directory=".", force="false")
    for name in sorted(set(texture_paths)):
        path = PurePosixPath(name)
        if path.parent.as_posix() != TEXTURE_DIR or path.suffix != ".texture":
            raise ValueError(f"Unexpected texture path: {name}")
        ET.SubElement(add, "texture", path=path.with_suffix("").as_posix())
    ET.indent(root, space="    ")
    manifest = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    readme = f"""# {character.title()} -> Miranda Lawson (PAYDAY 2 character swap)

Packaging revision 1.1. In-game appearance, animation and compatibility have
NOT been verified by this packaging repair. The previous 'works in-game'
claim was not supported by an in-game test.

## Requirements

- SuperBLT (legacy BLT alone is not sufficient for BeardLib).
- BeardLib, installed as PAYDAY 2\\mods\\BeardLib\\mod.txt.
  Get it from https://github.com/simon-wh/PAYDAY-2-BeardLib/releases
  BeardLib is REQUIRED: main.xml registers the new Lawson texture paths.
  PocoHUD working confirms Lua mods load, not that model overrides load.

## Install / upgrade

1. Fully exit PAYDAY 2.
2. Move any older lawson_{character} folder outside the game as a backup.
   Check mods\\, mods\\mod_overrides\\ and assets\\mod_overrides\\ for copies.
3. Extract this ZIP into PAYDAY 2\\assets\\mod_overrides\\ (create it if absent).
   The final layout must be exactly:

   PAYDAY 2\\assets\\mod_overrides\\lawson_{character}\\main.xml
   PAYDAY 2\\assets\\mod_overrides\\lawson_{character}\\README.txt
   PAYDAY 2\\assets\\mod_overrides\\lawson_{character}\\units\\...

   NOT mods\\mod_overrides, and no extra lawson_{character} folder level.
   Do not put these asset packs beside PocoHUD in mods\\.
4. Initially test just this pack. Temporarily move other replacements for
   {character.title()} outside the game, and select the default outfit/two-piece suit.
5. Restart the game, select {character.title()}, and check the unmasked menu preview.
   Back up your save before testing an offline heist; also inspect a matching
   third-person/team character. This is not a separate outfit to equip.

## If nothing changes

- Confirm main.xml and units are directly inside the folder shown above.
- Confirm BeardLib is installed and enabled and the pack is not disabled in
  BeardLib. Seeing an entry in a mod manager is not proof its assets loaded.
- Fully restart after changing files/settings; merely switching characters
  may leave cached resources in use.
- If still unchanged, share a screenshot of the full install path, the game
  version, SuperBLT/BeardLib versions, and the newest mods\\logs\\ log (if present).
  For a crash, also share %LOCALAPPDATA%\\PAYDAY 2\\crash.txt, if present.

## Contents and limitations

- Rebuilt menu and third-person .model files and two .material_config files.
- Nineteen diffuse/normal .texture files; main.xml registers their new DB paths.
- This repair changes metadata only, not geometry, rigging or textures.
- Custom outfits may use different models; vanilla armor/bags may clip.
- First-person arms, facial animation, masks, ragdolls and co-op compatibility
  are not verified. Test offline first; do not assume multiplayer safety.

## Remove

With the game closed, move lawson_{character} out of assets\\mod_overrides\\.
"""
    return {"main.xml": manifest, "README.txt": readme.encode("utf-8")}


def write_metadata(root: Path, character: str) -> None:
    textures = [p.relative_to(root).as_posix() for p in (root / TEXTURE_DIR).glob("*.texture")]
    for name, data in package_metadata(character, textures).items():
        (root / name).write_bytes(data)


def repair_archive(archive: Path) -> None:
    """Atomically replace only metadata; do not extract or rebuild game assets."""
    character = archive.stem.removeprefix("lawson_")
    prefix = f"lawson_{character}/"
    temporary = None
    try:
        with ZipFile(archive) as source:
            names = source.namelist()
            if not names or any(not n.startswith(prefix) for n in names):
                raise ValueError(f"Unexpected ZIP root in {archive}")
            if len(names) != len(set(names)):
                raise ValueError(f"Duplicate ZIP entries in {archive}")
            textures = [n[len(prefix):] for n in names if n.endswith(".texture")]
            metadata = package_metadata(character, textures)
            with tempfile.NamedTemporaryFile(dir=archive.parent, suffix=".zip", delete=False) as tmp:
                temporary = Path(tmp.name)
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as output:
                output.comment = source.comment
                for info in source.infolist():
                    if info.filename not in {prefix + n for n in metadata}:
                        output.writestr(info, source.read(info))
                for name, data in metadata.items():
                    output.writestr(prefix + name, data)
        temporary.replace(archive)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    for archive in args.archives:
        repair_archive(archive)
        print(f"Repaired metadata: {archive}")


if __name__ == "__main__":
    main()
