# CI: what runs, what must pass, how to change it

`.github/workflows/test.yml` has three jobs. `lawson-las.yml` builds one pack on its own.

| Job | Runs | Cost | Blocking? |
| --- | --- | --- | --- |
| `test` | every gate that reads the tree: checksums, ruff, mypy, links, docs index, the suite (+ coverage floor), skip budget, `um` CLI, knowledge base, publish check | ~4 min | **yes** |
| `changes` | pull requests only: did this change touch `dist/`, `tools/` or `references/`? | seconds | no, it feeds `packs` |
| `packs` | `tools/pd2-las/fresh.py check`: all 13 tracked ZIPs built again from scratch and compared byte for byte | ~15 min | on `main` yes |

`packs` runs on a push to `main`, a tag, the nightly schedule, a manual run with
`rebuild_packs`, a pull request labelled `rebuild-packs`, and — the 2026-11-26 addition — a
pull request whose `changes` job says it touched `dist/`, `tools/` or `references/`. The
label is still there for what paths cannot see: a runner image change, a new `pins.txt`
installer. Run it by hand on a branch with:

```sh
gh workflow run test.yml --ref <branch> -f rebuild_packs=true
```

## What the repository owner must set once

The checks above only bind if GitHub is told to require them. The repository has no
branch protection and no ruleset as of 2026-11-26 (`gh api repos/…/rulesets` returns `[]`),
and the workflow token cannot create one (`403 Resource not accessible by integration`), so
this is a settings change, made once, by a person with admin rights:

- **Settings → Rules → Rulesets → New branch ruleset** for `main`: require a pull request,
  require the status checks **`test`** and **`changes`**, block force pushes, block deletion.
- Leave `packs` out of the required list: it takes fifteen minutes and the `changes` job
  already decides when it is worth them. It still blocks a push to `main` when it runs and
  fails.

Do the same for any other protected branch. Nothing in the repository can enforce this from
the outside, which is why it is written here rather than only in a workflow comment.

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
