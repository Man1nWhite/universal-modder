#!/usr/bin/env python3
"""Count what an agent pays to answer eight questions about this repository.

    python3 measure.py key   --tree T                 the answer key, from the artefacts in T
    python3 measure.py walk  --tree T --routes before the routes below, run for real in T; calls, bytes, tokens
    python3 measure.py start --tree T --routes before what each harness loads at start, per harness-loaders.md
    python3 measure.py facts --tree T                 every size, sha256, date, script, target and pack name x docs
    python3 measure.py graph --tree T                 every script under tools/ x Makefile, workflows, tests, docs
    python3 measure.py lines --tree T --base COMMIT   README.md and AGENTS.md, line by line: upstream's or ours
    python3 measure.py ledger --tree T                every line removed since 19ca55a: dropped, or moved to <file>
    python3 measure.py change --tree T                T8's starting point: the slim pack changed on purpose
    python3 measure.py packs --tree T --old COMMIT    each tracked zip of COMMIT against T's: the members that differ

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
import io
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
                  # not `status`: its sha256_ok compares the zip with a sidecar the builder has just rewritten
                  ("run", "git status --short dist build", (0, r"`git status --short dist build` lists only packs you meant to"))],
        "expect": {"the rebuilt zip is the tracked one": ("empty", 2)}},
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
                  ("run", f"make -sC {P} test", (0, rf"make -sC {P} test "))],
        "expect": {"the suite passes": ("passes", 3)},
        "teardown": "git checkout -- ."},
}
Q = rf"\| `make -sC {P} %s` \|"
AFTER = {
    "T1 set up after a sandbox restart": {
        "fixture": "rm -rf .venv dist build node_modules",
        "steps": [("run", f"make -sC {P} env", ("start", Q % "env"))],
        "expect": {"ready": r'"ready": true'}},
    "T2 state of all 14 packs": {
        "steps": [("run", f"make -sC {P} status", ("start", Q % "status"))],
        "expect": {"4 pd2-las packs": r'(?s)"Miranda_LAS": \{"is": "tracked".*"Christie_LAS_Slim": \{"is": "tracked"',
                   "lawson_las": r'"lawson_las": \{"is": "tracked"', "9 head packs": r'(?s)(_over_\w+": \{"is": "tracked".*){9}'}},
    "T3 is everything green": {
        "steps": [("run", f"make -sC {P} green", ("start", Q % "green"))],
        "expect": {"suite": r"\d+ passed", "fresh": r"16 of 16 tracked zips", "kb": r"PASS: \d+ notes checked",
                   "publish": r"\d+ files, 0 failures", "pyflakes": r"\[ok  \] lint ", "um help": r"\[ok  \] um and its command groups"}},
    "T4 rebuild one pack and prove its bytes": {
        "steps": [("run", f"make -sC {P} slim", ("start", rf"`make -sC {P} <target>`: [^\n]*`slim`"))],
        "expect": {"the rebuilt zip is the tracked one": rf'"{SLIM}": \{{"is": "tracked"'}},
    "T5 was the pack seen in game, and were those the tracked bytes": {
        "steps": [("read", "docs/pd2-las/HANDOFF.md", ("start", r"Was a pack seen in game[^\n]*`docs/pd2-las/HANDOFF\.md`"))],
        "expect": {"date": r"`Christie_LAS_Slim` \| {seen_date}", "hash seen": r"{seen_sha}"}},
    "T6 what is open": {
        "steps": [("read", README, ("start", rf'What is open \| "Next" in `{README}`'))],
        "expect": {"in-game sign-off": r"In-game verification", "sleeve defect": r"sleeves are open", "gloss": r"Gloss, measured and not fixed",
                   "lawson_las": r"`lawson_las` and the nine head packs have no record", "head packs": r"the nine head packs have no record"}},
    "T7 which command rebuilds Geralt_over_Rust": {
        "steps": [],
        "expect": {"command": r"`heads` \(the nine `\*_over_\*` packs\)"}},
    "T8 a pack changed on purpose: make the suite pass again": {
        "fixture": "mutate",
        # nothing to edit: "A rebuilt pack needs no document edited". The one call is the suite, which says so.
        "steps": [("run", f"make -sC {P} test", ("start", rf"`make -sC {P} test` is the suite"))],
        "expect": {"the suite passes": ("passes", 0)},
        "teardown": "git checkout -- ."},
}
ROUTES = {"before": BEFORE, "after": AFTER}


def zip_bytes(entries, stamp: tuple = (2020, 1, 1, 0, 0, 0)) -> bytes:
    """The zip that the one pack writer gives for these members (tools/pd2-las/las_outfit_pack.zip_bytes)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            entry = zipfile.ZipInfo(name, date_time=stamp)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            zf.writestr(entry, data)
    return buffer.getvalue()


def mutate(tree: Path) -> str:
    """Change the slim pack on purpose, the way a rebuild does. Returns the sed that edits the old figures.

    One member differs (a line break at the end of BUILD_INFO.json), the zip is what the pack writer gives
    for its members, and the sidecar is written as the builder writes it. A zip that the writer would not
    give - one with a comment, say - fails test_that_writer_gives_each_tracked_pack_its_files on any commit,
    whatever the documents say, and so measures nothing about them.
    """
    path = tree / f"dist/{SLIM}.zip"
    old_size, old_sha = path.stat().st_size, digest(path)
    with zipfile.ZipFile(path) as z:
        entries = [(info.filename, z.read(info)) for info in z.infolist()]
    if zip_bytes(entries) != path.read_bytes():
        raise SystemExit(f"{path}: this Python does not deflate as the tracked zip was deflated; "
                         "use the one the packs are built with (.venv/bin/python)")
    path.write_bytes(zip_bytes((name, data + b"\n" if name.endswith("/BUILD_INFO.json") else data) for name, data in entries))
    new_size, new_sha = path.stat().st_size, digest(path)
    (tree / f"dist/{SLIM}.zip.sha256").write_text(f"{new_sha}  dist/{SLIM}.zip\n")
    print(f"   {SLIM}: {old_size:,} B {old_sha[:12]} -> {new_size:,} B {new_sha[:12]}", flush=True)
    return f"sed -i 's/{old_size:,}/{new_size:,}/; s/{old_sha}/{new_sha}/'"


def walk(tree: Path, routes: dict, only: str = "") -> dict:
    routes = {task: route for task, route in routes.items() if not only or task[:2] in only.split(",")}
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
            elif isinstance(want, tuple) and want[0] == "passes":
                found[name] = steps[want[1]]["exit"] == 0 and bool(re.search(r"\d+ passed", seen[want[1]]))
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
    "after": {
        "Claude Code": ["AGENTS.md"], "Codex": ["AGENTS.md"], "Gemini CLI": ["GEMINI.md:import"],
        "Cursor (editor)": ["AGENTS.md"], "Cursor (CLI)": ["AGENTS.md"],
        "Copilot (VS Code, Local)": ["AGENTS.md"], "Copilot CLI": ["AGENTS.md", "GEMINI.md"], "OpenCode": ["AGENTS.md"]},
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


# --------------------------------------------------------------------------- every removed line

D_COPY = "dropped: a byte-for-byte copy of AGENTS.md"
D_UP = "dropped: upstream's presentation of the toolkit, in upstream's README; no agent acts on it here"
D_STATUS = "dropped: `make -sC tools/pd2-las status` prints it"
SAME = "moved to %s (reworded in place)"
PORT = SAME % "tools/pd2-port/README.md"
NEW_STATUS = "moved to tools/pd2-port/STATUS.md"
NOT_RELEASED = "the release serves the build of 282703f and the tracked pack is ten rebuilds later (tools/pd2-port/STATUS.md)"
# old file -> (first line, last line, what became of the lines in that range), on the base commit's numbering
LEDGER = {
    "AGENTS.md": [
        (3, 5, SAME % "AGENTS.md"), (7, 11, "moved to AGENTS.md, \"Modding any other game\""),
        (12, 18, "moved to AGENTS.md, Rules: \"Keep the state in a command\""), (19, 20, "moved to AGENTS.md, \"Modding any other game\""),
        (23, 26, "dropped: `uv tool install` of rehan-remade installs upstream, not this fork; every document calls `bin/um` by path"),
        (27, 36, "dropped: `bin/um --help` prints the command groups"),
        (37, 40, "moved to README.md (the MCP config files)"), (41, 44, "moved to AGENTS.md, Tools (two lines); the OAuth endpoint is in skills/fal-assets/SKILL.md"),
        (45, 51, "moved to AGENTS.md, Tools; the six example names dropped: `ls examples/`"), (71, 72, SAME % "AGENTS.md"),
        (75, 76, "dropped: `uv run --with pytest` exits 127 where there is no uv and is not the pinned environment; AGENTS.md now names `make -sC tools/pd2-las test` and `green`"),
        (80, 94, D_STATUS + " (packs, sizes, the target that rebuilds each); which archive feeds which pack was already in models/README.md and references/README.md"),
        (96, 104, "moved to AGENTS.md (the table of questions)"),
        (106, 106, "moved to AGENTS.md (the first row and the last bullet); the restore itself moved into tools/pd2-las/recover_env.sh"),
        (108, 126, "moved to tools/README.md, word for word")],
    "CLAUDE.md": [(1, 127, D_COPY + "; Claude Code 2.1.277 and later reads AGENTS.md where there is no CLAUDE.md")],
    "GEMINI.md": [(1, 127, D_COPY + "; replaced by the one line `@AGENTS.md`, which Gemini CLI expands")],
    "README.md": [
        (1, 28, D_UP), (29, 66, "moved to tools/README.md (what each pipeline builds, pack layout, install, previews); the audit counts dropped: check_all.py prints them"),
        (67, 76, "dropped: docs/pd2-las/HANDOFF.md, \"Seen in game\", is the home. This README said the four L4D2 head packs were tested in game on 2026-11-05; the tracked zips are later rebuilds, so the README was the one that was wrong"),
        (77, 81, "dropped: the guide is linked from tools/pd2-port/README.md, the boundary is tools/README.md"),
        (82, 89, "dropped: tools/pd2-las/README.md, \"Do not\", and the two audits it names already say it"),
        (90, 104, "dropped: every command in the table installs rehan-remade/universal-modder, which has no tools/ and no dist/; replaced by the table of what each harness reads in a clone"),
        (105, 109, SAME % "README.md"), (110, 118, "dropped: installs upstream; plugins/opencode/README.md"),
        (119, 133, "dropped: skills/fal-assets/SKILL.md holds it"), (134, 289, D_UP), (290, 300, "moved to README.md (one line: licence, credits upstream)"), (301, 305, D_UP)],
    "docs/pd2-las/HANDOFF.md": [
        (5, 6, SAME % "docs/pd2-las/HANDOFF.md"), (15, 17, SAME % "docs/pd2-las/HANDOFF.md"),
        (19, 34, D_STATUS + " (size, sha256) and dist/<name>.zip.sha256 holds the hash; what each pack is: tools/README.md; what builds it: tools/pd2-las/Makefile"),
        (36, 39, SAME % "docs/pd2-las/HANDOFF.md"),
        (50, 52, SAME % "docs/pd2-las/HANDOFF.md" + ": the flag is `false` in every pack since 2026-11-13 (DECISIONS.md, D31)"),
        (58, 58, SAME % "docs/pd2-las/HANDOFF.md" + ": the rebuild of 2026-11-13 added")],
    "tools/README.md": [
        (1, 22, SAME % "tools/README.md" + "; the list of zip names dropped: `status` prints it"),
        (24, 40, "dropped: \"No code to deduplicate\" and \"234 tests\" were measured on 2026-10-19 and are contradicted by docs/audits/2026-11-12-tool-merge.md, which found jobs done in more than one place and merged some; the dialect and release points moved to tools/README.md, \"Sharing code between the trees\""),
        (42, 49, "moved to tools/README.md, \"Sharing code between the trees\"; \"unifying files across the two trees: no\" dropped, the 2026-11-12 merge did it under the byte rule")],
    "tools/pd2-las/README.md": [
        (4, 6, SAME % "tools/pd2-las/README.md"), (17, 18, SAME % "tools/pd2-las/README.md"),
        (20, 21, "dropped: \"Done\" is what `status` and `fresh` compute; \"Open\" pointed at Next in the same file"),
        (27, 45, SAME % "tools/pd2-las/README.md"),
        (46, 47, "dropped: no document quotes a size or a sha256 any more, so a changed zip needs none edited"),
        (66, 66, SAME % "tools/pd2-las/README.md"), (107, 108, SAME % "tools/pd2-las/README.md"),
        (130, 130, "dropped: `bin/um kb search` finds the note")],
    "tools/pd2-port/README.md": [
        (22, 23, PORT + "; \"published by the release workflow\" corrected: " + NOT_RELEASED),
        (34, 43, PORT + ": STATUS.md is the dated record now; \"Its pack facts are pinned by tests\" went with that test"),
        (45, 54, PORT),
        (64, 66, PORT + "; \"published as the release asset\" and \"v1 kept for comparison\" dropped: " + NOT_RELEASED + ", and there is no v1 release"),
        (89, 94, PORT + "; \"default 0.1.2\" dropped: `VERSION` in build_las_pack.py holds it"),
        (97, 114, PORT + ", one line per command; \"(16 mutations)\" dropped: check_all.py --full prints the count"),
        (119, 122, PORT + "; \"exactly what the release serves\" dropped: " + NOT_RELEASED + "; the two pinned versions dropped: tools/pd2-las/pins.txt is the one place they are written"),
        (254, 256, "dropped: check_all.py prints the counts"),
        (257, 257, "moved to tools/pd2-port/STATUS.md, \"Found and settled\" (the green channel)"),
        (262, 264, PORT + "; \"16/16\" dropped: check_all.py --full prints it"),
        (267, 269, PORT + "; \"five ways\" dropped: check_all.py prints the count"),
        (282, 284, PORT + ", corrected: \"the bytes are identical\" was wrong, " + NOT_RELEASED + "; the installer is sent to dist/lawson_las.zip"),
        (296, 297, PORT + "; \"the latest release is lawson-las-v2\" dropped: the newest file in tools/pd2-port/releases/ says it"),
        (311, 314, PORT + ", rewritten: STATUS.md quotes no figure of the tracked pack, so step 3 is to record the release there; "
                   "test_the_status_page_says_whether_the_release_serves_the_tracked_pack holds it"),
        (323, 326, PORT + "; \"always downloadable\" dropped: an artifact belongs to one workflow run and expires"),
        (330, 332, PORT + "; the in-game record is tools/pd2-port/STATUS.md, \"Seen in game\""),
        (335, 337, PORT + "; the heights dropped: the `target_ops` docstring in rig_target.py has them"),
        (342, 345, "dropped: \"Guide compliance\" in the same file lists these rules, and names the knowledge note now"),
        (346, 350, "dropped: \"Pipeline\", stage 2, and the comments under \"Build\" in the same file say it")],
    "tools/pd2-port/STATUS.md": [
        (1, 4, NEW_STATUS + ", the header: rewritten on 2026-11-13 as the dated record"),
        (6, 29, "dropped: a note that listed which sections below it were stale; those sections are gone. What it said of the transfer today is under \"Found and settled\""),
        (31, 35, "dropped: tools/pd2-port/README.md is where to start, and the header says so"),
        (37, 45, NEW_STATUS + ", \"Released and tracked\" and \"Seen in game\"; the tracked size and sha256 dropped: `make -sC tools/pd2-las status` prints them; "
                 "\"the v1 release stays up\" corrected: there is none; the Docs row dropped: README, \"Publish a release\""),
        (47, 48, "dropped: tools/pd2-port/README.md, \"Install\""),
        (50, 58, "dropped: tools/pd2-port/README.md and AGENTS.md give the two commands; the timings were stale by the page's own note"),
        (60, 73, "dropped: check_all.py and `make -sC tools/pd2-las green` print today's results; the G1 warning is under \"Found and settled\""),
        (75, 99, NEW_STATUS + ", \"Found and settled\", shortened; \"See §6 for the planned fix\" dropped: the transfer was replaced (the `target_ops` docstring)"),
        (101, 113, NEW_STATUS + ", \"Found and settled\" (the green channel)"),
        (115, 118, "dropped: the transfer was rebuilt another way by 2026-10-22; \"Corrections\" says so"),
        (120, 129, "dropped: constraint 1 was overtaken (the core now moves rigidly at 1:1: the `target_ops` docstring); 2 is audit check N3; 3 is the guide audit (README, \"Guide compliance\")"),
        (131, 135, "dropped: the `target_ops` docstring in rig_target.py has the heights"),
        (136, 146, NEW_STATUS + ", \"Dead ends\""),
        (147, 149, "dropped: the tear angles of the transfer of 2026-10-19, which is no longer in the tree"),
        (150, 157, NEW_STATUS + ", \"Dead ends\""),
        (158, 162, "dropped: struck through and marked done on 2026-11-11 in the line itself"),
        (164, 174, "dropped: a proposal for the transfer of 2026-10-19; the transfer was built another way"),
        (176, 180, "dropped: `make -sC tools/pd2-las env` makes the environment and tools/pd2-las/pins.txt is the one place the versions are written"),
        (181, 185, "moved to tools/pd2-port/README.md, \"Build\""),
        (186, 188, "moved to tools/pd2-port/README.md, \"Publish a release\""),
        (189, 196, "dropped: tools/pd2-port/README.md, \"Inputs and outputs\", and `make -sC tools/pd2-las env`"),
        (197, 198, "dropped: `make -sC tools/pd2-las green` runs both"),
        (199, 199, "dropped: AGENTS.md, Rules"),
        (201, 223, "dropped: the branch it describes is gone and both lines of work are in main; \"Corrections\" says so"),
        (225, 244, "dropped: tools/pd2-port/README.md names every one of these files under \"Build\", \"Pipeline\" and \"What is reusable\"")],
    "tools/skyrim-nif/README.md": [
        (12, 13, SAME % "tools/skyrim-nif/README.md" + "; \"91/91 checks\" dropped: docs/skyrim-nif/CROSSCHECK.md has the count"),
        (25, 34, "dropped: both commands stop without 1.zip..5.zip, which were removed with the port; the README says so now, and `--help` of "
                 "inventory.py and crosscheck.py gives each command"),
        (36, 36, "dropped: a comment, \"one file, ad hoc\"; the sentence above the example says it"),
        (73, 74, SAME % "tools/skyrim-nif/README.md" + ", in the past tense: measured while the archives were in the tree"),
        (84, 84, SAME % "tools/skyrim-nif/README.md" + "; \"91/91\" dropped: docs/skyrim-nif/CROSSCHECK.md has the count")],
}


def ledger(tree: Path, base: str) -> list[list]:
    rows = [["file", "line", "what became of it", "text"]]
    for name, rules in LEDGER.items():
        old = sh(f"git show {base}:{name}", tree)[1].splitlines()
        new = (tree / name).read_text().splitlines() if (tree / name).is_file() else []
        for tag, first, last, _, _ in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
            for number in range(first + 1, last + 1) if tag in ("delete", "replace") else ():
                if old[number - 1].strip():
                    fate = [text for lo, hi, text in rules if lo <= number <= hi]
                    if len(fate) != 1:
                        raise SystemExit(f"{name}:{number} is removed and {len(fate)} ledger rules cover it")
                    rows.append([name, number, fate[0], old[number - 1]])
    return rows


# --------------------------------------------------------------------------- what a rebuild changed in a pack

def packs(tree: Path, old: str) -> list[str]:
    """Every tracked zip as COMMIT holds it against the file in T: which members differ, and in JSON which keys."""
    def fields(z):
        return [(i.filename, i.date_time, i.compress_type, i.external_attr, i.create_system, i.flag_bits, i.extra, i.comment)
                for i in z.infolist()]

    out = []
    for rel in tracked(tree, "dist/*.zip", "build/pd2-las/*.zip"):
        if sh(f"git rev-parse {old}:'{rel}'", tree)[1].strip() == sh(f"git hash-object '{rel}'", tree)[1].strip():
            continue
        was = subprocess.run(["git", "show", f"{old}:{rel}"], cwd=tree, capture_output=True, check=True).stdout
        now = (tree / rel).read_bytes()
        a, b = zipfile.ZipFile(io.BytesIO(was)), zipfile.ZipFile(io.BytesIO(now))
        out.append(f"{rel}: {len(was):,} B {hashlib.sha256(was).hexdigest()[:8]}… -> {len(now):,} B "
                   f"{hashlib.sha256(now).hexdigest()[:8]}…; {len(a.infolist())} -> {len(b.infolist())} members, "
                   + ("the same names, order and zip fields" if fields(a) == fields(b) else "OTHER names, order or zip fields"))
        for name in sorted(set(a.namelist()) | set(b.namelist())):
            x = a.read(name) if name in a.namelist() else None
            y = b.read(name) if name in b.namelist() else None
            if x == y:
                continue
            if x is None or y is None:
                out.append(f"   {name}: in one of the two only")
                continue
            line = f"   {name}: {len(x):,} -> {len(y):,} B"
            if name.endswith(".json"):
                p, q = json.loads(x), json.loads(y)
                line += "; keys that differ: " + ", ".join(
                    f"{k} {json.dumps(p.get(k))} -> {json.dumps(q.get(k))}" for k in sorted(set(p) | set(q)) if p.get(k) != q.get(k))
            out.append(line)
    return out or [f"every tracked zip is what {old} holds"]


def tsv(rows: list[list]) -> str:
    return "".join("\t".join(str(cell) for cell in row) + "\n" for row in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["key", "walk", "start", "facts", "graph", "lines", "ledger", "change", "packs"])
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--routes", default="before")
    ap.add_argument("--base", default="23902ef42e8ea9b077bfbbf6911eb8ea0348e55a", help="lines: the merge base with upstream")
    ap.add_argument("--ledger-base", default="19ca55adb9bc31842b0c89de55d49e09d0566274", help="ledger: the commit before the change")
    ap.add_argument("--only", default="", help="walk: the tasks to run, by number: T4,T5")
    ap.add_argument("--old", default="HEAD", help="packs: the commit whose zips T's are compared with")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    tree = args.tree.resolve()
    if args.command in ("walk", "change") and tree == Path(__file__).resolve().parents[3]:
        raise SystemExit(f"{args.command} changes tracked files: give it a scratch worktree, not this checkout")
    if args.command == "change":
        mutate(tree)
        return 0
    commit = sh("git rev-parse HEAD", tree)[1].strip()
    if args.command == "packs":
        text = "\n".join(packs(tree, args.old)) + "\n"
    elif args.command in ("facts", "graph", "lines", "ledger"):
        text = tsv({"facts": facts, "graph": graph}[args.command](tree) if args.command in ("facts", "graph")
                   else lines(tree, args.base) if args.command == "lines" else ledger(tree, args.ledger_base))
    else:
        result = {"key": lambda: key(tree), "walk": lambda: walk(tree, ROUTES[args.routes], args.only),
                  "start": lambda: start(tree, LOADS[args.routes])}[args.command]()
        text = json.dumps({"commit": commit, "routes": args.routes, args.command: result}, indent=1) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
