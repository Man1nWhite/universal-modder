#!/usr/bin/env python3
"""Build every rebuildable pack again, in a copy of the working tree, and compare.

    python tools/pd2-las/fresh.py check
    python tools/pd2-las/fresh.py matrix [--configs a,b,...] [--builders x,y] [--trace all]

check   builds every distribution pack in build/fresh/tree, including the
        native Hila replacement after its body and head donors
        and compares generated ZIPs to the verified digests of the original
        ZIPs. A copied pack does not count as a rebuild.
        No tolerance: a zip is the tracked bytes or it is not. Exit status 1 when
        one is not; what differs inside it is listed member by member.
matrix  the same build under other numeric code paths (CONFIGS), two at a time,
        each in its own copy under build/vary/. Prints which zips move against
        the first configuration and, with --trace, where each builder first
        computes another value (trace_run.py).

Neither touches a tracked file: the builders write into the copy.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = REPO / ".venv" / "bin" / "python"
sys.path.insert(0, str(HERE))

import determinism  # noqa: E402
import extract_2b  # noqa: E402
from pack_checksum import distribution_zips, sha256_file, verify_checksum  # noqa: E402
from status import target as make_target  # noqa: E402
import trace_run  # noqa: E402

#: What builds the tracked packs, in dependency order. Miranda and busty share
#: a texture staging directory; the head packs consume the base Miranda ZIP.
BUILDERS = {
    "miranda": ["tools/pd2-las/build_models.py"],
    "busty": ["tools/pd2-las/build_busty_variant.py"],
    "lawson": ["tools/pd2-port/build_las_pack.py"],
    "heads": ["tools/build_joy_head_mods.py"],
    "honokodae": ["tools/pd2-las/build_honoko2_dae.py"],
    "christie": ["tools/pd2-las/build_christie_source.py"],
    "cloverchristie": ["tools/pd2-las/build_clover_christie.py"],
    "hila": ["tools/build_hila_body_mod.py"],
    "voices_stream": ["tools/build_hila_stream_mod.py"],
    # Reads dist/Honoka/OfficeSuite_Miranda_Romance_over_Hila.zip for its head, so
    # it runs after `hila`. `--only` keeps the OfficeSuite body pack out of it.
    "honokodae_head": ["tools/pd2-las/build_honoko2_dae.py", "--only", "officesuite_head"],
}

_NO_512 = "X86_V4 AVX512_ICL AVX512_SPR"
#: Numeric code paths for `matrix`: environment variables that numpy, OpenBLAS
#: and glibc read when they load. "declared" is the build as it runs by itself,
#: on the code path of determinism.CODE_PATH. Every other one also sets
#: PD2_CODEPATH=free, which tells the builders to leave the code path alone.
CONFIGS = {
    "declared": {},
    "as-is": {},
    "avx2": {"OPENBLAS_CORETYPE": "Haswell", "NPY_DISABLE_CPU_FEATURES": _NO_512},
    "sse42": {"OPENBLAS_CORETYPE": "Nehalem", "NPY_DISABLE_CPU_FEATURES": "X86_V3 " + _NO_512},
    "threads-1": {"OPENBLAS_NUM_THREADS": "1"},
    "threads-4": {"OPENBLAS_NUM_THREADS": "4"},
    "libm-plain": {"OPENBLAS_CORETYPE": "Nehalem", "NPY_DISABLE_CPU_FEATURES": "X86_V3 " + _NO_512,
                   "GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2,-FMA,-AVX512F,-AVX512VL"},
}


class BuildFailed(Exception):
    def __init__(self, name: str, status: int, tail: list[str]):
        super().__init__(f"{name} exited with {status}")
        self.name, self.status, self.tail = name, status, tail


def tracked_zips() -> list[str]:
    """Enumerate ZIPs independently of sidecars, and fail on incomplete coverage."""
    paths = set()
    for command in (["ls-files", "-z", "--", "dist"], ["ls-tree", "-rz", "--name-only", "HEAD", "--", "dist"]):
        listing = subprocess.run(["git", *command], cwd=REPO, capture_output=True)
        if listing.returncode and command[0] == "ls-files":
            raise SystemExit(f"cannot list build inputs: {os.fsdecode(listing.stderr).strip()}")
        paths.update(os.fsdecode(raw) for raw in listing.stdout.split(b"\0") if raw)
    try:
        return distribution_zips(REPO, paths)
    except ValueError as error:
        raise SystemExit(str(error)) from error


def build_plan(requested: str, zips: list[str]) -> dict[str, list[str]]:
    """Order builders by dependencies and identify every output they owe."""
    names = set(requested.split(",")) if requested else set(BUILDERS)
    if unknown := names - BUILDERS.keys():
        raise SystemExit(f"unknown builders: {', '.join(sorted(unknown))}")
    outputs = {name: [] for name in BUILDERS}
    for rel in zips:
        owner = make_target(Path(rel).stem)
        owner = "miranda" if owner == "build" else owner
        if owner not in outputs:
            raise SystemExit(f"no builder for {rel}")
        outputs[owner].append(rel)
    plan = {name: owned for name, owned in outputs.items() if name in names}
    if empty := [name for name, owned in plan.items() if not owned]:
        raise SystemExit(f"no distribution ZIPs assigned to builders: {', '.join(empty)}")
    return plan


def verified_checksums(zips: list[str]) -> dict[str, str]:
    """Verify original artifacts before any builder can replace them."""
    try:
        return {rel: verify_checksum(REPO / rel, REPO) for rel in zips}
    except (OSError, ValueError) as error:
        raise SystemExit(f"original distribution: {error}") from error


def copy_tree(tree: Path, outputs: list[str]) -> None:
    """Copy the working tree as git sees it, omitting the outputs we will verify."""
    if tree.exists():
        shutil.rmtree(tree)
    omit = set(outputs) | {rel + ".sha256" for rel in outputs}
    listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=REPO, capture_output=True, check=True).stdout
    for raw in listing.split(b"\0"):
        rel = os.fsdecode(raw)
        source = REPO / rel
        if raw and rel not in omit and source.is_file():
            target = tree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    (tree / "build").mkdir(parents=True, exist_ok=True)


def require_env(plan: dict[str, list[str]]) -> None:
    if not PY.is_file() or (plan.keys() - {"lawson", "heads", "hila"} and not extract_2b.ready()):
        raise SystemExit("no .venv or no current 2B templates: run `make -sC tools/pd2-las env` first")


def run_builders(tree: Path, extra: dict, plan: dict[str, list[str]], trace_dir: Path | None = None) -> None:
    logs = tree.parent / "log"
    logs.mkdir(exist_ok=True)
    env = {**os.environ, **extra, extract_2b.ENV: str(extract_2b.TEMPLATES.resolve())}
    for name, outputs in plan.items():
        occupied = [rel for zip_rel in outputs for rel in (zip_rel, zip_rel + ".sha256")
                    if (tree / rel).exists() or (tree / rel).is_symlink()]
        if occupied:
            raise BuildFailed(name, 1, ["outputs already present before building: " + ", ".join(occupied)])
        command = [str(PY)]
        if trace_dir is not None:
            trace_dir.mkdir(parents=True, exist_ok=True)
            command += ["tools/pd2-las/trace_run.py", "--out", str(trace_dir / f"{name}.log")]
        command += BUILDERS[name]
        with open(logs / f"{name}.log", "w") as log:
            status = subprocess.run(command, cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        if status:
            tail = (logs / f"{name}.log").read_text(errors="replace").splitlines()[-6:]
            raise BuildFailed(name, status, tail)
        missing = [rel for rel in outputs if not (tree / rel).is_file()]
        if missing:
            raise BuildFailed(name, 1, ["did not produce: " + ", ".join(missing)])
        if name != "lawson":  # Romance's distributed sidecar is written at promotion time.
            for rel in outputs:
                try:
                    verify_checksum(tree / rel, tree)
                except (OSError, ValueError) as error:
                    raise BuildFailed(name, 1, [str(error)]) from error


# ------------------------------------------------------------ what differs


def _members(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return {info.filename.split("/", 1)[-1]: z.read(info) for info in z.infolist() if not info.is_dir()}


def _count(a: bytes, b: bytes) -> int:
    import numpy as np
    if len(a) != len(b):
        return max(len(a), len(b))
    return int((np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8)).sum())


def _model_diff(a: bytes, b: bytes) -> str:
    import numpy as np
    import diesel_model as dm
    try:
        old, new = dm.ModelFile.read(a).sections, dm.ModelFile.read(b).sections
    except Exception as error:
        return f"does not read as a model ({error})"
    if [(s.type, s.id, len(s.payload)) for s in old] != [(s.type, s.id, len(s.payload)) for s in new]:
        return "other sections"
    parts = []
    for x, y in zip(old, new):
        if x.payload == y.payload:
            continue
        if x.type != dm.GEOMETRY:
            parts.append(f"{dm.TAG_NAMES.get(x.type, hex(x.type))} {x.id}")
            continue
        ga, gb = dm.decode_geometry(x.payload), dm.decode_geometry(y.payload)
        for key in ("verts", "normals", "uv0", "blendindices", "blendweights", "uvdir_u", "uvdir_v"):
            if not ga[key] or len(ga[key]) != len(gb[key]):
                continue
            was, now = np.asarray(ga[key], float), np.asarray(gb[key], float)
            rows = np.flatnonzero((was != now).any(axis=1))
            if not len(rows):
                continue
            flipped = int((np.abs(was[rows] + now[rows]).max(axis=1) < 1e-6).sum())
            rest = len(rows) - flipped
            text = f"geometry {x.id} {key}: {len(rows)} of {len(was)} vertices"
            if flipped:
                text += f", {flipped} reversed"
            if rest:
                gap = np.abs(was[rows] - now[rows]).max(axis=1)
                text += f", {rest} by up to {float(np.sort(gap)[rest - 1]):.2g}"
            parts.append(text)
    return "; ".join(parts) or "bytes outside the decoded channels"


def _texture_diff(a: bytes, b: bytes) -> str:
    import numpy as np
    import dds_encode
    text = f"{_count(a, b):,} bytes"
    if len(a) == len(b) and a[84:88] == b"DXT5" == b[84:88]:
        try:
            for level in range(len(dds_encode.bc3_levels(a))):
                gap = np.abs(dds_encode.decode_bc3_level(a, level).astype(int)
                             - dds_encode.decode_bc3_level(b, level).astype(int)).max(axis=2)
                ys, xs = np.nonzero(gap)
                if len(ys):
                    text += (f"; level {level}: {len(ys)} texels, x {xs.min()}..{xs.max()}, y {ys.min()}..{ys.max()}"
                             f" of {gap.shape[0]}, by up to {int(gap.max())}")
        except Exception as error:
            text += f" (not decoded: {error})"
    return text


def explain(tracked_zip: Path, fresh_zip: Path) -> list[str]:
    """One line per member that differs between two builds of a pack."""
    old, new = _members(tracked_zip), _members(fresh_zip)
    out = []
    for name in sorted(set(old) | set(new)):
        if old.get(name) == new.get(name):
            continue
        short = name.rsplit("/", 1)[-1]
        if name not in old or name not in new:
            out.append(f"{short}: in one of the two only")
        elif name.endswith(".model"):
            out.append(f"{short}: {_model_diff(old[name], new[name])}"[:400])
        elif name.endswith(".texture"):
            out.append(f"{short}: {_texture_diff(old[name], new[name])}"[:400])
        else:
            out.append(f"{short}: {_count(old[name], new[name]):,} bytes")
    return out


def machine() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    lines = cpuinfo.read_text(errors="replace").splitlines() if cpuinfo.exists() else []
    model = next((line.split(":", 1)[1].strip() for line in lines
                  if line.lower().startswith(("model name", "cpu part"))), platform.processor() or "?")
    flags = next((line.split(":", 1)[1].split() for line in lines if line.startswith(("flags", "Features"))), [])
    return (f"{model} ({platform.machine()}), {os.cpu_count()} threads, "
            f"AVX-512 {'yes' if 'avx512f' in flags else 'no'}, AVX2 {'yes' if 'avx2' in flags else 'no'}")


def note(title: str, text: str, level: str = "notice") -> None:
    """A GitHub annotation: the part of a run that the API serves to a reader without the log."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level} title={title}::{' '.join(text.split())[:900]}", flush=True)


def check(args) -> int:
    original = verified_checksums(tracked_zips())
    plan = build_plan(args.builders, list(original))
    zips = sorted(rel for owned in plan.values() for rel in owned)
    require_env(plan)
    tree = REPO / "build" / "fresh" / "tree"
    print(f"machine: {machine()}", flush=True)
    note("runner", machine())
    told = subprocess.run([str(PY), str(HERE / "determinism.py")], cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, **({"PD2_CODEPATH": "free"} if args.free else {})})
    path = (told.stdout.strip().splitlines() or [told.stderr.strip()[-300:] or "?"])[-1]
    path = ("left to the machine: " if args.free else "declared: ") + path
    print(f"code path {path}", flush=True)
    note("code path", path)
    copy_tree(tree, zips)
    try:
        run_builders(tree, {"PD2_CODEPATH": "free"} if args.free else {}, plan)
    except BuildFailed as failed:
        text = f"{failed.name} did not build (exit {failed.status}): " + " | ".join(failed.tail)
        print(text)
        note("fresh build", text, "error")
        return 2
    different = [rel for rel in zips if sha256_file(tree / rel) != original[rel]]
    for rel in zips:
        print(("DIFFERENT  " if rel in different else "same       ") + rel)
    details = []
    for rel in different:
        try:
            explanations = explain(REPO / rel, tree / rel)
        except zipfile.BadZipFile as error:
            explanations = [f"not a readable ZIP: {error}"]
        for line in explanations:
            details.append(f"{Path(rel).name}: {line}")
    for line in details:
        print("    " + line)
    summary = f"{len(zips) - len(different)} of {len(zips)} tracked zips are the tracked bytes after a fresh build"
    if args.builders:
        summary += f" (selected builders: {', '.join(plan)})"
    if different:
        summary += "; different: " + ", ".join(Path(rel).name for rel in different if rel.startswith("dist/"))
    print(summary)
    note("fresh build", summary)
    for line in details[:7]:
        note("differs", line)
    return 1 if different else 0


# ----------------------------------------------------------------- matrix

PROBE = r'''
import ctypes, glob, hashlib, json, math, os, struct, sys
import numpy as np
from numpy._core._multiarray_umath import __cpu_features__ as features
def blas():
    for path in glob.glob(os.path.join(os.path.dirname(np.__file__), "..", "numpy.libs", "libscipy_openblas*.so*")):
        lib, found = ctypes.CDLL(path), {}
        for what, kind in (("corename", ctypes.c_char_p), ("num_threads", ctypes.c_int)):
            for symbol in (f"scipy_openblas_get_{what}64_", f"scipy_openblas_get_{what}", f"openblas_get_{what}64_", f"openblas_get_{what}"):
                if hasattr(lib, symbol):
                    function = getattr(lib, symbol)
                    function.restype = kind
                    value = function()
                    found[what] = value.decode() if isinstance(value, bytes) else value
                    break
        return f"{found.get('corename', '?')}, {found.get('num_threads', '?')} threads"
    return "?"
out = {"numpy": " ".join(name for name in ("X86_V2", "X86_V3", "X86_V4", "AVX512_ICL", "AVX512_SPR") if features.get(name)), "blas": blas()}
x = np.linspace(0.001, 6.0, 1 << 20)
y = x[::-1].copy()
for kind in (np.float64, np.float32):
    a, b = x.astype(kind), y.astype(kind)
    p, q = a[:65536].reshape(256, 256), b[:65536].reshape(256, 256)
    for name, value in (("sin", np.sin(a * 100)), ("cos", np.cos(a * 100)), ("exp", np.exp(-a)), ("log", np.log(a)),
                        ("power", np.power(a, kind(1.35))), ("arctan2", np.arctan2(a - 3, b - 2)), ("hypot", np.hypot(a, b)),
                        ("sqrt", np.sqrt(a)), ("add.reduce", np.add.reduce(a.reshape(1024, 1024), axis=1)),
                        ("dot", np.dot(a, b)), ("matmul", p @ q), ("lstsq", np.linalg.lstsq(p[:, :8], q[:, :3], rcond=None)[0]),
                        ("svd", np.linalg.svd(p[:16, :16])[1])):
        out[f"{name} {np.dtype(kind).name}"] = hashlib.sha256(np.asarray(value).tobytes()).hexdigest()[:12]
values = x[::64].tolist()
table = [f(v) for v in values for f in (lambda v: math.sin(v * 100), lambda v: math.exp(-v), lambda v: math.pow(v, 1.35), lambda v: math.atan2(v - 3, 2 - v))]
out["libm through math"] = hashlib.sha256(struct.pack(f"<{len(table)}d", *table)).hexdigest()[:12]
print(json.dumps(out))
'''


def one_config(name: str, plan: dict[str, list[str]], traced: bool) -> dict:
    base = REPO / "build" / "vary" / name
    extra = dict(CONFIGS.get(name) or {})
    if name != "declared":
        extra["PD2_CODEPATH"] = "free"
    result = {"config": name, "env": extra}
    try:
        zips = [rel for owned in plan.values() for rel in owned]
        copy_tree(base / "tree", zips)
        told = {**os.environ, **extra, **(determinism.CODE_PATH if name == "declared" else {})}
        probe = subprocess.run([str(PY), "-c", PROBE], env=told, capture_output=True, text=True)
        result["probe"] = (json.loads(probe.stdout) if probe.returncode == 0 and probe.stdout.strip()
                           else {"numpy": "probe failed", "blas": probe.stderr.strip()[-200:]})
        started = time.time()
        run_builders(base / "tree", extra, plan, base / "trace" if traced else None)
        result["seconds"] = round(time.time() - started)
        result["sha256"] = {rel: sha256_file(base / "tree" / rel) for rel in zips}
    except BuildFailed as failed:
        result["failed"] = f"{failed.name} (exit {failed.status}): " + " | ".join(failed.tail)
    (base / "result.json").write_text(json.dumps(result, indent=1))
    return result


def compare_traces(reference: Path, other: Path, limit: int = 8) -> list[str]:
    """Where two traces of one builder part: the first value of any kind, and the first exact ones."""
    def read(path):
        events, totals = {}, {}
        with open(path) as handle:
            for line in handle:
                part = line.split()
                if part[0] in ("C", "R"):
                    events[part[0], part[1]] = part[2:]
                elif part[0] == "S":
                    totals[part[1]] = part[2:]
        return events, totals

    (ea, ta), (eb, tb) = read(reference), read(other)
    rows, seen = [], {"exact": set(), "float": set()}
    for (kind, call), a in ea.items():
        b = eb.get((kind, call))
        label = ("arguments of " if kind == "C" else "return of ") + call + (f", called from {a[3]}" if kind == "C" else "")
        if b is None:
            rows.append((int(a[2]), "path", label + ": not reached in the other run"))
        elif a[1] != b[1]:
            rows.append((int(a[2]), "exact", label))
            seen["exact"].add(call.split("#")[0])
        elif a[0] != b[0]:
            rows.append((int(a[2]), "float", label))
            seen["float"].add(call.split("#")[0])
    for name, a in ta.items():
        b = tb.get(name)
        if b is None or a[0] != b[0]:
            rows.append((int(a[3]), "path", f"{name}: called {a[0]} times, {b[0] if b else 0} in the other run"))
        elif a[2] != b[2] and name not in seen["exact"]:
            rows.append((int(a[3]), "exact", f"a return of {name} after its first {trace_run.FIRST} calls"))
        elif a[1] != b[1] and name not in seen["exact"] and name not in seen["float"]:
            rows.append((int(a[3]), "float", f"a return of {name} after its first {trace_run.FIRST} calls"))
    rows.sort()
    if not rows:
        return ["the two traces are the same"]
    exact = [text for _seq, kind, text in rows if kind in ("exact", "path")]
    out = [f"first value that differs: {rows[0][2]} ({'float64 only' if rows[0][1] == 'float' else rows[0][1]}); "
           f"{sum(kind == 'float' for _s, kind, _t in rows)} lines differ in float64 only, {len(exact)} in exact values"]
    out += [f"exact: {text}" for text in exact[:limit]]
    return out


def matrix(args) -> int:
    names = args.configs.split(",")
    original = verified_checksums(tracked_zips())
    plan = build_plan(args.builders, list(original))
    require_env(plan)
    traced = set(names) if args.trace == "all" else set(filter(None, args.trace.split(",")))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = dict(zip(names, pool.map(lambda name: one_config(name, plan, name in traced), names)))
    reference = names[0]
    ref = results[reference]
    tracked = {rel: original[rel] for owned in plan.values() for rel in owned}
    print(f"machine: {machine()}\nbuilders: {', '.join(plan)}\n")
    print(f"| configuration | numpy | OpenBLAS | seconds | functions whose results differ from `{reference}` |")
    print("| --- | --- | --- | --- | --- |")
    for name in names:
        probe = results[name].get("probe", {})
        moved = [key for key, value in probe.items() if key not in ("numpy", "blas") and ref.get("probe", {}).get(key) != value]
        print(f"| `{name}` | {probe.get('numpy', '?')} | {probe.get('blas', '?')} | {results[name].get('seconds', '-')} "
              f"| {', '.join(moved) or 'none'} |")
    print()
    status = 0
    for name in names:
        result = results[name]
        if "failed" in result:
            print(f"`{name}`: FAILED: {result['failed']}")
            status = 2
            continue
        off = [Path(rel).name for rel, sha in result["sha256"].items() if sha != tracked[rel] and rel.startswith("dist/")]
        moved = [rel for rel, sha in result["sha256"].items() if sha != ref.get("sha256", {}).get(rel)]
        print(f"`{name}`: {len(moved)} of {len(tracked)} zips differ from `{reference}`; "
              f"{len(off)} of the {len(tracked)} packs differ from the tracked bytes" + (f" ({', '.join(off)})" if off else ""))
        for rel in moved:
            if rel.startswith("build/") and "dist/" + Path(rel).name in moved:
                continue
            for line in explain(REPO / "build" / "vary" / reference / "tree" / rel, REPO / "build" / "vary" / name / "tree" / rel):
                print(f"    {Path(rel).name}: {line}")
        if name != reference and name in traced and reference in traced:
            for builder in plan:
                a = REPO / "build" / "vary" / reference / "trace" / f"{builder}.log"
                b = REPO / "build" / "vary" / name / "trace" / f"{builder}.log"
                if a.exists() and b.exists():
                    for line in compare_traces(a, b):
                        print(f"    trace of {builder}: {line}")
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    one = sub.add_parser("check")
    one.add_argument("--builders", default="", help="compare only these builders (comma separated); other ZIPs are inputs only")
    one.add_argument("--free", action="store_true", help="do not hold the builders to the declared code path")
    many = sub.add_parser("matrix")
    many.add_argument("--configs", default="declared,as-is,avx2,sse42,threads-1,threads-4,libm-plain")
    many.add_argument("--builders", default="")
    many.add_argument("--trace", default="", help="`all`, or the configurations to trace (comma separated)")
    many.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args(argv)
    return check(args) if args.command == "check" else matrix(args)


if __name__ == "__main__":
    raise SystemExit(main())
