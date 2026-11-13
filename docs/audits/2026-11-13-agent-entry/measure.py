#!/usr/bin/env python3
"""Count what an agent pays to answer eight questions about this repository.

    python3 measure.py key   --tree T                 the answer key, from the artefacts in T
    python3 measure.py walk  --tree T --routes before the routes below, run for real in T; calls, bytes, tokens
    python3 measure.py start --tree T --routes before what each harness loads at start, per harness-loaders.md
    python3 measure.py facts --tree T                 every size, sha256, date, script, target and pack name x docs
    python3 measure.py graph --tree T                 every script under tools/ x Makefile, workflows, tests, docs
    python3 measure.py lines --tree T --base COMMIT   README.md and AGENTS.md, line by line: upstream's or ours

T is a checkout of the commit to measure. `walk` builds packs, deletes dist/ and edits docs in T, so give it
a scratch worktree, never the checkout you work in:

    git worktree add --detach ../wt-before 19ca55a && python3 measure.py walk --tree ../wt-before --routes before

A "call" is one shell command or one file read. A route starts with the instruction file in context (the one
the harnesses load) and every step must be pointed to by text the agent already has: the pointer is a regular
expression, and the run fails when it is not found there. A step with no pointer is one the documents do not
lead to; it is counted and reported as "unpointed". Bytes are those of the file read or of the command's
stdout and stderr. Tokens are tiktoken's o200k_base, when tiktoken is installed. Nothing here is estimated.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

SLIM = "Christie_LAS_Slim"
DOCS = ["README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "docs/pd2-las/HANDOFF.md", "tools/README.md",
        "tools/pd2-las/README.md", "tools/pd2-port/README.md", "tools/pd2-port/STATUS.md",
        "tools/skyrim-nif/README.md", "CONTRIBUTING.md", "models/README.md", "references/README.md"]


def tokens(text: str):
    try:
        import tiktoken
    except ImportError:
        return None
    return len(tiktoken.get_encoding("o200k_base").encode(text, disallowed_special=()))


def sh(command: str, cwd: Path, timeout: int = 1800):
    started = time.time()
    done = subprocess.run(["bash", "-c", command], cwd=cwd, capture_output=True, text=True, errors="replace",
                          timeout=timeout)
    return done.returncode, done.stdout + done.stderr, round(time.time() - started, 1)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked(tree: Path, *patterns: str) -> list[str]:
    return [line for line in sh("git ls-files -- " + " ".join(f"'{p}'" for p in patterns), tree)[1].splitlines() if line]


# --------------------------------------------------------------------------- the answer key

def key(tree: Path) -> dict:
    """Read from the zips, their sidecars, status.py, the workflow and the dated record. No agent document is read."""
    packs = {}
    for side in sorted(tree.glob("dist/*.zip.sha256")) + sorted(tree.glob("build/pd2-las/*.zip.sha256")):
        path = side.with_name(side.name[:-len(".sha256")])
        row = {"bytes": path.stat().st_size, "sha256": side.read_text().split()[0]}
        row["zip_is_sidecar"] = digest(path) == row["sha256"]
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.count("/") == 1 and name.endswith(("BUILD_INFO.json", "build_manifest.json")):
                    row["runtime_verified"] = json.loads(z.read(name)).get("runtime_verified")
        packs[str(path.relative_to(tree))] = row
    status = json.loads(sh("python3 tools/pd2-las/status.py", tree)[1])
    workflow = (tree / ".github/workflows/test.yml").read_text()
    checks = {name: bool(re.search(pattern, workflow)) for name, pattern in {
        "pyflakes": r"pyflakes um tools tests", "suite": r"pytest -q tests", "um help": r"\./bin/um --help",
        "kb": r"um kb check --index", "publish": r"um publish check \.", "fresh": r"fresh\.py check"}.items()}
    review = "docs/audits/2026-11-10-christie-slim-screenshot-review.md"
    seen = re.search(r"\b([0-9a-f]{8})…[0-9a-f]+", (tree / review).read_text()).group(1)
    slim = packs[f"dist/{SLIM}.zip"]
    return {
        "tracked_zips": len(packs), "packs_in_dist": sum(k.startswith("dist/") for k in packs),
        "every_zip_is_its_sidecar": all(p["zip_is_sidecar"] for p in packs.values()),
        "ready": status["ready"], "hint": status["hint"],
        "ci_checks": sorted(name for name, found in checks.items() if found),
        "seen_in_game": {"pack": SLIM, "date": review.split("/")[-1][:10], "record": review, "sha256_seen": seen,
                         "sha256_tracked": slim["sha256"][:8], "were_the_tracked_bytes": slim["sha256"].startswith(seen)},
        "no_in_game_flag": sorted(k for k, p in packs.items() if k.startswith("dist/") and p.get("runtime_verified") is not True),
        "packs": packs,
    }


# --------------------------------------------------------------------------- the routes

START = "AGENTS.md"     # what is in context before the first call; `start` says which harness loads what
P = "tools/pd2-las"
README = f"{P}/README.md"
# (kind, target, pointer). kind: read | run. pointer: (where the agent learned of this step, regex) or None.
# where: "start", or the number of an earlier step of the same task (its file or its output).
BEFORE = {
    "T1 set up after a sandbox restart": {
        "fixture": "rm -rf .venv dist build node_modules",
        "steps": [("run", "git checkout -- dist build node_modules", ("start", r"`git checkout -- dist build node_modules` restores")),
                  ("run", f"make -sC {P} env", ("start", rf"`make -sC {P} env` rebuilds the pinned")),
                  ("run", f"python3 {P}/status.py", ("start", rf"`python3 {P}/status\.py` says which of the two is still missing"))],
        "expect": {"ready": r'"ready": true'}},
    "T2 state of all 14 packs": {
        "steps": [("run", f"make -sC {P} status", ("start", rf"\| `make -sC {P} status` \|")),
                  ("run", ".venv/bin/python tools/pd2-port/check_all.py", ("start", r"\| `\.venv/bin/python tools/pd2-port/check_all\.py` \|")),
                  ("run", ".venv/bin/python tools/build_joy_head_mods.py", ("start", r"\| `\.venv/bin/python tools/build_joy_head_mods\.py` \|")),
                  ("run", "git status --short dist build", None)],
        "expect": {"4 pd2-las packs": r'(?s)("sha256_ok": true.*){4}', "lawson_las": r"\[ok  \] tracked pack matches its checksum",
                   "9 head packs": ("empty", 3)}},
    "T3 is everything green": {
        "steps": [("run", "uv run --with pytest pytest -q tests", ("start", r"\*\*Tests:\*\* `uv run --with pytest pytest -q tests`")),
                  ("read", README, ("start", rf"\| `{README}` \|")),
                  ("run", f"make -sC {P} test", (1, rf"make -sC {P} test ")),
                  ("run", f"make -sC {P} fresh", (1, rf"make -sC {P} fresh ")),
                  ("run", "bin/um kb check --index", ("start", r"CI also runs `um kb check --index`")),
                  ("run", ".venv/bin/python -m um kb check --index", None),
                  ("run", "bin/um publish check .", ("start", r"`um publish check \.`"))],
        "expect": {"suite": r"\d+ passed", "fresh": r"16 of 16 tracked zips", "kb": r"PASS: \d+ notes checked",
                   "publish": r"\d+ files, 0 failures", "pyflakes": ("ran", r"pyflakes"), "um help": ("ran", r"um --help")}},
    "T4 rebuild one pack and prove its bytes": {
        "steps": [("read", README, ("start", rf"\| `{README}` \|")),
                  ("run", f"make -sC {P} slim", (0, r"\| `slim` \|")),
                  ("run", f"make -sC {P} status", (0, rf"make -sC {P} status "))],
        "expect": {"the rebuilt zip is the tracked one": rf'"{SLIM}": {{[^\n]*"sha256_ok": true'}},
    "T5 was the pack seen in game, and were those the tracked bytes": {
        "steps": [("read", README, ("start", rf"\| `{README}` \|")),
                  ("read", "docs/pd2-las/HANDOFF.md", (0, r"what was seen in game and when, dead ends: `docs/pd2-las/HANDOFF\.md`"))],
        "expect": {"date": r"`Christie_LAS_Slim` \| {seen_date}", "hash seen": r"{seen_sha}"}},
    "T6 what is open": {
        "steps": [("read", README, ("start", rf"\| `{README}` \|")),
                  ("read", "tools/pd2-port/STATUS.md", ("start", r"the state of the shipped port is in `tools/pd2-port/STATUS\.md`")),
                  ("read", "tools/README.md", ("start", r"\| `tools/README\.md` \|"))],
        "expect": {"in-game sign-off": r"In-game verification", "sleeve defect": r"sleeves are open", "gloss": r"Gloss, measured and not fixed",
                   "lawson_las": r"never game-verified", "head packs": r"(?i)over_.{0,200}(unverified|no record|offline-verified)"}},
    "T7 which command rebuilds Geralt_over_Rust": {
        "steps": [],
        "expect": {"command": r"Geralt_over_Rust\.zip`[^\n]*`tools/build_joy_head_mods\.py`"}},
    "T8 a pack changed on purpose: make the suite pass again": {
        "fixture": "mutate",
        "steps": [("read", README, ("start", rf"\| `{README}` \|")),
                  ("run", f"wc -c dist/{SLIM}.zip; sha256sum dist/{SLIM}.zip", (0, r"A changed zip needs its size and sha256 in")),
                  ("run", "{sed} AGENTS.md CLAUDE.md GEMINI.md docs/pd2-las/HANDOFF.md",
                   (0, r"its size and sha256 in `AGENTS\.md`, its copies and `docs/pd2-las/HANDOFF\.md`")),
                  ("run", ".venv/bin/python -m pytest -q tests/test_las_pack.py -k quote", (0, r"\(`test_las_pack\.py`\)"))],
        "expect": {"the doc test passes": r"1 passed"},
        "teardown": "git checkout -- ."},
}
ROUTES = {"before": BEFORE}


def mutate(tree: Path) -> str:
    """Change the slim pack by one zip comment, and its sidecar with it. Returns the sed that edits the old figures."""
    path = tree / f"dist/{SLIM}.zip"
    old_size, old_sha = path.stat().st_size, digest(path)
    with zipfile.ZipFile(path, "a") as z:
        z.comment = b"changed on purpose"
    new_size, new_sha = path.stat().st_size, digest(path)
    (tree / f"dist/{SLIM}.zip.sha256").write_text(f"{new_sha}  {SLIM}.zip\n")
    return f"sed -i 's/{old_size:,}/{new_size:,}/; s/{old_sha}/{new_sha}/'"


def walk(tree: Path, routes: dict) -> dict:
    answers = key(tree)
    fill = {"{seen_date}": answers["seen_in_game"]["date"], "{seen_sha}": answers["seen_in_game"]["sha256_seen"]}
    start = (tree / START).read_text()
    out = {}
    for task, route in routes.items():
        if route.get("fixture") == "mutate":
            fill["{sed}"] = mutate(tree)
        elif route.get("fixture"):
            sh(route["fixture"], tree)
        seen, steps, ran = {"start": start}, [], []
        for number, (kind, target, pointer) in enumerate(route["steps"]):
            for token, value in fill.items():
                target = target.replace(token, value)
            if pointer and not re.search(pointer[1], seen[pointer[0]]):
                raise SystemExit(f"{task}, step {number}: nothing the agent has read says {pointer[1]!r}")
            if kind == "read":
                rc, text, seconds = 0, (tree / target).read_text(), 0.0
            else:
                rc, text, seconds = sh(target, tree)
                ran.append(target)
            seen[number] = text
            steps.append({"kind": kind, "target": target, "pointed": bool(pointer), "exit": rc, "seconds": seconds,
                          "bytes": len(text.encode()), "tokens": tokens(text)})
            print(f"   {task[:2]} {kind} {target[:70]:<70} exit {rc} {len(text.encode()):>7} B {seconds:>6} s", flush=True)
        found = {}
        for name, want in route["expect"].items():
            if isinstance(want, tuple) and want[0] == "empty":
                found[name] = steps[want[1]]["exit"] == 0 and not seen[want[1]].strip()
            elif isinstance(want, tuple):
                found[name] = any(re.search(want[1], command) for command in ran)
            else:
                for token, value in fill.items():
                    want = want.replace(token, value)
                found[name] = any(re.search(want, text) for text in seen.values())
        if route.get("teardown"):
            sh(route["teardown"], tree)
        total = lambda field: sum(step[field] or 0 for step in steps)
        out[task] = {"calls": len(steps), "unpointed": sum(not s["pointed"] for s in steps),
                     "failed_calls": sum(s["exit"] != 0 for s in steps), "bytes": total("bytes"),
                     "tokens": total("tokens") if tokens("x") else None, "seconds": round(total("seconds"), 1),
                     "answer_reached": found, "steps": steps}
    return out


# --------------------------------------------------------------------------- what loads at start

# Which files each harness puts in context for a session started in a clone. Sources: harness-loaders.md.
# A file listed twice is loaded twice; "import" marks a file whose `@AGENTS.md` line the harness expands.
LOADS = {
    "before": {
        "Claude Code": ["CLAUDE.md"], "Codex": ["AGENTS.md"], "Gemini CLI": ["GEMINI.md"],
        "Cursor (editor)": ["AGENTS.md"], "Cursor (CLI)": ["AGENTS.md", "CLAUDE.md"],
        "Copilot (VS Code, Local)": ["AGENTS.md", "CLAUDE.md"], "Copilot CLI": ["AGENTS.md"], "OpenCode": ["AGENTS.md"]},
}


def start(tree: Path, loads: dict) -> dict:
    out = {}
    for harness, files in loads.items():
        text = ""
        for name in files:
            body = (tree / name.split(":")[0]).read_text()
            text += body + ((tree / "AGENTS.md").read_text() if name.endswith(":import") else "")
        out[harness] = {"files": files, "bytes": len(text.encode()), "tokens": tokens(text)}
    return out


# --------------------------------------------------------------------------- facts x documents

def facts(tree: Path) -> list[list]:
    answers = key(tree)
    wanted = []
    for rel, pack in answers["packs"].items():
        name = Path(rel).stem
        wanted += [("size", f"{pack['bytes']:,}"), ("sha256", pack["sha256"]), ("zip", rel), ("pack", name)]
    wanted += [("pin", pin) for pin in re.findall(r"==([0-9.]+)", (tree / "tools/pd2-las/pins.txt").read_text())]
    wanted += [("target", f"make -sC tools/pd2-las {t}") for t in re.findall(r"^([a-z]+):", (tree / "tools/pd2-las/Makefile").read_text(), re.M)]
    wanted += [("script", rel) for rel in tracked(tree, "tools/*.py", "tools/*.sh")]
    docs = {doc: (tree / doc).read_text() for doc in DOCS if (tree / doc).is_file()}
    dates = sorted({d for text in docs.values() for d in re.findall(r"\b20\d\d-\d\d-\d\d\b", text)})
    wanted += [("date", d) for d in dates]
    rows = [["kind", "fact", "docs", *docs]]
    for kind, fact in dict.fromkeys(wanted):
        pattern = re.compile(rf"(?<![\w/.-]){re.escape(fact)}(?![\w-])" if kind in ("pack", "script", "zip") else re.escape(fact))
        counts = [len(pattern.findall(text)) for text in docs.values()]
        rows.append([kind, fact, sum(c > 0 for c in counts), *counts])
    return rows


# --------------------------------------------------------------------------- scripts x who reaches them

LOADERS = {"import_module", "__import__", "importorskip", "_load", "load", "load_tool", "_tool", "run_path"}


def graph(tree: Path) -> list[list]:
    """Static. A script is named by a Python file that imports it, passes its module name to a loader, or
    holds its file name in a string; by any other file that holds its path. "Reaches" follows those edges on."""
    scripts = tracked(tree, "tools/*.py", "tools/*.sh")
    by_stem, by_file = {}, {}
    for rel in scripts:
        by_stem.setdefault(Path(rel).stem, []).append(rel)
        by_file.setdefault(Path(rel).name, []).append(rel)

    def near(candidates: list[str], rel: str) -> set[str]:
        same = [c for c in candidates if Path(c).parent == Path(rel).parent]
        return set(same or candidates)

    def python_refs(rel: str) -> set[str]:
        stems, files = set(), set()
        for node in ast.walk(ast.parse((tree / rel).read_text())):
            if isinstance(node, ast.Import):
                stems |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                stems.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in LOADERS:
                stems |= {a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                files |= set(re.findall(r"(?<![\w.-])([\w-]+\.(?:py|sh))(?![\w-])", node.value))
        found = set()
        for stem in stems & set(by_stem):
            found |= near(by_stem[stem], rel)
        for name in files & set(by_file):
            found |= near(by_file[name], rel)
        return found - {rel}

    def path_refs(text: str) -> set[str]:
        hit = {rel for rel in scripts if re.search(rf"(?<![\w.-]){re.escape(rel)}(?![\w-])", text)}
        return hit | {rel for rel in scripts if rel.startswith("tools/pd2-las/")
                      and re.search(rf"\$\(HERE\)/{re.escape(Path(rel).name)}(?![\w-])", text)}

    def doc_refs(doc: str) -> set[str]:
        """Paths, and bare file names where they can only mean one script: unique, or beside the document."""
        text = (tree / doc).read_text()
        bare = set(re.findall(r"(?<![\w./-])([\w-]+\.(?:py|sh))(?![\w-])", text))
        return path_refs(text) | {rel for name in bare & set(by_file) for rel in by_file[name]
                                  if len(by_file[name]) == 1 or Path(rel).parent == Path(doc).parent}

    edges = {rel: python_refs(rel) if rel.endswith(".py") else path_refs((tree / rel).read_text()) - {rel} for rel in scripts}
    roots = {"makefile": path_refs((tree / "tools/pd2-las/Makefile").read_text()),
             "workflows": set().union(*(path_refs((tree / w).read_text()) for w in tracked(tree, ".github/workflows/*.yml"))),
             "tests": set().union(*(python_refs(t) for t in tracked(tree, "tests/*.py"))),
             "docs": set().union(*(doc_refs(d) for d in DOCS if (tree / d).is_file()))}

    def closure(direct: set[str]) -> set[str]:
        reached, queue = set(direct), list(direct)
        while queue:
            for nxt in edges[queue.pop()]:
                if nxt not in reached:
                    reached.add(nxt)
                    queue.append(nxt)
        return reached

    reach = {name: closure(direct) for name, direct in roots.items()}
    rows = [["script", *[f"{n} names it" for n in roots], *[f"{n} reaches it" for n in roots], "named by these scripts"]]
    for rel in scripts:
        users = sorted(other for other in scripts if rel in edges[other])
        rows.append([rel, *[int(rel in roots[n]) for n in roots], *[int(rel in reach[n]) for n in roots], " ".join(users)])
    return rows


# --------------------------------------------------------------------------- upstream's lines and ours

def lines(tree: Path, base: str) -> list[list]:
    rows = [["file", "line", "origin", "text"]]
    for name in ("README.md", "AGENTS.md"):
        theirs = sh(f"git show {base}:{name}", tree)[1].splitlines()
        ours = (tree / name).read_text().splitlines()
        origin = ["ours"] * len(ours)
        for tag, _, _, start_, end in difflib.SequenceMatcher(None, theirs, ours, autojunk=False).get_opcodes():
            if tag == "equal":
                origin[start_:end] = ["upstream"] * (end - start_)
        rows += [[name, number + 1, origin[number], text] for number, text in enumerate(ours)]
    return rows


def tsv(rows: list[list]) -> str:
    return "".join("\t".join(str(cell) for cell in row) + "\n" for row in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["key", "walk", "start", "facts", "graph", "lines"])
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--routes", default="before")
    ap.add_argument("--base", default="23902ef42e8ea9b077bfbbf6911eb8ea0348e55a")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    tree = args.tree.resolve()
    if args.command == "walk" and tree == Path(__file__).resolve().parents[3]:
        raise SystemExit("walk deletes dist/ and edits documents: give it a scratch worktree, not this checkout")
    commit = sh("git rev-parse HEAD", tree)[1].strip()
    if args.command in ("facts", "graph", "lines"):
        text = tsv({"facts": facts, "graph": graph}[args.command](tree) if args.command != "lines" else lines(tree, args.base))
    else:
        result = {"key": lambda: key(tree), "walk": lambda: walk(tree, ROUTES[args.routes]),
                  "start": lambda: start(tree, LOADS[args.routes])}[args.command]()
        text = json.dumps({"commit": commit, "routes": args.routes, args.command: result}, indent=1) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
