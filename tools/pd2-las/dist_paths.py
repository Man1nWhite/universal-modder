"""Paths of shipped packs; ZIP filenames are independent of their internal mod folders."""
from pathlib import Path

_RENAMED = {
    "Miranda_LAS.zip": "Miranda_L4D2_LAS.zip",
    "Miranda_Busty_LAS.zip": "Miranda_L4D2_Busty_LAS.zip",
    "lawson_las.zip": "Miranda_Romance_LAS.zip",
}


def dist_path(root: Path, name: str) -> Path:
    """Locate a pack or sidecar by basename, including legacy builder names."""
    suffix = ".sha256" if name.endswith(".sha256") else ""
    base = name.removesuffix(suffix) if suffix else name
    base = _RENAMED.get(base, base)
    if base.startswith("Miranda_L4D2_"):
        group = "Miranda_L4D2"
    elif base.startswith("Miranda_Romance_"):
        group = "Miranda_Romance"
    elif base.startswith("Christie_"):
        group = "Christie"
    elif base.startswith(("Honoko", "OfficeSuite")):
        group = "Honoka"
    elif base.startswith("Geralt_"):
        group = "Geralt"
    elif base.startswith("Arivus_"):
        group = "Arivus"
    elif base.startswith("Miranda_Lawson_VO"):
        group = "Hila"
    else:
        raise ValueError(f"Unknown distribution pack: {name}")
    return root / "dist" / group / (base + suffix)
