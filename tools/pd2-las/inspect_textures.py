"""What a Source-asset addon actually contains — and whether its textures decode.

`inspect_gma.py` answers a *model* question from a `.gma` alone. This answers the
two questions that come after it, and the ones a vanilla `.vpk`/`.zip` addon
raises just as often:

1. **Is the mesh textured, or is there a bodygroup whose texture is missing?**
   Every material the models name is resolved against the addon's own files
   (`.vmt`, then the `.vtf` that VMT actually points at, following `$basetexture`
   inside the addon before falling back to the same folder). What comes back is
   present / missing, with the texture's real dimensions and mip count, because a
   512² placeholder where the render expects 2048² is a different problem from a
   pink checkerboard.
2. **Does the texture decode at all?** A VTF that parses is not the same as a VTF
   that opens: DXT5 with a truncated mip chain parses fine and renders black in
   Blender (the symptom that sends people hunting for the wrong bug).

Both are read-only and in-memory. Nothing is written to disk and nothing is
rendered: the addon is licensed content that must not enter the repository.

Run it on the same files `inspect_gma.py` takes — a `.gma`, or a raw Source
`.vpk`/`.zip` from a download:

    python tools/pd2-las/inspect_textures.py path/to/870161699.gma
    python tools/pd2-las/inspect_textures.py addon.gma --json report.json

Optional cross-check: if the `sourcepp` package (pip install sourcepp) is
available, every VTF it can open is decoded a second time and compared with
`vtf.py`. Disagreement is reported, not swallowed — two independent decoders
agreeing is the only cheap proof either is right.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vtf as vtfmod  # noqa: E402
from gma import VTX_SUFFIXES, GmaArchive, GmaError  # noqa: E402
from source_model import SourceModelError, load_model  # noqa: E402
from vpk import VpkArchive, VpkError  # noqa: E402

_EXT = {".gma": "gma", ".vpk": "vpk", ".zip": "zip"}

#: "Materials" a compiled MDL names that are not drawable materials: `phy` is the
#: physics model's placeholder, `__vphys` the collision hull. They never have a
#: VMT, so reporting them as untextured would be a false alarm on every model.
_ENGINE_ONLY = {"phy", "__vphys", "breakable_surf", "player_shared", "nodraw"}


# --------------------------------------------------------------- containers


class _Container:
    """Uniform read interface over `.gma`, `.vpk`, `.zip` and folder addons."""

    def __init__(self, paths: list[str], read, name: str, meta: dict | None = None):
        self._paths = paths
        self._read = read
        self.name = name
        self.meta = meta or {}
        self._lower = {p.lower(): p for p in paths}

    @property
    def paths(self) -> list[str]:
        return self._paths

    def has(self, path: str) -> bool:
        return path.lower() in self._lower

    def read(self, path: str) -> bytes:
        real = self._lower.get(path.lower())
        if real is None:
            raise KeyError(path)
        return self._read(real)

    def find(self, *suffixes: str) -> list[str]:
        want = tuple(s.lower() for s in suffixes)
        return [p for p in self._paths if p.lower().endswith(want)]


def open_container(path: Path) -> _Container:
    """Open a `.gma`, a single-file `.vpk`, a `.zip` of either, or a folder.

    The folder case is not a convenience: a Garry's Mod addon on disk *is* a
    folder (`addons/<name>/…`, or a workshop item someone has unpacked), and
    the legacy download format for the same content is a zip with one top
    folder inside it. Both are stripped of that wrapper so `materials/…` paths
    resolve the same way they do inside a `.gma`.
    """
    if path.is_dir():
        return open_folder(path)
    kind = _EXT.get(path.suffix.lower())
    if kind == "gma":
        arc = GmaArchive(path.read_bytes(), name=str(path))
        return _Container([e.path for e in arc.entries], arc.read, str(path))
    if kind == "vpk":
        arc = VpkArchive(path.read_bytes(), name=str(path))
        return _Container([e.path for e in arc.entries], arc.read, str(path))
    if kind == "zip":
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            inner = [n for n in names if n.lower().endswith((".gma", ".vpk"))]
            if len(inner) == 1:
                return open_nested(path, inner[0])
            # Read through the zip while it is open: handing its `read` out
            # would fail later with "attempt to read ZIP archive that was
            # already closed". Whole-archive reads are the norm here anyway.
            strip = _strip_wrapper_folder(names)
            members = strip or {n: n for n in names}
            bodies = {name: zf.read(member) for name, member in members.items()}
            read = bodies.__getitem__
            return _Container(list(bodies), read, str(path), _read_meta(read, list(bodies)))
    raise ValueError(f"{path}: expected a .gma, .vpk, .zip, or an addon folder")


#: A wrapper folder around an addon is named after the addon; these are the
#: names that are content roots instead, so a "folder" called `materials` is
#: the addon itself and must not be stripped.
_CONTENT_ROOTS = {
    "addons", "bin", "cfg", "data", "lua", "maps", "materials", "models",
    "particles", "resource", "scenes", "scripts", "sound",
}


def _top_folder(names: list[str]) -> str | None:
    """The single folder every path sits under, when that is a wrapper."""
    firsts = {n.split("/", 1)[0] for n in names}
    if len(firsts) != 1:
        return None
    top = firsts.pop()
    if any("/" not in n for n in names):  # a file at the root: not a wrapper
        return None
    return None if top.lower() in _CONTENT_ROOTS else top


def _strip_wrapper_folder(names: list[str]) -> dict[str, str]:
    """Map each zip member to the addon-relative path inside a wrapper folder."""
    top = _top_folder(names)
    if top is None:
        return {}
    return {n[len(top) + 1:]: n for n in names}


def open_folder(root: Path) -> _Container:
    """An unpacked addon folder: `addons/<name>/` or an extracted workshop item."""
    files = [p for p in sorted(root.rglob("*")) if p.is_file()]
    rel = {str(p.relative_to(root)).replace("\\", "/"): p for p in files}
    top = _top_folder(list(rel))
    if top is not None:
        rel = {name[len(top) + 1:]: path for name, path in rel.items()}

    def read(name: str) -> bytes:
        return rel[name].read_bytes()

    meta = _read_meta(read, list(rel))
    return _Container(list(rel), read, str(root), meta)


#: `addoninfo.txt` has two spellings in the wild: Garry's Mod's KeyValues form
#: (`"name" "…"`, `"tags" "fun"`) and the older Valve addon form L4D2 addons
#: still ship (`AddonTitle "…"`, `AddonDescription "…"`). Both are `key "value"`
#: pairs with an optional quote on the key, so one regex covers them.
_ADDONINFO_KEY = re.compile(r'(?:"([A-Za-z0-9_]+)"|([A-Za-z0-9_]+))\s+"([^"]*)"')

_ADDONINFO_FIELDS = {
    "name": "name",
    "addontitle": "name",
    "type": "type",
    "description": "description",
    "addondescription": "description",
    "author": "author",
    "addonauthor": "author",
}


def parse_addoninfo(text: str) -> dict:
    """The `addoninfo.txt` keys worth reporting (legacy, pre-gmad folder addons)."""
    meta: dict = {}
    for quoted, bare, value in _ADDONINFO_KEY.findall(text):
        key = (quoted or bare).lower()
        value = value.strip()
        if not value:
            continue
        if key in _ADDONINFO_FIELDS:
            meta.setdefault(_ADDONINFO_FIELDS[key], value)
        elif key == "tags":
            meta.setdefault("tags", []).append(value)
    return meta


def parse_addon_json(text: str) -> dict:
    """The `addon.json` keys `gmad` reads: title, type, tags, description."""
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(blob, dict):
        return {}
    meta: dict = {}
    for source, target in (("title", "name"), ("name", "name")):
        if blob.get(source) and target not in meta:
            meta[target] = str(blob[source])
    for key in ("type", "description"):
        if blob.get(key):
            meta[key] = str(blob[key])
    tags = blob.get("tags")
    if isinstance(tags, str):
        tags = [tags]
    if isinstance(tags, list) and tags:
        meta["tags"] = [str(t) for t in tags]
    return meta


def _read_meta(read, names: list[str]) -> dict:
    """Title/type/tags from `addoninfo.txt` or `addon.json`, when present.

    A `.gma` carries this in its header; a folder addon carries it in one of
    those two files, and knowing what the addon claims to be is the cheapest
    cross-check against what its files say.
    """
    lower = {n.lower(): n for n in names}
    for wanted, parser in (
        ("addoninfo.txt", parse_addoninfo),
        ("addon.json", parse_addon_json),
    ):
        real = lower.get(wanted)
        if real is None:
            continue
        try:
            meta = parser(read(real).decode("utf-8", "replace"))
        except (OSError, KeyError, UnicodeDecodeError):
            continue  # metadata is a nicety; a bad one must not stop the report
        if meta:
            return meta
    return {}


def open_nested(zip_path: Path, inner: str) -> _Container:
    """Open the single `.gma`/`.vpk` member of a zip without unpacking to disk."""
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(inner)
    if inner.lower().endswith(".gma"):
        arc = GmaArchive(data, name=f"{zip_path}!{inner}")
    else:
        arc = VpkArchive(data, name=f"{zip_path}!{inner}")
    return _Container([e.path for e in arc.entries], arc.read, f"{zip_path}!{inner}")


# ------------------------------------------------------------------ VMT/VTF

#: `$basetexture "models\foo\bar"` (quoted), then the unquoted spelling.
#: VMTs are KeyValues with a `patch`/`insert` wrapper, so this scans the text
#: rather than parsing the tree — the key can appear at any nesting depth.
_BASETEXTURE = re.compile(r'\$basetexture\s+"([^"]+)"', re.IGNORECASE)
#: `$bumpmap`, `$phongexponenttexture`, `$lightwarptexture`, … — any `$…` key
#: whose value looks like a texture path.
_ANY_TEX_KEY = re.compile(r'(\$[a-z0-9_]+)\s+"([^"\\/\s]+(?:[\\/][^"]+)?)"', re.IGNORECASE)
_BASE_ALT = re.compile(r"\$basetexture\s+([^\s\"]+)", re.IGNORECASE)
#: Every other `$...texture`/`$bumpmap` reference, so a normal map is not
#: reported as an unreferenced orphan.
_TEXTURE_KEY = re.compile(r'(\$[a-z0-9_]*texture[a-z0-9_]*)\s+"([^"]+)"', re.IGNORECASE)
#: `EyeRefract` materials (every Source character's eyeballs) name their colour
#: map `$iris` or `$corneatexture`, so `$basetexture` alone reads as "untextured".
_IRIS_KEY = re.compile(r'\$(?:iris|corneatexture)\s+"([^"]+)"', re.IGNORECASE)


def parse_texture_refs(text: str) -> list[str]:
    """Every texture a VMT points at (`$basetexture`, `$bumpmap`, `$iris`, …).

    KeyValues here nest inside `patch { insert { … } }`, so the text is scanned
    instead of parsed as a tree; an engine path like
    `Engine/eye-reflection-cubemap-` is dropped because it is not an addon file.
    """
    refs = [m.group(1).strip().replace("\\", "/") for m in _IRIS_KEY.finditer(text)]
    for m in _ANY_TEX_KEY.finditer(text):
        value = m.group(2).strip()
        if "engine/" in value.lower() or not value:
            continue
        refs.append(value.replace("\\", "/"))
    return refs


def parse_basetexture(text: str) -> str | None:
    """Pull `$basetexture` out of a VMT without a KeyValues dependency."""
    for pattern in (_BASETEXTURE, _BASE_ALT):
        m = pattern.search(text)
        if m:
            return m.group(1).strip().replace("\\", "/")
    m = _IRIS_KEY.search(text)
    return m.group(1).strip().replace("\\", "/") if m else None


@dataclass
class TextureReport:
    vmt: str
    basetexture: str | None
    vtf_path: str | None
    present: bool
    width: int = 0
    height: int = 0
    mips: int = 0
    fmt: str = ""
    decodes: bool | None = None  # None = no PNG decoder installed to ask
    error: str = ""
    sourcepp_agrees: bool | None = None


def resolve_texture(container: _Container, vmt_path: str) -> TextureReport:
    """Follow a `.vmt` to its texture inside the container and decode it."""
    rep = TextureReport(vmt=vmt_path, basetexture=None, vtf_path=None, present=False)
    try:
        vmt_text = container.read(vmt_path).decode("latin1")
    except KeyError:
        rep.error = "vmt unreadable"
        return rep
    base = parse_basetexture(vmt_text)
    rep.basetexture = base
    if not base:
        rep.error = "no $basetexture"
        return rep

    # materials/…/x.vmt pointing at "models/foo/bar" -> materials/models/foo/bar.vtf,
    # then the same folder as the VMT (the common authored shortcut).
    candidates = [f"materials/{base}.vtf"]
    parent = vmt_path.rsplit("/", 1)[0] if "/" in vmt_path else ""
    base_name = base.rsplit("/", 1)[-1]
    if parent:
        candidates.append(f"{parent}/{base_name}.vtf")
    candidates.append(f"{base}.vtf")

    for cand in candidates:
        if container.has(cand):
            rep.vtf_path = cand
            break
    if not rep.vtf_path:
        # last resort: is there a .vtf with that basename anywhere?
        hits = container.find(f"/{base_name}.vtf")
        rep.vtf_path = hits[0] if hits else None
    if not rep.vtf_path:
        return rep

    rep.present = True
    try:
        img = vtfmod.parse_vtf(container.read(rep.vtf_path))
    except (vtfmod.VtfError, KeyError) as exc:
        rep.error = f"{type(exc).__name__}: {exc}"
        return rep
    rep.width, rep.height = img.width, img.height
    rep.mips = img.mipmap_count
    rep.fmt = vtfmod.FORMAT_NAMES.get(img.highres_format, str(img.highres_format))
    rep.decodes = _decodes(container.read(rep.vtf_path))
    if rep.decodes is False:
        rep.error = rep.error or "decoder refused the image data"
    rep.sourcepp_agrees = _sourcepp_check(container.read(rep.vtf_path), img)
    return rep


def _decodes(raw: bytes) -> bool | None:
    """Does `vtf.py` get pixels out of it (not just a header)?

    `None` when the PNG step cannot run because Pillow is absent: a missing
    optional dependency must not be reported as a broken texture, which is the
    one wrong answer that sends someone hunting through their VMTs.
    """
    try:
        png = vtfmod.to_png(vtfmod.parse_vtf(raw))
    except ImportError:
        return None
    except Exception:  # noqa: BLE001 - any decoder failure means "no"
        return False
    return png[:8] == b"\x89PNG\r\n\x1a\n"


def _sourcepp_check(raw: bytes, ours) -> bool | None:
    """Second opinion from `sourcepp`, if it is installed. None = not available."""
    try:
        from sourcepp import vtfpp  # noqa: PLC0415 - optional dependency
    except ImportError:
        return None
    try:
        theirs = vtfpp.VTF(raw)
        rgba = theirs.get_image_data_as_rgba8888(0, 0, 0, 0)
    except Exception:  # noqa: BLE001 - a decoder that raises is a disagreement
        return False
    return bool(rgba) and (theirs.width, theirs.height) == (ours.width, ours.height)


# ------------------------------------------------------------------ report


def inspect(path: Path) -> dict:
    container = open_container(path)
    report: dict = {
        "file": str(path),
        "container": container.name,
        "addon": container.meta,
        "file_count": len(container.paths),
        "by_extension": dict(
            Counter(
                p.rsplit(".", 1)[-1].lower() if "." in p else "(none)"
                for p in container.paths
            ).most_common()
        ),
        "models": [],
        "textures": [],
        "orphan_textures": [],
        "errors": [],
    }

    used: set[str] = set()
    for triple in _model_triples(container):
        entry: dict = {"paths": list(triple), "materials": [], "missing": []}
        try:
            model = load_model(*(container.read(p) for p in triple))
        except (SourceModelError, KeyError) as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            report["models"].append(entry)
            continue
        entry["bodygroups_skipped"] = model.skipped_bodygroup_models
        here = triple[0].rsplit("/", 1)[0] if "/" in triple[0] else ""
        for material in model.materials:
            stem = material.replace("\\", "/").rsplit("/", 1)[-1]
            if stem.lower() in _ENGINE_ONLY:
                entry["materials"].append(
                    {"material": material, "vmt": None, "texture": None,
                     "engine_only": True}
                )
                continue
            vmt = _find_vmt(container, stem, here)
            if vmt is None:
                entry["materials"].append(
                    {"material": material, "vmt": None, "texture": None}
                )
                entry["missing"].append(material)
                continue
            used.add(vmt.lower())
            for ref in parse_texture_refs(container.read(vmt).decode("latin1")):
                name = ref.rsplit("/", 1)[-1]
                for cand in (f"materials/{ref}.vtf", f"{here_vmt(vmt)}/{name}.vtf"):
                    if container.has(cand):
                        used.add(cand.lower())
            tex = resolve_texture(container, vmt)
            if tex.vtf_path:
                used.add(tex.vtf_path.lower())
            entry["materials"].append(
                {
                    "material": material,
                    "vmt": vmt,
                    "texture": tex.vtf_path,
                    "size": [tex.width, tex.height],
                    "mips": tex.mips,
                    "format": tex.fmt,
                    "decodes": tex.decodes,
                    "error": tex.error,
                    "sourcepp_agrees": tex.sourcepp_agrees,
                }
            )
            if not tex.present or tex.decodes is False:
                entry["missing"].append(material)
            report["textures"].append(tex.__dict__)
        report["models"].append(entry)

    report["orphan_textures"] = [
        p for p in container.find(".vtf") if p.lower() not in used
    ]
    return report


def here_vmt(vmt_path: str) -> str:
    return vmt_path.rsplit("/", 1)[0] if "/" in vmt_path else ""


def _model_triples(container: _Container) -> list[tuple[str, str, str]]:
    out = []
    for mdl in container.find(".mdl"):
        stem = mdl[:-4]
        vvd = stem + ".vvd"
        if not container.has(vvd):
            continue
        for vtx in (stem + suffix for suffix in VTX_SUFFIXES):
            if container.has(vtx):
                out.append((mdl, vvd, vtx))
                break
    return out


def _find_vmt(container: _Container, stem: str, model_dir: str) -> str | None:
    """A model's material stem -> the `.vmt` inside the addon."""
    for cand in (f"materials/models/{stem}.vmt", f"materials/{stem}.vmt"):
        if container.has(cand):
            return cand
    if model_dir:
        guess = model_dir.replace("models/", "materials/models/", 1) + f"/{stem}.vmt"
        if container.has(guess):
            return guess
    hits = container.find(f"/{stem}.vmt", f"materials/{stem}.vmt")
    return hits[0] if hits else None


def render(report: dict) -> str:
    meta = report.get("addon") or {}
    lines = [f"container: {report['container']}"]
    if meta:
        claimed = ", ".join(
            f"{key} {value!r}" for key, value in meta.items() if key != "description"
        )
        lines.append(f"addon    : {claimed}")
    lines += [
        f"files    : {report['file_count']} — "
        + ", ".join(f"{k} x{v}" for k, v in report["by_extension"].items()),
        "",
    ]
    for i, m in enumerate(report["models"], 1):
        lines.append(f"[{i}] {m['paths'][0]}")
        if "error" in m:
            lines.append(f"    unreadable: {m['error']}")
            continue
        if not m["materials"]:
            lines.append("    no materials declared")
        for mat in m["materials"]:
            if mat.get("engine_only"):
                continue
            if not mat["vmt"]:
                lines.append(f"    ✗ {mat['material']}: no .vmt in the addon")
                continue
            if not mat.get("texture"):
                lines.append(
                    f"    ✗ {mat['material']}: {mat['vmt']} -> "
                    f"{mat['error'] or 'no texture'}"
                )
                continue
            size = "×".join(str(v) for v in mat["size"])
            if mat["decodes"] is None:
                mark, note = "?", "  [decoded: not checked — Pillow is not installed]"
            else:
                mark, note = ("✓" if mat["decodes"] else "✗"), ""
            agree = ""
            if mat["sourcepp_agrees"] is True:
                agree = " [sourcepp agrees]"
            elif mat["sourcepp_agrees"] is False:
                agree = " [SOURCEPP DISAGREES]"
            lines.append(
                f"    {mark} {mat['material']}: {mat['vmt']} -> {mat['texture']} "
                f"({size}, {mat['mips']} mips, {mat['format']}){agree}{note}"
            )
            if mat["error"]:
                lines.append(f"        {mat['error']}")
        lines.append("")
    if report["orphan_textures"]:
        lines.append(
            f"textures no model references: {len(report['orphan_textures'])} "
            f"(e.g. {', '.join(report['orphan_textures'][:4])})"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("addon", type=Path, help=".gma, .vpk or .zip (of either)")
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    args = ap.parse_args(argv)
    try:
        report = inspect(args.addon)
    except (GmaError, VpkError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render(report))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
