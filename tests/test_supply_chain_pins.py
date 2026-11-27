"""Every third-party action and the npm package are pinned to an exact version.

A tag is a moving pointer: `actions/checkout@v4` is whatever commit the maintainer moved `v4`
to this morning, and one of the jobs that ran it holds `contents: write`. The same is true of
`node-unrar-js@^2.0.2`, which unpacks the 2B templates every OfficeSuite pack is skinned onto:
a patch release on npm changes the bytes of a tracked pack with no commit in this repository.

So: actions name a 40-character commit with the release in a comment, `package.json` names an
exact version, `package-lock.json` agrees with it, and the extractor's npm fallback installs
from that lockfile (`npm ci`) instead of fetching latest. `dependabot.yml` moves all of it
weekly, as a commit that can be reviewed like any other.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(?:\s+#\s*(\S+))?\s*$", re.M)
SHA = re.compile(r"^[0-9a-f]{40}$")
EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def workflow_uses() -> list[tuple[str, str, str | None]]:
    found: list[tuple[str, str, str | None]] = []
    for workflow in WORKFLOWS:
        for match in USES.finditer(workflow.read_text(encoding="utf-8")):
            found.append((workflow.name, match.group(1), match.group(2)))
    return found


def test_the_scan_sees_the_actions():
    uses = workflow_uses()
    assert len(uses) >= 5, f"only {len(uses)} `uses:` lines found; the scanner is broken"


def test_every_action_is_pinned_to_a_commit():
    loose = [
        f"{name}: {uses}"
        for name, uses, _ in workflow_uses()
        if "@" in uses and not SHA.match(uses.rsplit("@", 1)[1])
    ]
    assert not loose, "actions must name a commit, not a tag:\n  " + "\n  ".join(loose)


def test_every_pinned_action_names_the_release_it_was():
    missing = [f"{name}: {uses}" for name, uses, comment in workflow_uses() if not comment]
    assert not missing, "a pinned action needs `# vX.Y.Z` beside it, or nobody can update it:\n  " + \
        "\n  ".join(missing)
    unstamped = [
        f"{name}: {uses} # {comment}"
        for name, uses, comment in workflow_uses()
        if comment and not re.fullmatch(r"v\d+\.\d+\.\d+", comment)
    ]
    assert not unstamped, "the comment is the release tag (vX.Y.Z):\n  " + "\n  ".join(unstamped)


def test_actions_are_pinned_in_every_workflow():
    workflows_with_uses = {path.name for path in WORKFLOWS
                           if "uses:" in path.read_text(encoding="utf-8")}
    assert workflows_with_uses, "no workflow uses an action any more: check .github/workflows/"


def test_the_npm_package_is_an_exact_version():
    dependencies = json.loads((ROOT / "package.json").read_text())["dependencies"]
    loose = [f"{name}@{spec}" for name, spec in dependencies.items()
             if not EXACT_VERSION.match(spec)]
    assert not loose, f"package.json must pin an exact version, not a range: {loose}"


def test_the_lockfile_agrees_with_package_json():
    manifest = json.loads((ROOT / "package.json").read_text())["dependencies"]
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["dependencies"] == manifest, "package-lock.json is stale"
    for name, version in manifest.items():
        installed = lock["packages"][f"node_modules/{name}"]["version"]
        assert installed == version, f"{name}: package.json {version}, lockfile {installed}"


def test_the_extractor_installs_from_the_lockfile():
    source = (ROOT / "tools" / "pd2-las" / "extract_2b.py").read_text(encoding="utf-8")
    assert '"ci"' in source, "the npm fallback must install the lockfile (`npm ci`)"
    assert not re.search(r'"install",[^)]*"node-unrar-js"\)', source), \
        "the npm fallback must not fetch node-unrar-js by name; that is whatever is latest today"


def test_dependabot_watches_both_ecosystems():
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    for ecosystem in ("github-actions", "npm"):
        assert f"package-ecosystem: {ecosystem}" in text, ecosystem


@pytest.mark.parametrize("workflow", [path.name for path in WORKFLOWS])
def test_every_workflow_still_parses(workflow):
    yaml = pytest.importorskip("yaml")
    document = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text())
    assert "jobs" in document and document["jobs"], workflow
