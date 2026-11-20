"""Exercise the release shell steps locally: no builds of game assets and no GitHub calls."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
from pack_checksum import sidecar_path, write_checksum  # noqa: E402

ROMANCE = Path("dist/Miranda_Romance/Miranda_Romance_LAS.zip")
L4D2 = Path("dist/Miranda_L4D2/Miranda_L4D2_LAS.zip")
VERIFY = "verify the checked-in pack checksums"
BUILD = "build the pack"
COMPARE = "verify the build matches the tracked pack"
PUBLISH = "publish to the GitHub release"
TAG = "lawson-las-v3"
VALID_NOTES = "Notes for the release\n\n<!-- pack_version: 0.1.2 -->\n"


@pytest.fixture
def release_checkout(tmp_path):
    steps = yaml.safe_load((REPO / ".github/workflows/lawson-las.yml").read_text())["jobs"]["build"]["steps"]
    for rel in (ROMANCE, L4D2):
        pack = tmp_path / rel
        pack.parent.mkdir(parents=True)
        pack.write_bytes(f"original {pack.name}".encode())
        write_checksum(pack, root=tmp_path)
    checksum = "tools/pd2-las/pack_checksum.py"
    (tmp_path / checksum).parent.mkdir(parents=True)
    shutil.copyfile(REPO / checksum, tmp_path / checksum)
    builder = tmp_path / "tools/pd2-port/build_las_pack.py"
    (builder.parent / "releases").mkdir(parents=True)
    (tmp_path / "builder-input.bin").write_bytes((tmp_path / ROMANCE).read_bytes())
    builder.write_text("""\
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--version', default='default')
args = parser.parse_args()
Path('built-version').write_text(args.version)
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_bytes(Path('builder-input.bin').read_bytes())
""")
    gh = tmp_path / "fake-bin/gh"
    gh.parent.mkdir()
    gh.write_text("#!/usr/bin/env python3\n" + """\
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert args[0] == 'release'
with open(Path(os.environ['MOCK_ROOT']) / 'gh-args.jsonl', 'a') as handle:
    handle.write(json.dumps(args) + '\\n')
if args[1] == 'view':
    sys.exit(0 if os.environ.get('MOCK_EXISTING') == 'yes' else 1)
if args[1] == 'create':
    assert Path(args[args.index('--notes-file') + 1]).is_file()
""")
    gh.chmod(0o755)

    def run(*, ref_name=TAG, tag=True, existing=False):
        env = {**os.environ, "PATH": os.pathsep.join((str(gh.parent), str(Path(sys.executable).parent), os.environ["PATH"])),
               "GITHUB_REF": f"refs/{'tags' if tag else 'heads'}/{ref_name}", "GITHUB_REF_NAME": ref_name,
               "NOTES": f"tools/pd2-port/releases/{ref_name}.md", "MOCK_ROOT": str(tmp_path),
               "MOCK_EXISTING": "yes" if existing else "no"}
        for step in steps:
            name = step.get("name")
            if name not in {VERIFY, BUILD, COMPARE, PUBLISH} or (name == PUBLISH and not tag):
                continue
            proc = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]],
                                  cwd=tmp_path / step.get("working-directory", "."), env=env,
                                  capture_output=True, text=True)
            if proc.returncode:
                return name, proc
        return None

    return tmp_path, run


def test_release_checks_the_original_before_the_builder_can_repair_it(release_checkout):
    root, run = release_checkout
    pack = root / ROMANCE
    pack.write_bytes(b"corrupted original")
    name, proc = run(ref_name="main", tag=False)
    assert name == VERIFY and "does not match its checksum" in proc.stderr
    assert not (root / "built-version").exists()
    assert pack.read_bytes() == b"corrupted original"


def test_release_compares_scratch_bytes_instead_of_overwriting_dist(release_checkout):
    root, run = release_checkout
    pack = root / ROMANCE
    before = (pack.read_bytes(), sidecar_path(pack).read_bytes())
    (root / "builder-input.bin").write_bytes(b"different build")
    name, _ = run(ref_name="main", tag=False)
    assert name == COMPARE
    assert (root / "built-version").read_text() == "default"
    assert (pack.read_bytes(), sidecar_path(pack).read_bytes()) == before
    assert not (root / "gh-args.jsonl").exists()


@pytest.mark.parametrize("notes", [None, "<!-- pack_version: invalid -->\n", VALID_NOTES + "<!-- pack_version: nope -->\n"])
def test_tag_requires_one_valid_version_even_if_release_exists(release_checkout, notes):
    root, run = release_checkout
    if notes is not None:
        (root / f"tools/pd2-port/releases/{TAG}.md").write_text(notes)
    name, proc = run(existing=True)
    assert name == BUILD and ("Missing notes" in proc.stderr or "Expected one pack_version" in proc.stderr)
    assert not (root / "built-version").exists()
    assert not (root / "gh-args.jsonl").exists()


@pytest.mark.parametrize("existing", [False, True])
def test_release_downloads_verify_next_to_their_zips(release_checkout, existing):
    root, run = release_checkout
    (root / f"tools/pd2-port/releases/{TAG}.md").write_text(VALID_NOTES)
    result = run(existing=existing)
    assert result is None, (result[0], result[1].stderr) if result else None
    assert (root / "built-version").read_text() == "0.1.2"
    calls = [json.loads(line) for line in (root / "gh-args.jsonl").read_text().splitlines()]
    assert [c[1] for c in calls] == (["view", "upload"] if existing else ["view", "create", "upload"])
    assert calls[-1][2] == TAG and calls[-1][-1] == "--clobber"
    detached = root / "downloads"
    detached.mkdir()
    for name in calls[-1][3:-1]:
        shutil.copyfile(root / "build/lawson-release" / name, detached / name)
    assert {p.name for p in detached.iterdir()} == {p.name + ext for p in (ROMANCE, L4D2) for ext in ("", ".sha256")}
    proc = subprocess.run(["sha256sum", "-c", *(p.name for p in detached.glob("*.sha256"))],
                          cwd=detached, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
