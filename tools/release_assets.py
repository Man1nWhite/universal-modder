#!/usr/bin/env python3
"""Publish `dist/` and `references/` as GitHub release assets, and fetch them back.

The packs and the source archives are the heavy half of this repository (about 420 MB in a
working tree, and more than 1.7 GB with their history). They are also the half that changes
bytes rather than lines: a rebuilt pack is a new 9 MB blob, forever, in every clone. So they
live in releases, and the repository keeps the code, the skills, the knowledge base and one
manifest (`assets.json`) that says exactly which bytes are current:

    dist/<character>/<name>.zip            a shipped pack
    dist/<character>/<name>.zip.sha256     its sidecar, written by the builder
    references/<archive>                   the build inputs the builders read

    python tools/release_assets.py plan      what is published, and how big it is
    python tools/release_assets.py write     regenerate assets.json from the tree
    python tools/release_assets.py check     assets.json against the files that are present
    python tools/release_assets.py remote    what GitHub holds against the manifest
    python tools/release_assets.py upload    create the releases, upload what is missing
    python tools/release_assets.py fetch     download into place, verify every sha256
    python tools/release_assets.py verify    check the files against assets.json, offline

`fetch` needs no GitHub token: the repository is public, so the assets come from
`https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>`. `upload` does need `gh`
(any token with `contents: write` on the repository).

The bytes do not change on the way out and back: `fetch` verifies the sha256 the manifest
records, and `upload` compares the size and digest GitHub reports. A pack that is rebuilt is
therefore published by uploading it and running `write`, and a clone is brought up to date by
`fetch` — the repository's own bytes stay small either way.

Exit status is 0 on success and 1 on any mismatch, which is what CI and `make green` use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "assets.json"
VERSION = 1

#: One release per prefix. The tag is stable: a new pack is another asset under the same tag,
#: so a clone does not have to learn a new tag every time the tree changes.
RELEASES = {
    "packs-v1": {
        "title": "PAYDAY 2 packs (dist/)",
        "prefix": "dist",
        "note": (
            "The tracked PAYDAY 2 packs, byte for byte: every `dist/<character>/<name>.zip` and "
            "its `.sha256` sidecar.\n\n"
            "These are build outputs, not source: the repository holds the builders, "
            "`references/` holds their inputs, and `assets.json` names the bytes that are "
            "current. Verify a download with `python tools/release_assets.py fetch`, which "
            "checks every sha256, or by hand: `sha256sum -c <name>.zip.sha256`.\n\n"
            "Nothing here is MIT licensed; see `NOTICE.md` in the repository for what each "
            "asset is and whose it is."
        ),
    },
    "sources-v1": {
        "title": "Build inputs (references/)",
        "prefix": "references",
        "note": (
            "The archives the builders read: converted models, extracted voice sets and the "
            "templates `references/README.md` describes.\n\n"
            "Not MIT licensed either: they are the work of the modellers and voice actors named "
            "in `references/README.md`, and they are here because a build that cannot read them "
            "cannot reproduce a pack. `python tools/release_assets.py fetch` restores them into "
            "`references/` and verifies them."
        ),
    },
}

DEFAULT_REPO = "Man1nWhite/universal-modder"
#: Markdown stays in git: it is documentation (`references/README.md` is the provenance table),
#: it is small, and a clone has to be able to read it without a network.
TRACKED_DOCS = (".md",)
CHUNK = 1 << 20


def die(message: str) -> None:
    print(f"release_assets: {message}", file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------------------- bytes


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


#: the characters GitHub keeps in an asset name; anything else it rewrites to `.`
KEPT = re.compile(r"[^A-Za-z0-9._-]")


def asset_name(rel: str) -> str:
    """`dist/A/B.zip` -> `dist__A__B.zip`; `references/ARIVUS VOICE (PAYDAY 2).zip` -> a safe name.

    GitHub takes only a flat asset name, so the path is encoded in it, and it rewrites every
    character outside `A-Za-z0-9._-` to `.` — a space, a parenthesis and a Cyrillic letter all
    become dots, two different paths can land on one name, and the upload then fails its own
    "did GitHub keep my name" check after the bytes are already up. So the name is made ASCII
    here: the rewrite GitHub would do, plus a short digest of the path when anything had to be
    rewritten, which keeps distinct paths distinct for ever.
    """
    name = rel.replace("/", "__")
    safe = KEPT.sub(".", name)
    if safe == name:
        return name
    stem, dot, ext = safe.rpartition(".")
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}.{ext}" if dot else f"{safe}-{digest}"


def path_of_asset(asset: str) -> str:
    return asset.replace("__", "/")


# --------------------------------------------------------------------------- the manifest


def tracked_paths() -> list[str]:
    """The files git tracks under the published prefixes, or the files on disk without git."""
    paths: set[str] = set()
    git = shutil.which("git")
    if git and (REPO / ".git").exists():
        out = subprocess.run([git, "ls-files", "-z", "--", *RELEASES_PREFIXES], cwd=REPO,
                             capture_output=True, check=True).stdout
        paths = {raw.decode("utf-8", "surrogateescape") for raw in out.split(b"\0") if raw}
    if not paths:
        for prefix in RELEASES_PREFIXES:
            root = REPO / prefix
            if root.is_dir():
                paths |= {p.relative_to(REPO).as_posix() for p in root.rglob("*") if p.is_file()}
    return sorted(paths)


RELEASES_PREFIXES = tuple(spec["prefix"] for spec in RELEASES.values())


def publishable(rel: str) -> bool:
    """Everything under the published prefixes except the Markdown that stays in git."""
    return not rel.endswith(TRACKED_DOCS)


def build_manifest() -> dict:
    releases: dict[str, dict] = {}
    for tag, spec in RELEASES.items():
        files: dict[str, dict] = {}
        for rel in tracked_paths():
            if not rel.startswith(spec["prefix"] + "/") or not publishable(rel):
                continue
            path = REPO / rel
            if not path.is_file():
                die(f"{rel} is tracked but not on disk; `git checkout -- {rel}` first")
            files[rel] = {"asset": asset_name(rel), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        names = [entry["asset"] for entry in files.values()]
        if len(set(names)) != len(names):
            die(f"{tag}: two paths encode to the same asset name")
        releases[tag] = {"title": spec["title"], "note": spec["note"], "files": files}
    return {"version": VERSION, "releases": releases}


def load_manifest(required: bool = True) -> dict | None:
    if not MANIFEST.is_file():
        if required:
            die(f"{MANIFEST.name} is missing: run `python tools/release_assets.py write`")
        return None
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"{MANIFEST.name} is not JSON: {exc}")
    if data.get("version") != VERSION:
        die(f"{MANIFEST.name} is version {data.get('version')}, this tool writes {VERSION}")
    return data


def manifest_entries(manifest: dict, prefix: str | None = None) -> list[tuple[str, str, dict]]:
    """(tag, relative path, entry) for every published file, or only one prefix's."""
    out = []
    for tag, release in manifest["releases"].items():
        for rel, entry in sorted(release["files"].items()):
            if prefix is None or rel.startswith(prefix + "/"):
                out.append((tag, rel, entry))
    return out


# --------------------------------------------------------------------------- http


DEFAULT_BASE = "https://github.com"


def download_url(repo: str, tag: str, asset: str, base: str = DEFAULT_BASE) -> str:
    return f"{base.rstrip('/')}/{repo}/releases/download/{tag}/{urllib.parse.quote(asset)}"


def can_upload(timeout: float = 10.0) -> bool:
    """Release assets are uploaded to uploads.github.com, a host some networks block.

    `api.github.com` still answers for the release and its listing, so a sandbox can create a
    release and not be able to put a byte in it. The check is a request, not a socket: a proxy
    that allows the TCP connect and refuses the request would pass a connect test.
    """
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://uploads.github.com", headers={"User-Agent": "universal-modder"}),
                timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True          # a 4xx from the host still proves the host answers
    except (urllib.error.URLError, OSError):
        return False


def token() -> str:
    """A token for the upload endpoint, from gh's credential store."""
    proc = subprocess.run(["gh", "auth", "token"], cwd=REPO, capture_output=True, text=True,
                          check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        die("`gh auth token` gave no token: log in with `gh auth login` (needs contents: write)")
    return proc.stdout.strip()


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "universal-modder-release-assets"})
    return urllib.request.urlopen(request, timeout=120)


def fetch_one(url: str, dest: Path, entry: dict, force: bool = False) -> str:
    """Download one asset into `dest`, atomically, and verify it. "ok" if it was already there."""
    if dest.is_file() and not force:
        if dest.stat().st_size == entry["bytes"] and sha256_file(dest) == entry["sha256"]:
            return "ok"
    dest.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=".fetch-", dir=dest.parent)
    os.close(handle)
    temp_path = Path(temp)
    try:
        with _open(url) as response, temp_path.open("wb") as out:
            shutil.copyfileobj(response, out, CHUNK)
        digest = sha256_file(temp_path)
        if digest != entry["sha256"]:
            die(f"{dest.relative_to(REPO) if dest.is_relative_to(REPO) else dest}: downloaded sha256 "
                f"{digest[:12]}…, the manifest says {entry['sha256'][:12]}… — {url}")
        if temp_path.stat().st_size != entry["bytes"]:
            die(f"{dest}: downloaded {temp_path.stat().st_size} bytes, the manifest says {entry['bytes']}")
        if dest.exists():
            dest.unlink()
        temp_path.replace(dest)
        return "fetched"
    finally:
        if temp_path.exists():
            temp_path.unlink()


# --------------------------------------------------------------------------- gh


def gh(*args: str, capture: bool = True) -> str:
    if not shutil.which("gh"):
        die("gh is not installed: upload needs it (`gh auth login`); fetch does not")
    proc = subprocess.run(["gh", *args], cwd=REPO, text=True,
                          capture_output=capture, check=False)
    if proc.returncode != 0:
        die(f"gh {' '.join(args[:2])} failed: {(proc.stderr or proc.stdout or '').strip()}")
    return proc.stdout.strip() if capture else ""


ASSET_JQ = '.assets[] | [.name, (.size|tostring), (.digest // ""), (.id|tostring)] | @tsv'


def remote_state(repo: str, tag: str) -> dict[str, dict] | None:
    """asset name -> {"id", "size", "digest"} for one release; None when the release is absent.

    None and {} are different answers: `remote` has to tell a release that was never created
    from one that is there with nothing in it.
    """
    proc = subprocess.run(["gh", "api", f"repos/{repo}/releases/tags/{quote_tag(tag)}",
                           "--jq", ASSET_JQ], cwd=REPO, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    assets = {}
    for line in proc.stdout.splitlines():
        name, size, digest, ident = (line.split("\t") + ["", "", ""])[:4]
        assets[name] = {"id": int(ident or 0), "size": int(size or 0),
                        "digest": digest.removeprefix("sha256:") or None}
    return assets


def release_assets(repo: str, tag: str) -> dict[str, dict]:
    assets = remote_state(repo, tag)
    if assets is None:
        die(f"{tag} is not on GitHub yet: `upload` creates it")
    return assets


def quote_tag(tag: str) -> str:
    return urllib.parse.quote(tag, safe="")


def release_exists(repo: str, tag: str) -> bool:
    return remote_state(repo, tag) is not None


def release_id(repo: str, tag: str) -> int:
    return int(gh("api", f"repos/{repo}/releases/tags/{quote_tag(tag)}", "--jq", ".id"))


def upload_asset(repo: str, tag: str, path: Path, name: str, replace_id: int | None = None) -> None:
    """Upload one file as a release asset under exactly `name`.

    `gh release upload` cannot name an asset anything but the file's basename, and these names
    encode a path (`dist__<character>__<pack>.zip`), so this goes through the API with the name
    in the query string.
    """
    if replace_id is not None:
        gh("api", "--method", "DELETE", f"repos/{repo}/releases/assets/{replace_id}")
    url = (f"https://uploads.github.com/repos/{repo}/releases/"
           f"{release_id(repo, tag)}/assets?name={urllib.parse.quote(name, safe='')}")
    request = urllib.request.Request(
        url, data=path.read_bytes(), method="POST",
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/octet-stream",
                 "Accept": "application/vnd.github+json", "User-Agent": "universal-modder"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            reply = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        die(f"upload of {path.name} failed: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')[:300]}")
    except (urllib.error.URLError, OSError) as exc:
        die(f"upload of {path.name} failed: {exc}\n"
            "  uploads.github.com may be blocked here; run `upload` elsewhere or dispatch "
            "the release-assets workflow")
    if reply.get("name") != name:
        die(f"GitHub stored the asset as {reply.get('name')!r}, not {name!r}; "
            "the manifest would not find it again")


def publish(repo: str, manifest: dict, only: list[str], dry_run: bool) -> dict:
    """Create the releases if needed and upload every asset that is absent or different."""
    result: dict[str, list[str]] = {}
    for tag, release in manifest["releases"].items():
        if only and tag not in only:
            continue
        files = release["files"]
        print(f"{tag}: {len(files)} file(s), {sum(e['bytes'] for e in files.values()) / 1e6:.1f} MB")
        have: dict[str, dict] = {}
        if not release_exists(repo, tag):
            if dry_run:
                print(f"  would create {tag}: {release['title']}")
            else:
                print(f"  creating {tag}")
                gh("api", "--method", "POST", f"repos/{repo}/releases", "-f", f"tag_name={tag}",
                   "-f", f"name={release['title']}", "-f", f"body={release['note']}",
                   # make_latest is a string in the API ("true"/"false"), the other two booleans
                   "-F", "draft=false", "-F", "prerelease=false", "-f", "make_latest=false")
                have = release_assets(repo, tag)
        else:
            have = release_assets(repo, tag)
        for rel, entry in sorted(files.items()):
            remote = have.get(entry["asset"])
            same_size = remote is not None and remote["size"] == entry["bytes"]
            same_digest = remote is not None and (remote["digest"] in (None, entry["sha256"]))
            if remote is not None and same_size and same_digest:
                result.setdefault(tag, []).append(f"present {rel}")
                continue
            action = "would upload" if dry_run else "uploading"
            print(f"  {action} {rel} ({entry['bytes'] / 1e6:.1f} MB)", flush=True)
            if dry_run:
                continue
            upload_asset(repo, tag, REPO / rel, entry["asset"],
                         replace_id=remote["id"] if remote else None)
            result.setdefault(tag, []).append(f"uploaded {rel}")
        if not dry_run:
            after = release_assets(repo, tag)
            for rel, entry in sorted(files.items()):
                remote = after.get(entry["asset"])
                if remote is None or remote["size"] != entry["bytes"]:
                    die(f"{tag}: {entry['asset']} did not arrive (GitHub reports "
                        f"{remote and remote['size']} bytes, the tree has {entry['bytes']})")
                if remote["digest"] and remote["digest"] != entry["sha256"]:
                    die(f"{tag}: {entry['asset']} arrived as {remote['digest'][:12]}…, the tree has "
                        f"{entry['sha256'][:12]}…")
            print(f"  verified {len(files)} asset(s) against the tree")
    return result


# --------------------------------------------------------------------------- commands


def cmd_write(args) -> int:
    manifest = build_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    total = sum(e["bytes"] for _, _, e in manifest_entries(manifest))
    count = len(manifest_entries(manifest))
    print(f"wrote {MANIFEST.name}: {count} file(s), {total / 1e6:.1f} MB across "
          f"{len(manifest['releases'])} release(s)")
    return 0


def cmd_check(args) -> int:
    manifest = load_manifest()
    problems, present, absent = [], 0, 0
    for tag, rel, entry in manifest_entries(manifest):
        path = REPO / rel
        if not path.is_file():
            absent += 1
            continue
        present += 1
        digest = sha256_file(path)
        if digest != entry["sha256"]:
            problems.append(f"{rel}: on disk sha256 {digest[:12]}…, {tag} publishes {entry['sha256'][:12]}… "
                            f"(rebuilt? `upload` it, then `write`)")
    for path in tracked_paths():
        if publishable(path) and not any(rel == path for _, rel, _ in manifest_entries(manifest)):
            problems.append(f"{path}: tracked but missing from {MANIFEST.name} (run `write`)")
    if problems:
        for problem in problems:
            print(f"MISMATCH {problem}", file=sys.stderr)
        die(f"{len(problems)} problem(s) with {MANIFEST.name}")
    print(f"PASS: {MANIFEST.name} matches the {present} file(s) present; {absent} not fetched yet")
    return 0


def cmd_plan(args) -> int:
    manifest = load_manifest()
    for tag, release in manifest["releases"].items():
        files = release["files"]
        print(f"{tag}: {len(files)} file(s), {sum(e['bytes'] for e in files.values()) / 1e6:.1f} MB")
        for rel, entry in sorted(files.items()):
            print(f"  {entry['bytes'] / 1e6:9.1f} MB  {rel}")
    total = sum(e["bytes"] for _, _, e in manifest_entries(manifest))
    print(f"total {len(manifest_entries(manifest))} file(s), {total / 1e6:.1f} MB")
    return 0


def cmd_fetch(args) -> int:
    manifest = load_manifest()
    repo = args.repo or DEFAULT_REPO
    prefix = next((spec["prefix"] for tag, spec in RELEASES.items() if tag == args.tag), None) if args.tag else None
    if args.tag and prefix is None:
        die(f"unknown tag {args.tag}; the manifest has {', '.join(manifest['releases'])}")
    counts = {"ok": 0, "fetched": 0}
    for tag, rel, entry in manifest_entries(manifest, prefix):
        dest = (Path(args.dest) / rel) if args.dest else REPO / rel
        state = fetch_one(download_url(repo, tag, entry["asset"], args.base_url), dest, entry,
                          force=args.force)
        counts[state] += 1
        if state == "fetched":
            print(f"fetched {rel}")
    print(f"PASS: {counts['fetched']} fetched, {counts['ok']} already present and verified")
    return 0


def cmd_verify(args) -> int:
    manifest = load_manifest()
    missing, wrong = [], []
    for tag, rel, entry in manifest_entries(manifest):
        path = (Path(args.dest) / rel) if args.dest else REPO / rel
        if not path.is_file():
            missing.append(rel)
        elif sha256_file(path) != entry["sha256"]:
            wrong.append(rel)
    if wrong:
        for rel in wrong:
            print(f"MISMATCH {rel}: not the published bytes", file=sys.stderr)
    if missing or wrong:
        die(f"{len(missing)} file(s) not fetched, {len(wrong)} not the published bytes"
            " (run `python tools/release_assets.py fetch`)")
    print(f"PASS: {len(manifest_entries(manifest))} file(s) are the published bytes")
    return 0


def cmd_remote(args) -> int:
    """What GitHub holds against the manifest: sizes and digests, without downloading a byte.

    This is the check that has to pass *before* dist/ and references/ stop being tracked: after
    that, a missing asset is a pack no clone can rebuild or even install.
    """
    manifest = load_manifest()
    repo = args.repo or DEFAULT_REPO
    problems: list[str] = []
    ok = 0
    for tag, release in manifest["releases"].items():
        if args.tag and tag != args.tag:
            continue
        have = remote_state(repo, tag)
        if have is None:
            problems.append(f"{tag}: the release does not exist yet (run `upload`)")
            continue
        for rel, entry in sorted(release["files"].items()):
            remote = have.get(entry["asset"])
            if remote is None:
                problems.append(f"{tag}: {rel} is not published yet")
            elif remote["size"] != entry["bytes"]:
                problems.append(f"{tag}: {rel} is {remote['size']} bytes on GitHub, the tree has "
                                f"{entry['bytes']}")
            elif remote["digest"] and remote["digest"] != entry["sha256"]:
                problems.append(f"{tag}: {rel} has sha256 {remote['digest'][:12]}… on GitHub, the "
                                f"tree has {entry['sha256'][:12]}…")
            else:
                ok += 1
    if problems:
        for problem in problems:
            print(f"MISSING {problem}", file=sys.stderr)
        die(f"{len(problems)} problem(s): {ok} asset(s) are published and correct")
    print(f"PASS: all {ok} assets are published, with the manifest's sizes and sha256")
    return 0


def cmd_upload(args) -> int:
    manifest = load_manifest()
    if args.write_first:
        manifest = build_manifest()
        if not args.dry_run:
            MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                encoding="utf-8")
            print(f"wrote {MANIFEST.name}")
    repo = args.repo or DEFAULT_REPO
    tags = [args.tag] if args.tag else list(manifest["releases"])
    if not args.dry_run and not can_upload():
        die("cannot reach uploads.github.com from here, so no asset can be uploaded.\n"
            "  Either run `python tools/release_assets.py upload` on a machine that can "
            "(any ordinary connection),\n"
            "  or dispatch the `release assets` workflow: "
            "gh workflow run release-assets.yml --ref <branch>")
    publish(repo, manifest, tags, args.dry_run)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="release_assets.py", description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("write", help="regenerate assets.json from the tree")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("check", help="assets.json against the files present (no network)")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("plan", help="what is published and how big it is")
    p.set_defaults(func=cmd_plan)

    for name, func, helptext in (("fetch", cmd_fetch, "download into place and verify"),
                                 ("verify", cmd_verify, "check the files against assets.json")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--repo", default=None, help=f"owner/name (default {DEFAULT_REPO})")
        p.add_argument("--tag", default=None, help="only this release")
        p.add_argument("--dest", default=None, help="root to write into (default: the repository)")
        p.add_argument("--base-url", default=DEFAULT_BASE,
                       help=f"where the assets are served from (default {DEFAULT_BASE})")
        p.add_argument("--force", action="store_true", help="download even when a file matches")
        p.set_defaults(func=func)

    p = sub.add_parser("remote", help="what GitHub holds, against the manifest (no download)")
    p.add_argument("--repo", default=None, help=f"owner/name (default {DEFAULT_REPO})")
    p.add_argument("--tag", default=None, help="only this release")
    p.set_defaults(func=cmd_remote)

    p = sub.add_parser("upload", help="create the releases and upload what is missing")
    p.add_argument("--repo", default=None, help=f"owner/name (default {DEFAULT_REPO})")
    p.add_argument("--tag", default=None, help="only this release")
    p.add_argument("--dry-run", action="store_true", help="say what would be uploaded")
    p.add_argument("--write-first", action="store_true", help="regenerate assets.json first")
    p.set_defaults(func=cmd_upload)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
