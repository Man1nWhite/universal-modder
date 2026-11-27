# CI: what runs, what must pass, how to change it

`.github/workflows/test.yml` has three jobs; there is no per-pack workflow any more (the Romance
LAS one went with its pack, D83).

| Job | Runs | Cost | Blocking? |
| --- | --- | --- | --- |
| `test` | every gate that reads the tree: checksums, ruff, mypy, links, docs index, the suite (+ coverage floor), skip budget, `um` CLI, knowledge base, publish check | ~4 min | **yes** |
| `changes` | pull requests only: did this change touch `dist/`, `tools/` or `references/`? | seconds | no, it feeds `packs` |
| `packs` | `tools/pd2-las/fresh.py check`: all 9 tracked ZIPs built again from scratch and compared byte for byte | ~15 min | on `main` yes |

`packs` runs on a push to `main`, a tag, the nightly schedule, a manual run with
`rebuild_packs`, a pull request labelled `rebuild-packs`, and — the 2026-11-26 addition — a
pull request whose `changes` job says it touched `dist/`, `tools/` or `references/`. The
label is still there for what paths cannot see: a runner image change, a new `pins.txt`
installer. Run it by hand on a branch with:

```sh
gh workflow run test.yml --ref <branch> -f rebuild_packs=true
```

## Branch rules: what is set, and how to set it again

The checks above only bind if GitHub is told to require them, and only the repository owner
can say so: the workflow token gets `403 Resource not accessible by integration` on every
ruleset write. Branch protection is a ruleset, **`main: required checks`** (id 28219531),
created 2026-11-27 and in force since; its record is readable with

```sh
gh api repos/Man1nWhite/universal-modder/rulesets/28219531
```

It is one settings change, in the browser — Settings → **Rules** → **Rulesets**. To change
it, edit that ruleset; to recreate it, **New branch ruleset** and then:

1. **Ruleset Name**: `main: required checks`.
2. **Enforcement status**: open the dropdown (it starts on *Disabled*) and pick **Active**.
   Nothing in the form applies until this is set, which is the step most often missed.
3. **Bypass list**: leave it empty so the rules apply to everyone, or — if you want an
   emergency route — **+ Add bypass** → role **Repository admin**. An empty list is the
   stronger setting; the price is that an urgent direct push to `main` waits for a pull
   request like everything else.
4. **Target branches** → **Add target** → **Include by pattern** → type **`main`** (the
   branch name alone — the form adds the `refs/heads/` itself, and typing it again stores
   `refs/heads/refs/heads/main`, a pattern that matches no branch at all and silently leaves
   `main` unprotected) → **Add Inclusion pattern**. The box then reads
   `refs/heads/main`; no "default branch" alias, so a rename does not quietly retarget it.
5. **Branch rules**, tick these four and leave the rest alone:
   - **Restrict deletions** — a branch with 1.8 GB of history is not one to delete by accident.
   - **Block force pushes** — the packs are byte-tracked; a rewritten `main` invalidates every
     `.sha256` and every clone.
   - **Require a pull request before merging** — leave the approval count at **0**: this is a
     one-person repository, and a required approval would mean approving your own PR is
     impossible rather than safer. Turn on *Dismiss stale approvals* only if approvals are
     ever required.
   - **Require status checks to pass** — after ticking it, **Add checks**, type `test`, choose
     the `test` job and confirm; repeat for `changes`. Both are job *names* from
     `.github/workflows/test.yml`.
6. Leave **Require linear history** off: `main` is merged with merge commits on purpose (the
   PR number stays in the history).
7. **Create** at the bottom.

**Do not add `packs` to the required checks.** It takes fifteen minutes and the `changes`
job already decides when it is worth them; requiring it would make every docs-only PR wait
for it, and a *skipped* job never reports the success a required check needs. It still blocks
a `main` push when it does run and fails, and the PR checks list shows it as skipped, not
green-by-default.

**Verify it took.** The browser check — Settings → Rules lists `main: required checks` as
*Active* — does not prove the pattern matches anything: a ruleset stored with the pattern
`refs/heads/refs/heads/main` is Active, has every rule, and applies to no branch. (That is
not hypothetical: the first attempt on 2026-11-27 stored exactly that, and only the check
below caught it.) Ask which rules `main` actually gets:

```sh
gh api repos/Man1nWhite/universal-modder/rules/branches/main \
  --jq '.[] | "\(.type): \(.parameters.required_status_checks // "" | tostring)"'
```

Four lines (`deletion`, `non_fast_forward`, `pull_request`, `required_status_checks`) mean it
applies — that is what `main` reports now; `[]` means the ruleset is inert, and the pattern
is the thing to look at. The ruleset's own record shows the stored pattern:

```sh
gh api repos/Man1nWhite/universal-modder/rulesets \
  --jq '.[] | .id' | xargs -I{} gh api "repos/Man1nWhite/universal-modder/rulesets/{}" \
  --jq '.conditions.ref_name.include'
```

Do the same for any other branch that should be protected. Nothing in the repository can
enforce this from the outside, which is why the steps are written here rather than only in a
workflow comment.

## The gates, and where their settings live

| Gate | Command | Settings |
| --- | --- | --- |
| lint | `python -m ruff check .` | `[tool.ruff]` in `pyproject.toml` (rules, ignores, excluded trees) |
| types | `python -m mypy` | `[tool.mypy]` — scoped to the byte-critical modules, by file list |
| tests | `python -m pytest -q -rsxX tests --cov --cov-fail-under=58` | `[tool.pytest.ini_options]`, `[tool.coverage.*]` |
| skip budget | `tools/pd2-port/check_skip_budget.py --report …` | the budget in that script |
| links, docs index | `tools/pd2-port/check_links.py`, `tools/gen_docs_index.py --check` | — |
| packs | `tools/pd2-las/fresh.py check` | `tools/pd2-las/packs.py` |

`make -sC tools/pd2-las green` runs the same list locally; `tests/test_agent_docs.py` fails if
the workflow and `check_all.py` ever run different commands.

Third-party actions are pinned to a commit with the release in a comment, and
`node-unrar-js` is pinned exactly, with `.github/dependabot.yml` moving both weekly
(`tests/test_supply_chain_pins.py` holds the line). The coverage floor is a ratchet: raise it
when the suite earns more, never lower it to make a change pass.
