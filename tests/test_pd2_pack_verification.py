"""Pack checks fail closed without conflating the different build pipelines."""
from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path[:0] = [str(TOOLS / "pd2-las"), str(TOOLS / "pd2-port")]

import check_all  # noqa: E402
import check_guide_compliance_self_test as self_test  # noqa: E402
import check_mesh_geometry as mesh  # noqa: E402
import check_test_suite_mutations as mutations  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from pack_checksum import sidecar_path, write_checksum  # noqa: E402

L4D2 = dist_path(ROOT, "Miranda_L4D2_LAS.zip")


def cli(script, *args):
    return subprocess.run([sys.executable, str(TOOLS / "pd2-port" / script), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True)


def test_selected_pack_only_gets_its_own_checksum_and_geometry(tmp_path):
    pack = tmp_path / "selected pack.zip"
    shutil.copyfile(L4D2, pack)
    write_checksum(pack)
    result = cli("check_all.py", "--pack", pack)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "all 2 stages passed" in result.stdout
    assert "not a full outfit audit" in result.stdout
    assert "19325 triangles" in result.stdout
    assert "normal-map convention" not in result.stdout and "mutations" not in result.stdout
    result = cli("check_guide_compliance.py", pack)
    assert result.returncode == 1 and "FAIL FORMAT" in result.stdout
    assert "legacy/2B" in result.stdout


@pytest.mark.parametrize("content", [None, b"", b"0" * 64 + b"  not-the-pack.zip\n"])
def test_selected_pack_with_invalid_sidecar_fails_as_a_check(tmp_path, capsys, content):
    pack = tmp_path / "pack.zip"
    shutil.copyfile(L4D2, pack)
    if content is not None:
        sidecar_path(pack).write_bytes(content)
    assert check_all.main(["--pack", str(pack)]) == 1
    output = capsys.readouterr()
    assert "[FAIL] pack matches its checksum" in output.out
    assert "Traceback" not in output.err


@pytest.mark.parametrize("changed", ["stale-names", "one-stale-name", "all-disabled"])
def test_mesh_geometry_rejects_missing_enabled_drawables(tmp_path, capsys, changed):
    pack = tmp_path / "bad-drawables.zip"
    with zipfile.ZipFile(L4D2) as good, zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED) as bad:
        for name in good.namelist():
            data = good.read(name)
            if name.endswith("/miranda.object"):
                tree = ET.fromstring(data)
                listed = [e for e in tree.findall(".//graphics//object") if e.get("enabled") == "true"]
                assert len(listed) > 1  # keep one drawable unchanged for the partial case
                for element in listed[:1] if changed == "one-stale-name" else listed:
                    if changed == "all-disabled":
                        element.set("enabled", "false")
                    else:
                        element.set("name", f"stale_{element.get('name')}")
                data = ET.tostring(tree)
            bad.writestr(name, data)
    assert mesh.main([str(pack)]) == 1
    output = capsys.readouterr().out
    if changed != "one-stale-name":
        assert "no analyzable triangles in third person (miranda)" in output
    else:
        assert "stale_" in output and "enabled drawables missing geometry" in output


def test_mesh_geometry_names_uncovered_drawables(tmp_path, capsys, monkeypatch):
    pack = tmp_path / "no-tangents.zip"
    with zipfile.ZipFile(L4D2) as good, zipfile.ZipFile(pack, "w") as bad:
        for entry in good.namelist():
            if entry.endswith(("/miranda.model", "/miranda.object")):
                bad.writestr(entry, good.read(entry))
    decode = mesh.Geometry

    def absent_tangent(*args):
        g = decode(*args)
        g.tangent = []
        return g

    monkeypatch.setattr(mesh, "Geometry", absent_tangent)
    assert mesh.main([str(pack)]) == 1
    out = capsys.readouterr().out
    assert "missing tangents" in out and "no analyzable triangles" in out


def test_tangent_diagnostic_accounts_for_mirrored_uvs():
    positions = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)]
    g = SimpleNamespace(pos=positions, nrm=[(0., 0., 1.)] * 3, uv=[(0., 0.), (-1., 0.), (0., 1.)],
                        tangent=[(-1., 0., 0.)] * 3, bitangent=[(0., 1., 0.)] * 3)
    assert mesh.analyse("mirrored uv", g, [(0, 1, 2)])["tangent_agree"] == 1.0


def test_contour_variable_must_be_on_each_material():
    base = self_test.read_pack()
    changed = self_test.m_no_contour_var(dict(base))
    key = self_test.TPP_CFG
    variable = b'name="contour_opacity"'
    assert 0 < changed[key].count(variable) == base[key].count(variable) - 1
    failures = [c for c in self_test.audit_pack(changed).checks if c["status"] == "FAIL"]
    assert any(c["id"] == "M5" and "no contour_opacity variable" in c["detail"] for c in failures)


def test_mutation_runner_requires_the_intended_pytest_failure(tmp_path, monkeypatch):
    test = tmp_path / "test_node.py"
    test.write_text("""\
import pytest

def test_skip():
    pytest.skip('fixture absent')

def test_wrong_failure():
    raise ValueError('N3: unrelated exception')

def test_caught():
    assert False, 'N3: intended failure'

def test_control():
    assert True
""")
    monkeypatch.setattr(mutations, "ROOT", tmp_path)
    report = tmp_path / "report.xml"
    pack = tmp_path / "pack.zip"
    assert "pytest exit 4" in mutations.run_test(f"{test}::test_missing", pack, report, "N3:")
    assert "skipped or errored" in mutations.run_test(f"{test}::test_skip", pack, report)
    assert "wrong failure" in mutations.run_test(f"{test}::test_wrong_failure", pack, report, "N3:")
    assert mutations.run_test(f"{test}::test_caught", pack, report, "N3:") is None
    assert mutations.run_test(f"{test}::test_control", pack, report) is None


def test_interrupted_mutation_does_not_write_to_original_pack(tmp_path, monkeypatch):
    pack = tmp_path / "original.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("data", b"original")
    original = pack.read_bytes()
    monkeypatch.setattr(mutations, "PACK", pack)
    scratch = []

    def run(test, input_path, report, expect=None):
        if expect is None:
            assert input_path.read_bytes() == original
            return None
        scratch.append(input_path)
        assert pack.read_bytes() == original
        with zipfile.ZipFile(input_path) as z:
            assert z.read("data") == b"mutated"
        raise KeyboardInterrupt

    monkeypatch.setattr(mutations, "run_test", run)
    monkeypatch.setattr(mutations, "MUTATIONS", [
        (lambda files: files.update(data=b"mutated"), "test_demo.py::test_control", "changed object", "N3:"),
    ])
    with pytest.raises(KeyboardInterrupt):
        mutations.main()
    assert scratch and scratch[0] != pack and not scratch[0].exists()
    assert pack.read_bytes() == original
