"""Check a mod folder before you share it: no secrets, no pasted decompiled code, credits present.

    um publish check ./MyMod --game "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Terraria"

FAIL  leaked API keys (FAL_KEY, Anthropic, GitHub, AWS...), .env files
INFO  files byte-identical to files in the game install: game-derived assets are allowed; this
      records their provenance
WARN  decompiler fingerprints in source (FUN_xxxx / DAT_xxxx / sub_XXXX, "// Decompiled with", ILSpy/dnSpy
      headers) - reimplement or reference instead of shipping decompiled code; big engine archives
      (.pak/.bsa/.ba2/.vpk/.rpf/.utoc...) whose file name no README or CREDITS file mentions; absolute
      user paths; no README / credits; fal-generated assets listed in fal_manifest.jsonl without an
      attribution line
Modelled on IW4L's publish-check. It is a lint, not legal advice: game-derived assets may ship at the
owner's call; name their source and keep credits.

Two exemptions keep a clean tree clean, so that a warning still means something when it appears:

- An archive whose file name is named in a README/CREDITS/Markdown file within the folder (or at its
  root) is provenance-recorded: this repository names every archive it carries in
  `references/README.md`, and warning about each one on every run taught people to ignore the check.
- The absolute-user-path rule skips test files (`tests/`, `test_*`, `*_test.py`): a fixture needs a
  realistic home directory to exercise the rule itself (`/home/<user>/saves`), and that is not a leak.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from um.common import die, to_posix

SECRET_PATTERNS = [
    ("fal key", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32}\b")),
    ("FAL_KEY assignment", re.compile(r"FAL_KEY\s*[=:]\s*['\"]?[A-Za-z0-9:_\-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    # project, service-account and admin keys carry - and _ in their body; legacy keys are plain alphanumerics
    ("OpenAI key", re.compile(r"\bsk-(?:(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{32,}|[A-Za-z0-9]{32,})")),
    # classic tokens (ghp_, gho_, ...) and fine-grained personal access tokens (github_pat_)
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})")),
    ("AWS key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS secret", re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{20,}", re.I)),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Discord token", re.compile(r"\b[MN][A-Za-z0-9_-]{23,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b")),
    ("Stripe key", re.compile(r"\b(?:sk_live|rk_live)_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[bpsa]-[A-Za-z0-9-]{10,}\b")),
]
DECOMP_PATTERNS = [
    ("Ghidra auto-name", re.compile(r"\b(?:FUN|DAT|LAB|PTR)_[0-9a-fA-F]{6,}\b")),
    ("IDA auto-name", re.compile(r"\b(?:sub|loc|unk|off|dword|qword)_[0-9A-F]{5,}\b")),
    ("decompiler header", re.compile(r"^\s*(?://|#|--|;)\s*(?:Decompiled with|Decompiler:|ILSpy|dnSpy|JetBrains decompiler)|^#region Assembly ", re.I | re.M)),
]
# A home directory that names a real user, as opposed to the placeholders every "where the game keeps
# its saves" README carries. `C:\Users\<you>`, `%USERPROFILE%` and `$HOME` are not leaks, and flagging
# them teaches people to ignore the check; `kb check` already skipped `<...>` while this did not. The
# Unix prefixes are assembled from parts so that this file does not match its own rule.
_USER_ROOTS = ("/home/", "/Users/")
USER_PATH_RE = re.compile(
    r"[A-Za-z]:\\Users\\([^\\\s\"'`]+)" + "".join(rf"|{re.escape(p)}([^/\s\"'`]+)/" for p in _USER_ROOTS)
)
PLACEHOLDER_RE = re.compile(r"^(?:<[^>]*>|%[^%]+%|\$\{?\w+\}?|\{[^}]*\})$")


def user_path(text: str) -> str | None:
    """The first home-directory path in `text` that names an actual user, or None (placeholders skipped)."""
    for m in USER_PATH_RE.finditer(text):
        name = next(g for g in m.groups() if g)
        if not PLACEHOLDER_RE.match(name):
            return m.group(0)
    return None


CODE_EXT = {".cs", ".c", ".cpp", ".h", ".hpp", ".py", ".lua", ".js", ".ts", ".rs", ".java", ".kt", ".gd", ".rpy", ".psc", ".gml",
            ".hlsl", ".glsl", ".as", ".vb", ".il"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "obj", ".vs", ".idea"}
TEXT_EXT = {".cs", ".c", ".cpp", ".h", ".hpp", ".py", ".lua", ".js", ".ts", ".json", ".toml", ".ini", ".cfg", ".txt", ".md", ".xml",
            ".yaml", ".yml", ".rs", ".java", ".kt", ".gd", ".rpy", ".psc", ".sh", ".ps1", ".bat", ".gml", ".hlsl", ".glsl", ".env"}
ARCHIVE_EXT = {".pak", ".utoc", ".ucas", ".bsa", ".ba2", ".vpk", ".rpf", ".pck", ".assets", ".bundle", ".sga", ".big", ".wad", ".bdt", ".archive", ".7z", ".rar", ".zip", ".tgz", ".tar"}


def _sha1(p: Path) -> str:
    """SHA1 of a file, chunked for large files."""
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_test_path(rel: str) -> bool:
    """A test file or fixture tree: a fake home directory there exercises a rule, it does not leak."""
    parts = rel.split("/")
    return (any(p.lower() in ("tests", "test", "__tests__", "fixtures") for p in parts[:-1])
            or parts[-1].lower().startswith("test_") or parts[-1].lower().endswith(("_test.py", "_test.cs")))


def provenance_notes(files: list[Path], limit_mb: int = 2) -> str:
    """Everything the folder's READMEs, CREDITS and Markdown say, lower-cased, for archive names.

    A big archive is only a warning when nothing in the folder accounts for it: naming the source in
    the README is what the warning asks for, so a mention is the fix.
    """
    notes = []
    for f in files:
        low = f.name.lower()
        if not (low.startswith(("readme", "credits", "notice", "sources")) or f.suffix.lower() in (".md", ".txt")):
            continue
        try:
            if f.stat().st_size > limit_mb << 20:
                continue
            notes.append(f.read_text(errors="replace").lower())
        except OSError:
            continue
    return "\n".join(notes)


def is_suspicious_filename(name: str) -> bool:
    """Filenames that often leak secrets or are accidental redistributions."""
    lower = name.lower()
    return any(lower.endswith(ext) for ext in (".pem", ".key", ".p12", ".pfx")) or lower in (".env", ".env.local")


def check(mod: str, game: str | None = None) -> int:
    root = Path(to_posix(mod))
    if not root.is_dir():
        die(f"not a folder: {root}")
    fails, warns, infos = [], [], []
    files = [p for p in root.rglob("*") if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(root).parts)]
    # game files, matched by size then hash
    if game:
        g = Path(to_posix(game))
        gr, mine = g.resolve(), root.resolve()
        # a mod inside the install (Dwarf Fortress mods/<name>) is not game content: don't match it against itself
        inside = mine.relative_to(gr).parts if mine != gr and mine.is_relative_to(gr) else None
        by_size: dict[int, list[Path]] = {}
        for p in g.rglob("*"):
            if inside and p.relative_to(g).parts[:len(inside)] == inside:
                continue
            if p.is_file():
                try:
                    by_size.setdefault(p.stat().st_size, []).append(p)
                except OSError:
                    pass
        for f in files:
            sz = f.stat().st_size
            if sz < 64 or sz not in by_size:
                continue
            h = _sha1(f)
            for gp in by_size[sz]:
                if _sha1(gp) == h:
                    infos.append(f"game file copied verbatim: {f.relative_to(root).as_posix()}  (== {gp.relative_to(g).as_posix()})")
                    break
    notes = provenance_notes(files) if any(f.suffix.lower() in ARCHIVE_EXT and f.stat().st_size > 5 << 20
                                                 for f in files) else ""
    for f in files:
        rel = f.relative_to(root).as_posix()        # same report on every OS (Windows would print src\Mod.cs)
        name = f.name.lower()
        is_dotenv = name == ".env" or name.startswith(".env.") or name.endswith(".env") or ".env." in name
        if is_dotenv:
            fails.append(f"env file (secrets?): {rel}")
        if f.suffix.lower() in ARCHIVE_EXT and f.stat().st_size > 5 << 20 and name not in notes:
            warns.append(f"large engine archive ({f.stat().st_size >> 20} MB): {rel} - name its source in the README")
        if f.suffix.lower() in TEXT_EXT or is_dotenv:
            try:
                txt = f.read_text(errors="replace")
            except OSError:
                continue
            for label, rx in SECRET_PATTERNS:
                if rx.search(txt):
                    fails.append(f"{label} in {rel}")
            for label, rx in DECOMP_PATTERNS if f.suffix.lower() in CODE_EXT else ():
                m = rx.findall(txt)
                if m:
                    warns.append(f"{label} x{len(m)} in {rel} (e.g. {m[0].strip()!r})")
            if not is_test_path(rel) and (found := user_path(txt)):
                warns.append(f"absolute user path in {rel} (e.g. {found!r})")
    names = {f.name.lower() for f in files}
    if not any(n.startswith("readme") for n in names):
        warns.append("no README (install steps, requirements, credits)")
    manifests = [f for f in files if f.name == "fal_manifest.jsonl"]
    if manifests:
        readmes = [f for f in files if f.name.lower().startswith(("readme", "credits"))]
        if not any("fal" in f.read_text(errors="replace").lower() for f in readmes):
            warns.append("fal-generated assets (fal_manifest.jsonl) but no credit line in README/CREDITS")
    for x in infos:
        print("INFO ", x)
    for x in fails:
        print("FAIL ", x)
    for x in warns:
        print("WARN ", x)
    print(f"{'FAIL' if fails else 'WARN' if warns else 'PASS'}: {len(files)} files, {len(fails)} failures, {len(warns)} warnings")
    return 1 if fails else 0


def main(a):
    raise SystemExit(check(a.mod, a.game))


def register(sub):
    import argparse
    p = sub.add_parser("publish", help="lint a mod folder before sharing (secrets, decompiled code, credits; game assets allowed)",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cs = p.add_subparsers(dest="cmd", metavar="<cmd>")
    q = cs.add_parser("check", help="check a mod folder")
    q.add_argument("mod")
    q.add_argument("--game", help="game install folder, to report game-derived files for provenance")
    q.set_defaults(func=main)
