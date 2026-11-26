"""Paths of shipped packs; ZIP filenames are independent of their internal mod folders.

`dist/` groups a pack by what it replaces. The Miranda family is one folder: the LAS outfits
over Miranda L4D2 and Miranda Romance, the whole-character packs built on them, the DOAXVV
`OfficeSuite` body (a Miranda head on the Secret Report costume) and the voice swap. The packs
that are gone - both Christie outfits, the Busty variant and the four unused head variants - have
no group any more, and asking for one is an error rather than a quiet new folder.
"""
from pathlib import Path

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
    for prefix, group in _GROUPS:
        if base.startswith(prefix):
            return root / "dist" / group / (base + suffix)
    raise ValueError(f"Unknown distribution pack: {name}")
