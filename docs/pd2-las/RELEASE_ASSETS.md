# Packs and sources in releases, not in the history

**State: tooling and manifest are in place; the tree is still tracked.** The three steps that
move the bytes out are ordered and gated below, and the first one needs a network that can reach
`uploads.github.com` — which a sandbox may not be able to.

## Why

| | now |
|---|---|
| clone of `main` | about 1.7 GB on GitHub, 419 MB of it `.git` in a shallow clone |
| working tree | 430 MB: `dist/` 189 MB, `references/` 231 MB |
| one rebuilt pack | a new 3–25 MB blob, in every clone, for ever |

The packs are outputs and the sources are inputs; neither is source code. A repository whose
history is mostly ZIPs cannot be read, grepped or diffed — which is the whole point of this one.
`assets.json` keeps what actually matters: which bytes are current.

## What is published

Two releases, each with a stable tag, so a new pack is another asset rather than a new tag:

| release | holds | files | size |
|---|---|---|---|
| `packs-v1` | every `dist/<character>/<name>.zip` and its `.sha256` | 48 | 197 MB |
| `sources-v1` | every `references/` archive the builders read | 69 | 231 MB |

- `assets.json` (tracked) is the manifest: for every file its path, size, sha256, and the flat
  asset name GitHub needs (`dist/Miranda_L4D2/Miranda_L4D2_LAS.zip` →
  `dist__Miranda_L4D2__Miranda_L4D2_LAS.zip`, since an asset name cannot contain `/`).
- **Markdown stays in git** — `references/README.md` is the provenance table `NOTICE.md` points
  at, and a clone has to be able to read it offline.
- The assets are the same third-party material `NOTICE.md` describes: not MIT, kept because a
  build that cannot read its inputs cannot reproduce a pack.

## Day to day

```sh
make -sC tools/pd2-las fetch      # the published packs and sources, into place, every sha256 checked
make -sC tools/pd2-las status     # does the tree match the published bytes?
python tools/release_assets.py remote    # does GitHub hold what the manifest says?
```

- `fetch` needs no token: the assets are served from `github.com`, and each one is hashed before
  it is moved into place, so an interrupted download leaves nothing behind.
- `status` compares each pack with the manifest instead of with `HEAD`: `tracked` means "these are
  the published bytes", `changed` means "rebuilt, not published yet", `missing` carries the
  `fetch` command.
- **Publishing a rebuilt pack:** build it, `python tools/release_assets.py upload`, then
  `python tools/release_assets.py write` and commit `assets.json` — the two-line diff that says the
  bytes changed. `upload` replaces an asset whose size or digest differs and leaves the rest alone,
  and it re-reads every asset from GitHub afterwards to prove the digests arrived.

## Moving the bytes out: the ordered runbook

Each step has a gate. Do not run a later step until the earlier gate passes; that is what keeps
the switch reversible.

### 0. Preflight (on the branch that has the packs)

```sh
python tools/release_assets.py check     # the manifest is the tree: 117 files, every sha256
git status --short                       # nothing uncommitted that matters
```

### 1. Upload

From a machine that can reach `uploads.github.com`:

```sh
python tools/release_assets.py upload            # creates both releases, uploads 117 assets
```

From anywhere, once this branch is on `main` (a `workflow_dispatch` workflow is only dispatchable
from the default branch):

```sh
gh workflow run release-assets.yml
gh run watch
```

### 2. Gate: GitHub holds the manifest's bytes

```sh
python tools/release_assets.py remote    # PASS: all 117 assets are published, with the manifest's sizes and sha256
```

This reads sizes and digests through `api.github.com` and downloads nothing. **If it does not say
PASS, stop**: untracking before this passes would leave a tree whose packs exist only in history.

### 3. Untrack

```sh
git rm -r --cached dist references
printf 'dist/\nreferences/*\n!references/README.md\n' >> .gitignore
```

Commit that with the `.gitignore` change. The files stay on disk (now ignored), so nothing local
is lost, every builder still runs, and `green` still passes; what changes is that a clone no longer
gets them and `fetch` becomes the way to get them.

Then prove it the way a new contributor would:

```sh
git clone --depth 1 <url> /tmp/fresh && cd /tmp/fresh
make -sC tools/pd2-las fetch     # 117 files, every sha256 checked
make -sC tools/pd2-las status    # every pack "tracked": byte for byte the published bytes
```

### 4. Rewrite the history (the step that shrinks the clone)

Only the repository owner can do this, and it is the one irreversible step — take a mirror copy
first, because that copy *is* the backup:

```sh
# 1. the backup: this mirror is the rollback, keep it until the rewrite is proven
git clone --mirror <url> universal-modder-backup.git
git clone --mirror <url> rewrite.git && cd rewrite.git

# 2. drop dist/ and references/ from every commit (this is the 1.7 GB)
pip install git-filter-repo
git filter-repo --invert-paths --path dist --path references

# 3. put the one Markdown file back: it is documentation, and step 3 kept it tracked
git checkout universal-modder-backup.git/main -- references/README.md
git -c user.name=you -c user.email=you@example.invalid commit -m \
  "Keep references/README.md: the provenance table is documentation, not an asset"

# 4. publish the rewritten history
git remote add origin <url>
git push --force origin 'refs/heads/*'
```

`git filter-repo` is the maintained tool; `git filter-branch` is the fallback and is 10–100×
slower. `filter-repo` removes the `origin` remote on purpose (step 4 adds it back by hand) and
refuses to run on a clone that is not fresh. Notes that matter afterwards:

- **Every clone must be re-cloned** (or `git fetch --force` plus `reset --hard origin/main`); a
  merge after a rewrite re-introduces the old blobs. Say so in the release notes.
- **Open pull requests** against the old commits cannot merge; they need a rebase onto the
  rewritten branch. Land or close them *before* the rewrite, or expect to help.
- **GitHub keeps unreachable objects reachable by SHA** until it garbage-collects. Old commit
  SHAs still resolve for a while; ask support to run `git gc --prune=now` if the old size must go
  now, and expect cached views of old commits to break.
- **Forks are unaffected** (their history is their own) and the parent `rehan-remade/universal-modder`
  keeps its own.
- The packs remain reachable in the releases and in the backup mirror; `assets.json` names them,
  so nothing depends on the old commits.

### 5. Gate: a clone is small, a fetch is complete

```sh
git clone --depth 1 <url> /tmp/tiny && du -sh /tmp/tiny/.git     # tens of MB, not hundreds
cd /tmp/tiny && make -sC tools/pd2-las fetch && make -sC tools/pd2-las green
```

## Rollback

- **Before step 4:** `git revert` the untrack commit and delete the releases (`gh release delete
  packs-v1 sources-v1`). The history is untouched, so everything is still there.
- **After step 4:** restore from the mirror copy (`git push --force` it back). Nothing else needs
  the old history: the packs are in the releases, and `assets.json` in the new history names them.

## What this does not do

- Nothing about `docs/renders/` (43 MB): those are the in-game evidence a reviewer reads, not
  build output, and they belong with the documents that cite them.
- Nothing about the fal-generated media under `docs/media/`; same reasoning.
- The `packs` CI job still rebuilds every tracked ZIP nightly — it now runs `make fetch` first, and
  that fetch is itself the check that the published bytes are complete.
