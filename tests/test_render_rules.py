"""Unified rules for tracked renders under `docs/renders/<project>/<ext>/...`.

Enforces `docs/renders/README.md`:
- `docs/renders/` is the single tracked home for renders and in-game captures;
- legacy tracked render directories (`docs/previews/`, `docs/pd2-las/renders/`) stay gone;
- no tracked image lives elsewhere under `docs/` (other than `docs/media/` branding assets);
- every tracked file under `docs/renders/` (except `docs/renders/README.md`) sits inside
  `<project>/<ext>/...`, with lowercase naming, batch `README.md`, and `manifest.json` for `in-game/`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RENDERS = REPO / "docs" / "renders"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tga", ".tif", ".tiff"}
RENDER_OUTPUT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_SOURCE_EXTS = {
    "model", "mdl", "smd", "obj", "tmc", "dae", "glb", "gltf", "fbx", "nif",
    "texture", "dds", "vtf", "tga", "in-game",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")


def _tracked_under(rel_root: str) -> list[Path]:
    git = shutil.which("git")
    root = REPO / rel_root
    if git and (REPO / ".git").exists():
        out = subprocess.run(
            [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", rel_root],
            cwd=REPO, capture_output=True, check=True,
        ).stdout.decode().split("\0")
        return [REPO / p for p in out if p and (REPO / p).is_file()]
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def validate_render_tree(renders_root: Path, files: list[Path] | None = None) -> list[str]:
    """Return a list of rule violations for files inside `renders_root`."""
    errors: list[str] = []
    if not (renders_root / "README.md").is_file():
        errors.append("missing docs/renders/README.md")
    if files is None:
        files = sorted(p for p in renders_root.rglob("*") if p.is_file())

    image_dirs: dict[Path, list[Path]] = {}
    for path in files:
        rel = path.relative_to(renders_root)
        parts = rel.parts
        if rel.as_posix() == "README.md":
            continue
        if len(parts) < 3:
            errors.append(f"{rel.as_posix()}: must live under <project>/<ext>/... (at least 3 path parts)")
            continue
        project, ext = parts[0], parts[1]
        if DATE_RE.match(project) or not SLUG_RE.match(project):
            errors.append(f"{rel.as_posix()}: invalid <project> folder {project!r} (lowercase slug, no date)")
        if ext not in ALLOWED_SOURCE_EXTS:
            errors.append(
                f"{rel.as_posix()}: invalid <ext> folder {ext!r} "
                f"(expected one of {sorted(ALLOWED_SOURCE_EXTS)})"
            )
        if path.suffix.lower() in IMAGE_EXTS:
            if path.suffix.lower() not in RENDER_OUTPUT_EXTS:
                errors.append(f"{rel.as_posix()}: unsupported render output extension {path.suffix!r}")
            if path.name != path.name.lower():
                errors.append(f"{rel.as_posix()}: render filename must be lowercase")
            image_dirs.setdefault(path.parent, []).append(path)

    for folder in sorted(image_dirs):
        rel_dir = folder.relative_to(renders_root)
        if not (folder / "README.md").is_file():
            errors.append(f"{rel_dir.as_posix()}/: missing batch README.md")
        if rel_dir.parts[1] == "in-game" and not (folder / "manifest.json").is_file():
            errors.append(f"{rel_dir.as_posix()}/: in-game capture batch missing manifest.json")
    return errors


def test_unified_render_rules_and_layout():
    assert (RENDERS / "README.md").is_file()
    readme_text = (RENDERS / "README.md").read_text(encoding="utf-8")
    for token in ("<project>", "<ext>", "in-game/", "README.md", "manifest.json"):
        assert token in readme_text, f"docs/renders/README.md missing {token!r}"

    for retired in ("docs/previews", "docs/pd2-las/renders", "docs/audits/2026-11-09-neck-arm"):
        assert not (REPO / retired).exists(), f"retired render folder still exists: {retired}"

    stray_docs_images = [
        p.relative_to(REPO).as_posix()
        for p in _tracked_under("docs")
        if p.suffix.lower() in IMAGE_EXTS
        and p.relative_to(REPO).parts[:2] not in {("docs", "renders"), ("docs", "media")}
    ]
    assert not stray_docs_images, f"tracked images under docs/ outside docs/renders/ and docs/media/: {stray_docs_images}"

    violations = validate_render_tree(RENDERS, _tracked_under("docs/renders"))
    assert not violations, "docs/renders/ layout violations:\n  " + "\n  ".join(violations)


def test_render_tools_do_not_default_to_retired_folders():
    previews_tool = (REPO / "tools" / "render_mod_previews.py").read_text(encoding="utf-8")
    assert 'ROOT / "docs" / "previews"' not in previews_tool
    assert 'ROOT / "build" / "previews"' in previews_tool
    assert "--unified" in previews_tool

    elbow_tool = (REPO / "tools" / "pd2-las" / "elbow_before_after.py").read_text(encoding="utf-8")
    assert "docs/pd2-las/renders" not in elbow_tool
    assert "build/pd2-las/renders" in elbow_tool


def test_validate_render_tree_catches_invalid_and_accepts_valid(tmp_path):
    root = tmp_path / "renders"
    root.mkdir()
    (root / "README.md").write_text("# Renders\n", encoding="utf-8")

    # valid offline model batch + valid in-game batch
    model_dir = root / "christie" / "model" / "base"
    model_dir.mkdir(parents=True)
    (model_dir / "README.md").write_text("# Christie\n", encoding="utf-8")
    (model_dir / "christie_body_front.png").write_bytes(b"png")

    ingame_dir = root / "honoka" / "in-game" / "2026-11-15"
    ingame_dir.mkdir(parents=True)
    (ingame_dir / "README.md").write_text("# Honoka\n", encoding="utf-8")
    (ingame_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (ingame_dir / "honoka_menu_front.png").write_bytes(b"png")

    assert validate_render_tree(root) == []

    # invalid cases: loose file, missing ext, combined ext, date as project, uppercase file, missing manifest
    (root / "loose.png").write_bytes(b"x")
    (root / "christie" / "missing_ext.png").write_bytes(b"x")
    bad_ext = root / "christie" / "mdl-vvd-vtx"
    bad_ext.mkdir(parents=True)
    (bad_ext / "README.md").write_text("# bad\n", encoding="utf-8")
    (bad_ext / "Christie_Front.png").write_bytes(b"x")
    bad_proj = root / "2026-11-15" / "model"
    bad_proj.mkdir(parents=True)
    (bad_proj / "a_front.png").write_bytes(b"x")
    bad_ingame = root / "christie" / "in-game" / "menu"
    bad_ingame.mkdir(parents=True)
    (bad_ingame / "README.md").write_text("# missing manifest\n", encoding="utf-8")
    (bad_ingame / "shot_front.png").write_bytes(b"x")

    errors = "\n".join(validate_render_tree(root))
    assert "loose.png" in errors
    assert "missing_ext.png" in errors
    assert "mdl-vvd-vtx" in errors
    assert "Christie_Front.png" in errors
    assert "2026-11-15" in errors
    assert "manifest.json" in errors
    assert "missing batch README.md" in errors


def test_new_ingame_capture_manifests_match_images():
    """Every in-game capture batch's manifest.json matches the archived PNGs' dimensions, sizes, and SHA-256."""
    import hashlib
    import json
    from PIL import Image

    manifests = sorted(RENDERS.rglob("manifest.json"))
    assert len(manifests) >= 3, manifests
    for manifest_path in manifests:
        directory = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest.get("screenshots") or manifest.get("captures") or manifest.get("files")
        assert entries, f"{manifest_path}: no capture entries"
        for shot in entries:
            fname = shot.get("file") or shot.get("archived") or shot.get("name")
            data = (directory / fname).read_bytes()
            assert len(data) == shot["bytes"], fname
            assert hashlib.sha256(data).hexdigest() == shot["sha256"], fname
            with Image.open(directory / fname) as image:
                if "width" in shot and "height" in shot:
                    assert image.size == (shot["width"], shot["height"]), fname


def test_every_tracked_model_render_sheet_belongs_to_render_mod_previews():
    """Prevent orphan model renders (like the removed Christie_LAS_Slim sheet) from lingering after a pack is deleted."""
    render_tools = (REPO / "tools" / "render_mod_previews.py").read_text(encoding="utf-8")
    extra_tool = REPO / "tools" / "render_clover_honoko.py"
    if extra_tool.is_file():
        render_tools += "\n" + extra_tool.read_text(encoding="utf-8")
    for rel_path in _tracked_under("docs/renders"):
        rel = rel_path.as_posix() if hasattr(rel_path, "as_posix") else str(rel_path)
        parts = rel.split("/")
        if len(parts) >= 4 and parts[2] == "model" and rel.endswith(".png"):
            sub = "/".join(parts[1:])
            assert sub in render_tools, f"{rel} is not produced by any render tool under tools/"
