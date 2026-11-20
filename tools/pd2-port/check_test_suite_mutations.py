"""Mutation-test the pack-level test suite.

The compliance checker's own self-test proves that the *checker* catches a
broken pack.  This proves the other half: that the pytest wrappers around it
really fail (and do not silently skip) when the pack is broken.  A test that
skips, or that asserts nothing, is worse than no test at all.

For every mutation, the matching test must pass on the unmodified Romance
pack and fail with the intended assertion on a scratch ZIP. A skip, missing
node, collection error, or unrelated exception is not a caught mutation.
The tracked pack is never written.

    python tools/pd2-port/check_test_suite_mutations.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import sys as _dist_sys
_dist_sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "pd2-las"))
from dist_paths import dist_path  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACK = dist_path(ROOT, "lawson_las.zip")
TEST_PACK_ENV = "PD2_TEST_LAWSON_PACK"
TPP_MODEL = "Lawson_LAS/assets/units/lawson/skins/lawson/lawson.model"

sys.path.insert(0, str(HERE))
import importlib.util


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dmodel = _load("dmodel_las", "dmodel.py")


def _read() -> dict[str, bytes]:
    with zipfile.ZipFile(PACK) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def _write(files: dict[str, bytes], path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


def m_inverted_triangle(files: dict[str, bytes]) -> dict[str, bytes]:
    """One triangle of the TPP body wound inside out."""
    data = bytearray(files[TPP_MODEL])
    model = dmodel.DieselModel.from_bytes(bytes(data))
    topo = next(s for s in model.sections if s.tag == "topology")
    off = topo.start + 8
    a = int.from_bytes(data[off:off + 2], "little")
    b = int.from_bytes(data[off + 2:off + 4], "little")
    data[off:off + 2] = b.to_bytes(2, "little")
    data[off + 2:off + 4] = a.to_bytes(2, "little")
    files[TPP_MODEL] = bytes(data)
    return files


def m_no_fps_unit(files: dict[str, bytes]) -> dict[str, bytes]:
    """The FPS unit is no longer registered."""
    main = files["Lawson_LAS/main.xml"].decode()
    main = main.replace('        <unit_mat path="units/lawson/skins/lawson/fps_lawson"/>\n', "")
    files["Lawson_LAS/main.xml"] = main.encode()
    return files


def m_no_localization(files: dict[str, bytes]) -> dict[str, bytes]:
    """The menu strings are gone."""
    files["Lawson_LAS/localization/english.txt"] = b""
    return files


def m_no_tangent_channels(files: dict[str, bytes]) -> dict[str, bytes]:
    """The geometry loses its tangent/bitangent channels."""
    data = bytearray(files[TPP_MODEL])
    model = dmodel.DieselModel.from_bytes(bytes(data))
    geo = next(s for s in model.sections if s.tag == "geometry")
    # the header block: vertex count, header count, then (size, type) pairs
    import struct
    hc = struct.unpack_from("<I", data, geo.start + 4)[0]
    for i in range(hc):
        at = geo.start + 8 + i * 8
        ity = struct.unpack_from("<I", data, at + 4)[0]
        if ity in (22, 23):
            struct.pack_into("<I", data, at + 4, 24)   # 24 = an unused type
    files[TPP_MODEL] = bytes(data)
    return files


MUTATIONS = [
    (m_inverted_triangle, "tests/test_las_pack.py::test_the_built_pack_has_no_inverted_faces",
     "triangle wound inside out", "triangles are inverted"),
    (m_inverted_triangle, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "triangle wound inside out (the audit must notice)", "N3:"),
    (m_no_fps_unit, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "FPS unit not registered", "P2:"),
    (m_no_localization, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "localization emptied", "P4:"),
    (m_no_tangent_channels, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "tangent channels removed from the geometry", "S7:"),
]


def run_test(test: str, pack: Path, report: Path, expect: str | None = None) -> str | None:
    """Run exactly one pytest node and require a pass or the specified assertion."""
    report.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--junitxml", str(report), test],
            cwd=ROOT, capture_output=True, text=True,
            env={**os.environ, TEST_PACK_ENV: str(pack)},
        )
    except OSError as error:
        return f"could not run pytest: {error}"
    wanted = 0 if expect is None else 1   # pytest.ExitCode.OK or TESTS_FAILED
    if proc.returncode != wanted:
        return f"pytest exit {proc.returncode}, expected {wanted}: {(proc.stderr or proc.stdout).strip()[-450:]}"
    try:
        cases = list(ET.parse(report).iter("testcase"))
    except (OSError, ET.ParseError) as error:
        return f"no readable pytest results: {error}"
    if len(cases) != 1 or cases[0].get("name") != test.rsplit("::", 1)[1]:
        return f"expected one result for {test}"
    case = cases[0]
    if case.find("skipped") is not None or case.find("error") is not None:
        return f"{test} was skipped or errored"
    failure = case.find("failure")
    if expect is None and failure is None:
        return None
    if expect is not None and failure is not None:
        message = failure.get("message", "")
        if message.startswith(("AssertionError:", "assert ")) and expect in message:
            return None
        return f"wrong failure: {message[:450]}"
    return f"unexpected pytest result for {test}"


def main() -> int:
    if not PACK.is_file():
        print("no built pack - run build_las_pack.py first")
        return 1
    base = _read()
    with tempfile.TemporaryDirectory(prefix="lawson-mutations-") as scratch:
        mutated = Path(scratch) / PACK.name
        report = Path(scratch) / "pytest.xml"
        for test in dict.fromkeys(test for _, test, _, _ in MUTATIONS):
            if error := run_test(test, PACK, report):
                print(f"FAIL clean baseline {test}: {error}")
                return 1
        misses = 0
        for mutate, test, label, expected in MUTATIONS:
            files = dict(base)
            mutate(files)
            if files == base:
                error = "mutation did not modify the pack"
            else:
                _write(files, mutated)
                error = run_test(test, mutated, report, expected)
            if error:
                misses += 1
                print(f"  MISS {label}: {error}")
            else:
                print(f"  ok   {label}: failed as expected")
    print(f"\n{len(MUTATIONS) - misses}/{len(MUTATIONS)} pack-level test mutations caught")
    return int(bool(misses))


if __name__ == "__main__":
    raise SystemExit(main())
