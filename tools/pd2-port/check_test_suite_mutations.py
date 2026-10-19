"""Mutation-test the pack-level test suite.

The compliance checker's own self-test proves that the *checker* catches a
broken pack.  This proves the other half: that the pytest wrappers around it
really fail (and do not silently skip) when the pack is broken.  A test that
skips, or that asserts nothing, is worse than no test at all.

For every mutation the shipped pack is broken in a way the test is supposed
to notice, the matching test is run, and the run must FAIL.  A test that
passes or skips is a hole in the suite.

    python tools/pd2-port/check_test_suite_mutations.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
PACK = ROOT / "dist" / "lawson_las.zip"
TPP_MODEL = "Lawson_LAS/units/lawson/skins/lawson/lawson.model"

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
    n = struct.unpack_from("<I", data, geo.start)[0]
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
     "triangle wound inside out"),
    (m_inverted_triangle, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "triangle wound inside out (the audit must notice)"),
    (m_no_fps_unit, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "FPS unit not registered"),
    (m_no_localization, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "localization emptied"),
    (m_no_tangent_channels, "tests/test_las_pack.py::test_built_pack_passes_the_guide_compliance_check",
     "tangent channels removed from the geometry"),
]


def main() -> int:
    if not PACK.exists():
        print("no built pack - run build_las_pack.py first")
        return 1
    base = _read()
    backup = PACK.read_bytes()
    misses = []
    with tempfile.TemporaryDirectory() as tmp:
        for mutate, test, label in MUTATIONS:
            files = dict(base)
            mutate(files)
            _write(files, PACK)
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test],
                cwd=ROOT, capture_output=True, text=True)
            PACK.write_bytes(backup)
            out = proc.stdout + proc.stderr
            skipped = "skipped" in out and proc.returncode == 0
            if proc.returncode == 0:
                misses.append(f"{label} -> {test} did not fail")
                state = "PASSED (not caught!)"
            elif skipped:
                misses.append(f"{label} -> {test} skipped instead of failing")
                state = "SKIPPED"
            else:
                state = "failed as expected"
            print(f"  {'ok  ' if state == 'failed as expected' else 'MISS'} "
                  f"{label:<44} {state}")
    print()
    if misses:
        print(f"{len(misses)} of {len(MUTATIONS)} mutations slipped through:")
        for m in misses:
            print(f"  - {m}")
        return 1
    print(f"{len(MUTATIONS)}/{len(MUTATIONS)} pack-level test mutations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
