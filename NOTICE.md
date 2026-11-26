# NOTICE — what the MIT licence covers, and what it does not

`LICENSE` (MIT) covers what this repository authored: the `um` CLI, the build pipelines under
`tools/`, the skills, the knowledge base and the documentation.

It does not cover the third-party material the repository carries:

| Where | What | Whose |
|---|---|---|
| `references/` | Source character and reference mod archives (Capcom, EA/BioWare, CD Projekt, Valve/L4D2, community mods) | Their creators; see the per-archive table in [`references/README.md`](references/README.md), which names the origin of every archive |
| `dist/` | Built pack ZIPs containing game-derived meshes, textures, materials and voice lines | The respective game studios and the community modellers credited in `references/README.md` |
| `docs/renders/`, `docs/media/` | Archived screenshots and software renders of that game content | Their creators/uploaders; each capture folder's `README.md`/`manifest.json` records provenance |
| `voice_lines_vox/` | Voice-line tables derived from the packs above | The respective rights holders |

The owner of this repository ships these game-derived assets at their own call, with sources
named and credits kept. Nothing here is a licence to redistribute third-party game content, and
the MIT grant must not be read as one: if you fork this repository, the provenance obligations
follow the files.

`um publish check` lints a folder for provenance and secrets before it is shared; it is a lint,
not legal advice.
