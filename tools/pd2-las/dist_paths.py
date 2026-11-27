"""Paths of shipped packs; ZIP filenames are independent of their internal mod folders.

`tools/pd2-las/packs.py` is the table this reads: pack name → `dist/` folder. `dist/` groups a
pack by what it replaces - the Miranda family in `Miranda/` (the LAS outfits' whole-character
packs, the DOAXVV `OfficeSuite` body and the voice swap), their source outfits in
`Miranda_L4D2/` and `Miranda_Romance/`, and `Geralt/` and `Arivus/` for those two characters.
A retired pack is not in the table, so asking for one raises instead of quietly naming a
folder that does not exist; `_RENAMED` still maps the builder names older than the packs.
"""
from pathlib import Path

from packs import GROUPS

#: builder names older than the pack names, still honoured by the builders that write them
_RENAMED = {
    "Miranda_LAS.zip": "Miranda_L4D2_LAS.zip",
    "lawson_las.zip": "Miranda_Romance_LAS.zip",
}

#: longest prefix first: `Miranda_Romance_over_Hila` must not be read as a `Miranda_Romance_` pack
_GROUPS = (
    ("Miranda_Romance_over_Hila", "Miranda"),
    ("Miranda_L4D2_over_Hila", "Miranda"),
    ("Miranda_Lawson_VO", "Miranda"),
    ("OfficeSuite", "Miranda"),
    ("Miranda_L4D2_", "Miranda_L4D2"),
    ("Miranda_Romance_", "Miranda_Romance"),
    ("Geralt_", "Geralt"),
    ("Arivus_", "Arivus"),
)


def dist_path(root: Path, name: str) -> Path:
    """Locate a pack or sidecar by basename, including legacy builder names."""
    suffix = ".sha256" if name.endswith(".sha256") else ""
    base = name.removesuffix(suffix) if suffix else name
    base = _RENAMED.get(base, base)
    if base in GROUPS:
        return root / "dist" / GROUPS[base] / (base + suffix)
    for prefix, group in _GROUPS:
        if base.startswith(prefix):
            return root / "dist" / group / (base + suffix)
    raise ValueError(f"Unknown distribution pack: {name}")
