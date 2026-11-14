#!/usr/bin/env python3
"""What keeps the tracked bytes independent of the machine that builds them.

Three things, one for each kind of cause that was found
(docs/audits/2026-11-12-cpu-independence.md):

* A decision on a number that is zero in exact arithmetic gets a rule, where it
  is taken: `tangents.py`.
* A value that has been through sin, cos, exp, arctan2 or a power, whose last
  digit no standard fixes, is rounded by `floor8` / `rounded` and compared by
  `above`. They stop the build when a value lies so close to a rounding
  boundary that another math library could put it on the other side.
* The float64 arithmetic that is left runs on one declared code path of numpy
  and OpenBLAS, the same on every x86-64 CPU: `enter`.

    python tools/pd2-las/determinism.py     # what this machine loads on the declared code path
"""
from __future__ import annotations

import ctypes
import glob
import math
import os
import platform
import sys
from pathlib import Path

#: How close to a rounding boundary a drawn value may come, on the scale it is
#: rounded on (0..255 for a texel, 0..1 for a paint weight). Two float64 math
#: libraries that keep to their documented accuracy differ by a few units in the
#: sixteenth digit per function; through the formulas here that stays below
#: 1e-12 on the 0..255 scale, and the largest difference measured between the
#: code paths tried on 2026-11-12 is in the audit. 1e-9 is a thousand times
#: that, and still stops a build for only two values in a thousand million.
MARGIN = 1e-9
#: `floor8` cuts a value off to the whole number below it, as this build always
#: did, but its boundary is NUDGE below each whole number, not the whole number
#: itself. Whole numbers are where values pile up (a flat area, a clip, a paint
#: weight of zero), and a value that one machine computes as 199.99999999999997
#: and another as 200.0 has to come out as 200 on both. 1/1024 of a step is far
#: below anything visible, and wide enough that a paint fading towards a whole
#: number crosses the boundary within a small fraction of a texel. If a build
#: ever stops at the margin, change this by a hair and build again.
NUDGE = 2.0 ** -10
#: `rounded` goes to the nearest whole number, and a half goes up: its boundary
#: is SHIFT below the half. Halves are where means pile up. Four dark texels of
#: 5, 5, 6, 6 average to 5.5; in a repainted area the same kind of mean comes
#: out as 8.5 give or take 1e-15, by whatever the math library's power left
#: over when it cancelled. Rounded to the even number, as numpy does, that is 8
#: on one machine and 9 on another. With the shift it is 9 on all of them.
SHIFT = 2.0 ** -25


class TooClose(ArithmeticError):
    """A value is within MARGIN of a rounding boundary: another math library could round it the other way."""


def _stop(gap, values, what: str):
    import numpy as np
    worst = np.unravel_index(int(np.argmin(gap)), gap.shape)
    raise TooClose(f"{what}: {int((gap < MARGIN).sum())} value(s) within {MARGIN:g} of a rounding boundary, the nearest "
                   f"at {tuple(int(i) for i in worst)}: {float(values[worst])!r}")


def floor8(values, what: str, check: bool = True):
    """A float image as texels: every value cut off to the whole number below it, held to 0..255.

    A value from NUDGE below a whole number upwards counts as that number.
    With `check`, stop when a value is within MARGIN of a boundary. Use it for
    what the build draws or paints: values that come out of sin, cos, exp,
    arctan2 or a power.
    """
    import numpy as np
    x = np.asarray(values, dtype=np.float64) + NUDGE
    if not np.isfinite(x).all():
        raise TooClose(f"{what}: a value is not finite")
    low = np.floor(x)
    if check and x.size:
        gap = np.minimum(x - low, low + 1.0 - x)
        if float(gap.min()) < MARGIN:
            _stop(np.atleast_1d(gap), np.atleast_1d(x), what)
    return np.clip(low, 0, 255).astype(np.uint8)


def rounded(values, what: str, check: bool = True):
    """Round to the nearest whole number, as float64; a half, and anything up to SHIFT below it, goes up.

    With `check`, stop when a value is within MARGIN of the boundary. Use it
    for a mean that has been through a power.
    """
    import numpy as np
    x = np.asarray(values, dtype=np.float64) + SHIFT
    if not np.isfinite(x).all():
        raise TooClose(f"{what}: a value is not finite")
    nearest = np.rint(x)
    if check and x.size:
        gap = 0.5 - np.abs(x - nearest)
        if float(gap.min()) < MARGIN:
            _stop(np.atleast_1d(gap), np.atleast_1d(x), what)
    return nearest


def above(values, threshold: float, what: str):
    """`values > threshold` as a mask; stops when a value is within MARGIN of the threshold."""
    import numpy as np
    x = np.asarray(values, dtype=np.float64)
    if x.size:
        gap = np.abs(x - threshold)
        if float(gap.min()) < MARGIN:
            _stop(np.atleast_1d(gap), np.atleast_1d(x), what)
    return x > threshold


# ------------------------------------------------------------ the code path

#: What numpy, OpenBLAS and glibc are told before they load. Each is the lowest
#: common denominator: the kernels and loops that every CPU able to import the
#: pinned numpy has, so that every such CPU runs the same instructions.
CODE_PATH = {
    "OPENBLAS_CORETYPE": "Nehalem",                                        # OpenBLAS: its SSE4.2 kernels
    "OPENBLAS_NUM_THREADS": "1",                                           # and one thread: a split sum is another sum
    "NPY_DISABLE_CPU_FEATURES": "X86_V3 X86_V4 AVX512_ICL AVX512_SPR",     # numpy's own loops: its x86-64-v2 baseline
    "GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2,-FMA",                       # glibc's math: asked for the routines without FMA
}

#: cos of the first number, from glibc 2.36: by its plain routine, by its FMA
#: routine. They differ in the last bit. glibc cannot be asked which one it
#: picked; this is how `libm` tells.
WITNESS = (11.166500000000035, "0x1.5c5a94bb936abp-3", "0x1.5c5a94bb936aap-3")


def blas() -> tuple[str, int]:
    """The kernels and the thread count of the OpenBLAS numpy loaded: ("Nehalem", 1), or ("?", 0)."""
    import numpy
    for path in glob.glob(os.path.join(os.path.dirname(numpy.__file__), "..", "numpy.libs", "libscipy_openblas*.so*")):
        library, found = ctypes.CDLL(path), {}
        for what, kind in (("corename", ctypes.c_char_p), ("num_threads", ctypes.c_int)):
            for symbol in (f"scipy_openblas_get_{what}64_", f"scipy_openblas_get_{what}",
                           f"openblas_get_{what}64_", f"openblas_get_{what}"):
                if hasattr(library, symbol):
                    function = getattr(library, symbol)
                    function.restype = kind
                    found[what] = function()
                    break
        core = found.get("corename", b"?")
        return (core.decode() if isinstance(core, bytes) else str(core)), int(found.get("num_threads", 0))
    return "?", 0


def _levels() -> list[str]:
    from numpy._core._multiarray_umath import __cpu_features__ as features
    return [name for name in ("X86_V2", "X86_V3", "X86_V4", "AVX512_ICL", "AVX512_SPR") if features.get(name)]


def loaded() -> str:
    """What keeps this process off the declared code path; empty when nothing does."""
    wide = [name for name in _levels() if name in CODE_PATH["NPY_DISABLE_CPU_FEATURES"].split()]
    if wide:
        return "numpy dispatches to " + ", ".join(wide)
    core, threads = blas()
    if core != CODE_PATH["OPENBLAS_CORETYPE"] or threads != 1:
        return f"OpenBLAS runs its {core} kernels on {threads} thread(s)"
    return ""


def libm() -> str:
    """What the witness says about glibc's math. Only on glibc 2.36 does it tell the plain routine from the FMA one."""
    x, plain, fused = WITNESS
    got = math.cos(x).hex()
    return ("answers as 2.36's plain routine" if got == plain else "answers as 2.36's FMA routine" if got == fused
            else "answers as neither routine of 2.36")


def describe() -> str:
    import numpy
    core, threads = blas()
    return (f"numpy {numpy.__version__} dispatching to {' '.join(_levels()) or 'nothing named'}; "
            f"OpenBLAS {core} kernels on {threads} thread(s); glibc {platform.libc_ver()[1] or '?'}, whose cos {libm()}")


def enter(script) -> None:
    """Put a builder on the declared code path, or refuse to build.

    Call it first thing in `main()`. numpy, OpenBLAS and glibc choose their
    code when they load, so a process that started without the declared
    environment starts again with it. Then what was loaded is checked; a
    process that is not on the declared code path stops here.

    Two cases are let through with a line on stderr, because their bytes are
    not meant to be the tracked ones: PD2_CODEPATH=free (the variation test of
    `fresh.py matrix`), and a builder's `main()` called from another program,
    as the tests do.
    """
    name = Path(script).name
    if os.environ.get("PD2_CODEPATH") == "free":
        print(f"{name}: code path left to the machine (PD2_CODEPATH=free); these are not the tracked bytes", file=sys.stderr)
        return
    wanted = {key: value for key, value in CODE_PATH.items() if os.environ.get(key) != value}
    started = bool(sys.argv and sys.argv[0]) and Path(sys.argv[0]).resolve() == Path(script).resolve()
    if wanted and not started:
        print(f"{name}: code path left to the machine (called, not started); these are not the tracked bytes", file=sys.stderr)
        return
    if wanted:
        if os.environ.get("PD2_CODEPATH") == "declared":
            raise SystemExit(f"{name}: the declared code path did not survive a restart: {sorted(wanted)}")
        os.environ.update(CODE_PATH)
        os.environ["PD2_CODEPATH"] = "declared"
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.executable, list(sys.orig_argv))
    problem = loaded()
    if problem:
        raise SystemExit(f"{name}: not on the declared code path: {problem}. The tracked bytes are built with "
                         + " ".join(f"{key}={value!r}" for key, value in CODE_PATH.items()))


if __name__ == "__main__":
    enter(__file__)
    print(describe())
