#!/usr/bin/env python3
"""The `tools/pd2-las/Makefile` targets, without make: the same commands, on Windows too.

    python tools/tasks.py                    # every target and what it does
    python tools/tasks.py status             # one JSON object: environment and every tracked pack
    python tools/tasks.py env                # once per fresh clone: pinned .venv, 2B templates
    python tools/tasks.py build              # rebuild one pack -> dist/
    python tools/tasks.py test green fresh   # the checks, in the order CI runs them
    python tools/tasks.py docs               # regenerate docs/README.md

Why this exists: the Makefile is the documented interface (`make -sC tools/pd2-las status`), and
it assumes POSIX. It hardcodes `.venv/bin/python`, shells out to `bash recover_env.sh` and lets
GNU make's own `BUILD` macro redirect each builder's log. On native Windows there is no make, no
`.venv/bin`, and the launcher is `bin/um.cmd`, so the fork's build pipeline — for Windows games
— had no supported entry point there at all. This script has no dependency beyond the standard
library (so it runs before the venv exists, like `status.py`) and calls the same scripts with the
same arguments.

Targets are kept in step with the Makefile by `tests/test_tasks.py`: every `name:  ## help` line
in the Makefile must have an entry here, and every entry here must be a Makefile target.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PD2_LAS = HERE / "pd2-las"
LOGS = ROOT / "build" / "pd2-las"

#: target -> (command after the interpreter, help). `{py}` is the venv interpreter when it exists.
TASKS: dict[str, tuple[list[str], str]] = {
    "status": (["{py}", "tools/pd2-las/status.py"], "one JSON object: environment, every tracked pack, what to run next"),
    "env": (["bash", "tools/pd2-las/recover_env.sh"], "once per fresh clone: pinned .venv, 2B composition, then status"),
    "build": (["{py}", "tools/pd2-las/build_models.py"], "Miranda_L4D2_LAS -> dist/Miranda_L4D2/"),
    "honokodae": (["{py}", "tools/pd2-las/build_honoko2_dae.py"], "OfficeSuite -> dist/Miranda/"),
    "heads": (["{py}", "tools/build_joy_head_mods.py"], "the over Hila heads, Geralt_over_Rust, Arivus_over_Hoxton -> dist/"),
    "voices_stream": (["{py}", "tools/build_hila_stream_mod.py"], "Miranda_Lawson_VO_over_Hila_Stream -> dist/Miranda/"),
    "voices_tables": (["{py}", "tools/build_stream_tables.py"], "the Rust and Old Hoxton stream tables -> voice_lines_vox/targets/"),
    "voices_char_rust": (["{py}", "tools/build_character_stream_mod.py", "--pack", "geralt-rust", "--bank", "char_rust"], "Geralt's takes onto Rust's own bank (refuses until the id map exists)"),
    "voices_sheets": (["{py}", "tools/import_voiceline_sheet.py"], "import a community voice-line sheet; needs SHEET= (and WANT=/TAB=/LEADS=1)"),
    "voices_master": (["{py}", "tools/build_vo_master.py"], "the VO source-of-truth workbook + per-tab CSVs -> voice_lines_vox/vo_master.xlsx, voice_lines_vox/vo_master/"),
    "glb": (["{py}", "tools/pd2-las/build_arivus_glb_pack.py"], "Arivus_Head_over_Old_Hoxton_GLB -> dist/Arivus/"),
    "inventory": (["{py}", "tools/pd2-las/build_las.py", "--stage", "inventory", "--out", "tools/pd2-las"], "what the source archive contains -> tools/pd2-las/source_inventory.json"),
    "audit": (["{py}", "tools/pd2-las/mip_audit.py"], "the mip levels of the face and eye textures (Markdown on stdout)"),
    "fresh": (["{py}", "tools/pd2-las/fresh.py", "check"], "every tracked pack built again and compared byte for byte"),
    "test": (["{py}", "-m", "pytest", "-q", "tests"], "the whole suite, offline"),
    "green": (["{py}", "tools/pd2-port/check_all.py", "--full"], "everything the test workflow checks, one line each"),
    "docs": (["{py}", "tools/gen_docs_index.py"], "regenerate docs/README.md"),
    "links": (["{py}", "tools/pd2-port/check_links.py"], "every relative Markdown link resolves"),
}

#: targets that write a pack and are therefore logged to build/pd2-las/<target>.log
BUILDERS = {"build", "honokodae", "heads", "voices_stream",
            "glb"}
#: `all` is the Makefile's list of every tracked pack; task order matters (heads reads the base ZIP)
ALL = ["build", "honokodae", "heads", "voices_stream",
       "glb"]


def python() -> str:
    """The pinned venv interpreter when the environment exists, else this one."""
    venv = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    return str(venv) if venv.exists() else sys.executable


#: targets that take their arguments from the environment, as the Makefile's `SHEET=...` does
ENV_ARGUMENTS: dict[str, list[tuple[str, str]]] = {
    # (environment variable, command-line flag)
    "voices_sheets": [("SHEET", "--sheet"), ("TAB", "--tab"), ("WANT", "--who")],
}


def command(target: str) -> list[str]:
    argv = [python() if part == "{py}" else part for part in TASKS[target][0]]
    for env, flag in ENV_ARGUMENTS.get(target, []):
        value = os.environ.get(env)
        if value:
            argv += [flag, value]
    if target == "voices_sheets":
        if not os.environ.get("SHEET"):
            print("usage: SHEET=references/sheets/<file>.csv python tools/tasks.py voices_sheets [WANT=Rust]",
                  file=sys.stderr)
            return []
        if os.environ.get("LEADS"):
            argv.append("--keys")
    return argv


def run(target: str) -> int:
    argv = command(target)
    if not argv:
        return 2
    LOGS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if target in BUILDERS:
        # the Makefile's BUILD macro: the builder's output goes to its log, the pack's state to stdout
        log = LOGS / f"{target}.log"
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.run(argv, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if proc.returncode:
            tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:])
            print(tail)
            print(f"FAILED: {' '.join(argv)} (the whole log: {log.relative_to(ROOT)})", file=sys.stderr)
            return proc.returncode
        code = subprocess.run([python(), "tools/pd2-las/status.py", target], cwd=ROOT).returncode
        print(f"{target}: {time.time() - t0:.1f}s, log {log.relative_to(ROOT)}", file=sys.stderr)
        return code
    return subprocess.run(argv, cwd=ROOT).returncode


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        width = max(len(t) for t in TASKS)
        print(__doc__.split("\n\n")[0])
        print()
        for name, (_, why) in TASKS.items():
            print(f"  {name:<{width}}  {why}")
        print(f"\n  {'all':<{width}}  every tracked pack, in the order the Makefile builds them")
        print("\nrun one or more: python tools/tasks.py status test")
        return 0
    if args[0] == "--json":
        print(json.dumps({k: v[1] for k, v in TASKS.items()}, indent=1))
        return 0
    targets = ALL if args == ["all"] else args
    unknown = [t for t in targets if t not in TASKS]
    if unknown:
        print(f"unknown target(s): {', '.join(unknown)}; run `python tools/tasks.py` for the list",
              file=sys.stderr)
        return 2
    for target in targets:
        print(f"== {target}: {TASKS[target][1]}", file=sys.stderr)
        code = run(target)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
