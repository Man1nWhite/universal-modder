#!/usr/bin/env python3
"""Run a script with headless `bpy`, on a machine that has no display.

    python tools/bootstrap_bpy.py --check                       # build the stubs, then stop
    python tools/bootstrap_bpy.py -- tools/pd2-las/arivus_v2_from_blend.py --check
    python tools/bootstrap_bpy.py -- tools/pd2-las/resave_arivus_blend.py --dump

Blender's Python wheel links the X11 and GL libraries a desktop Blender has. On a headless
box they are absent and `import bpy` stops at the first one
(`ImportError: libXrender.so.1: cannot open shared object file`), even though a script that
only reads mesh data never opens a window.

This compiles empty stub libraries under `build/bpy_stubs/` and loads them, with their
SONAMEs, into this process before `bpy` is imported — so the dynamic linker finds a symbol
the script never calls. What each stub has to define is read from `bpy`'s own libraries
(`nm -D --undefined-only`), not written by hand: a hand-written list missed
`XFixesShowCursor` and `glXGetVisualFromFBConfig`, and the loader stops at the first
missing symbol. The `xkb*` symbols are versioned (`xkb_context_new@V_0.5.0`), so those
stubs are linked with a version script.

The preload has to happen in the *same* process that imports `bpy`: `bpy`'s extension module
resolves its dependencies when it is loaded, so a preload in a parent that then `exec`s a
child is lost. That is why this runs the script in-process with `runpy` rather than
`os.execv`.

It is a loader shim, not a Blender replacement: `bpy` itself still has to be installed
(`pip install 'bpy==4.2.23'` to re-save a scene, `5.0.1` to read one written by 5.1) and
there is no GL context, so nothing here can render. Nothing on the build path uses it (D5):
the two Arivus-scene tools are the only callers.
"""
from __future__ import annotations

import argparse
import ctypes
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "build/bpy_stubs"

#: the SONAMEs headless `bpy` asks for, loaded in this order: the X11 libraries first, then
#: the GL ones, because a stub must be in the process before the library needing it loads.
#: A library that is a symlink on a real system (`libGL.so.1` -> `libGLX.so.0`) needs the
#: symbols of both, since the loader looks for them in the file it is asked for by name.
LIBRARIES: tuple[str, ...] = (
    "libXrender.so.1", "libXfixes.so.3", "libXi.so.6", "libXt.so.6", "libXxf86vm.so.1",
    "libXinerama.so.1", "libxkbcommon.so.0", "libSM.so.6", "libICE.so.6",
    "libGL.so.1", "libGLX.so.0", "libOpenGL.so.0", "libEGL.so.1",
)

#: which stub libraries an undefined symbol belongs to, matched as patterns: a bare `gl`
#: prefix also catches `glob64`, which the C library provides. A GL symbol goes into both
#: `libGL.so.1` and `libGLX.so.0`, because on a real system the first is a symlink to the
#: second and the loader looks for a symbol in the file it was asked for by name. First
#: match wins, so `^glX` is tested before `^gl[A-Z]`.
_OWNER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"^glX", ("libGLX.so.0", "libGL.so.1")),
    (r"^gl[A-Z]", ("libGL.so.1", "libGLX.so.0")),
    (r"^egl[A-Z]", ("libEGL.so.1",)),
    (r"^XRender", ("libXrender.so.1",)),
    (r"^XFixes", ("libXfixes.so.3",)),
    (r"^Xinerama", ("libXinerama.so.1",)),
    (r"^XF86", ("libXxf86vm.so.1",)),
    (r"^Xt[A-Z]", ("libXt.so.6",)),
    (r"^xkb_", ("libxkbcommon.so.0",)),
    (r"^(Smc|Ice)", ("libSM.so.6", "libICE.so.6")),
    # Xlib-adjacent calls `bpy` imports straight from the X libraries; the exact set differs
    # between wheels, so the whole `X` namespace is stubbed rather than listed. `libX11.so.6`
    # is on the system, so it is not one of the stubs and these all land in `libXi.so.6`.
    (r"^X[A-Z]", ("libXi.so.6",)),
    (r"^_Xi", ("libXi.so.6",)),
    (r"^_X[A-Z]", ("libXrender.so.1", "libXfixes.so.3", "libXxf86vm.so.1")),
)

#: the same patterns, as one expression, for filtering an undefined-symbol table
_WANTED = re.compile("|".join(f"(?:{pattern})" for pattern, _ in _OWNER))


def _nm(arguments: list[str], library: Path) -> list[str]:
    result = subprocess.run(["nm", *arguments, str(library)], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line.split()[-1] for line in result.stdout.splitlines() if line.split()]


def _wanted(library: Path) -> list[tuple[str, str | None]]:
    """`(symbol, version)` for every stub-provided symbol `library` imports."""
    wanted = []
    for name in _nm(["-D", "--undefined-only"], library):
        symbol, _, version = name.partition("@")
        if _WANTED.match(symbol):
            wanted.append((symbol, version or None))
    return wanted


def _owners(symbol: str) -> tuple[str, ...]:
    for pattern, libraries in _OWNER:
        if re.match(pattern, symbol):
            return libraries
    return ("libGL.so.1",)


def required_symbols(blender: Path) -> dict[str, dict[str, set[str]]]:
    """SONAME -> {"plain": symbols, "versioned": `symbol@@version`} the stubs must define."""
    wanted: dict[str, dict[str, set[str]]] = {
        name: {"plain": set(), "versioned": set()} for name in LIBRARIES}
    for library in sorted(blender.rglob("*.so")):
        for symbol, version in _wanted(library):
            for owner in _owners(symbol):
                wanted[owner]["versioned" if version else "plain"].add(
                    f"{symbol}@@{version}" if version else symbol)
    return wanted


def build(force: bool = False) -> Path:
    """Compile the stubs into `build/bpy_stubs/` and return its path."""
    import shutil

    STUBS.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise SystemExit("bootstrap_bpy: no C compiler (cc/gcc/clang) to build the stubs with")
    blender_lib = Path(sys.prefix) / "lib/python3.11/site-packages/bpy"
    if not (blender_lib / "__init__.so").is_file():
        raise SystemExit(f"bootstrap_bpy: {blender_lib} has no bpy; install the wheel first")
    wanted = required_symbols(blender_lib)
    for name in LIBRARIES:
        library = STUBS / name
        if library.is_file() and not force:
            continue
        plain = sorted(wanted[name]["plain"])
        versioned = sorted(wanted[name]["versioned"])
        if not plain and not versioned:
            plain = [name.split(".so")[0].replace("lib", "") + "_stub"]
        # every symbol needs a definition, versioned ones included: a version script only
        # *names* a version, and an entry for a symbol nothing defines is not exported
        defined = sorted({entry.partition("@@")[0] for entry in versioned} | set(plain))
        if not defined:
            defined = [name.split(".so")[0].replace("lib", "") + "_stub"]
        source = STUBS / f"{name}.c"
        source.write_text("\n".join(f"void {s}(void) {{}}" for s in defined) + "\n")
        command = [compiler, "-shared", "-fPIC", f"-Wl,-soname,{name}"]
        if versioned:
            script = STUBS / f"{name}.map"
            groups: dict[str, list[str]] = {}
            for entry in versioned:
                symbol, _, version = entry.partition("@@")
                groups.setdefault(version, []).append(symbol)
            # a version script is line oriented here: one symbol per line under `global:`,
            # and the block closes with `};` — a bare `}` or several symbols on one line is
            # a syntax error from `ld` 2.40.
            script.write_text("".join(
                f'{version} {{\n'
                "  global:\n"
                + "".join(f"    {symbol};\n" for symbol in sorted(symbols))
                + "  local: *;\n"
                "};\n"
                for version, symbols in sorted(groups.items())))
            command.append(f"-Wl,--version-script={script}")
        subprocess.run([*command, "-o", str(library), str(source)], check=True)
    return STUBS


def preload() -> None:
    """Load every stub into this process, so `bpy` finds them when it is imported."""
    for name in LIBRARIES:
        path = STUBS / name
        if not path.is_file():
            raise SystemExit(f"bootstrap_bpy: {path} is missing; run it once with --rebuild")
        ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild", action="store_true", help="recompile the stubs")
    ap.add_argument("--check", action="store_true", help="build the stubs, then exit")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="the script and its arguments, after `--`")
    args = ap.parse_args(argv)
    build(force=args.rebuild)
    if args.check:
        print(f"{STUBS.relative_to(ROOT)}: {len(LIBRARIES)} stub libraries")
        return 0
    command = [part for part in args.command if part != "--"]
    if not command:
        ap.error("no command: pass the script and its arguments after `--`")
    script = Path(command[0])
    if not script.is_absolute():
        script = Path.cwd() / script
    preload()
    sys.argv = [str(script), *command[1:]]
    import runpy

    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
