"""The one table of distribution packs: name, `dist/` folder, make target and builder.

Every other place that knew a pack — `dist_paths._GROUPS`, `status.TARGETS`,
`fresh.BUILDERS`, `tools/tasks.py`, the `Makefile`, the test literals — said the same
thing in its own words, so adding or retiring a pack meant six edits and the ones that
were missed only failed somewhere else. This is the table they are checked against
(`tests/test_one_pack_table.py`): edit here first, then the view that disagrees fails.

A pack is one `<name>.zip` in `dist/<group>/` with a `<name>.zip.sha256` beside it. Its
`builder` is the argv after the interpreter, run from the repository root; several packs
may share one builder (the `heads` target writes four, from one Ada/Geralt extraction).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pack:
    """Where a pack lives and what rebuilds it."""

    name: str                    # <name>.zip in dist/
    group: str                   # dist/<group>/
    make: str                    # make -sC tools/pd2-las <make>
    builder: tuple[str, ...]     # argv after the interpreter, from the repo root
    what: str                    # one line for `status`, the README and the runbook

    @property
    def rel(self) -> str:
        return f"dist/{self.group}/{self.name}.zip"


PACKS: dict[str, Pack] = {
    pack.name: pack
    for pack in (
        Pack("Miranda_L4D2_LAS", "Miranda_L4D2", "build",
             ("tools/pd2-las/build_models.py",),
             "the L4D2 Miranda LAS outfit and its first-person arms"),
        Pack("Miranda_Romance_LAS", "Miranda_Romance", "lawson",
             ("tools/pd2-port/build_las_pack.py",),
             "the ME2 Romance LAS outfit and its first-person arms"),
        Pack("OfficeSuite", "Miranda", "honokodae",
             ("tools/pd2-las/build_honoko2_dae.py",),
             "the DOAXVV Secret Report outfit from the Collada .dae, body-only, with FPS arms"),
        Pack("OfficeSuite_Head", "Miranda", "honokodae_head",
             ("tools/pd2-las/build_honoko2_dae.py", "--only", "officesuite_head"),
             "OfficeSuite's body with the Miranda Romance head as one unit"),
        Pack("Miranda_L4D2_over_Hila", "Miranda", "heads",
             ("tools/build_joy_head_mods.py",),
             "Hila's head replaced by the L4D2 Miranda head"),
        Pack("Miranda_Romance_over_Hila", "Miranda", "heads",
             ("tools/build_joy_head_mods.py",),
             "Hila's head replaced by the ME2 Romance head"),
        Pack("Geralt_over_Rust", "Geralt", "heads",
             ("tools/build_joy_head_mods.py",),
             "Rust's head, hair and beard replaced by Geralt's"),
        Pack("Arivus_over_Hoxton", "Arivus", "heads",
             ("tools/build_joy_head_mods.py",),
             "the GTA Arivus head over Old Hoxton"),
        Pack("Miranda_Lawson_VO_over_Hila_Stream", "Miranda", "voices_stream",
             ("tools/build_hila_stream_mod.py",),
             "Miranda's voice lines as one id-keyed Wwise .stream per Hila slot"),
        Pack("Geralt_VO_over_Rust_Stream", "Geralt", "voices_geralt",
             ("tools/build_character_stream_mod.py", "--pack", "geralt-rust"),
             "Geralt's barks for the Rust slots the set covers"),
        Pack("Arivus_VO_over_Hoxton_Stream", "Arivus", "voices_arivus",
             ("tools/build_character_stream_mod.py", "--pack", "arivus-old-hoxton"),
             "Arivus' barks for the Old Hoxton slots the set covers"),
        Pack("Arivus_Head_over_Old_Hoxton_GLB", "Arivus", "glb",
             ("tools/pd2-las/build_arivus_glb_pack.py",),
             "the Arivus head as glTF + DDS, for other engines"),
    )
}

#: name -> `dist/` folder, for `dist_paths.dist_path`
GROUPS: dict[str, str] = {pack.name: pack.group for pack in PACKS.values()}

#: make target -> the name `fresh.py check --builders NAME` knows it by, where it differs
#: (fresh.py grew the builder names before the Makefile did; renaming its CLI would break
#: the recorded commands in docs and the tests that pass these names).
FRESH_NAMES: dict[str, str] = {"build": "miranda"}

#: name -> make target, for `status.TARGETS`
TARGETS: dict[str, str] = {pack.name: pack.make for pack in PACKS.values()}


def builders() -> dict[str, tuple[str, ...]]:
    """make target -> the argv that writes its packs (one builder may write several)."""
    out: dict[str, tuple[str, ...]] = {}
    for pack in PACKS.values():
        seen = out.setdefault(pack.make, pack.builder)
        if seen != pack.builder:
            raise SystemExit(
                f"packs.py: {pack.make} is claimed by two builders: {seen} and {pack.builder}"
            )
    return out


def packs_for(make: str) -> list[str]:
    return [pack.name for pack in PACKS.values() if pack.make == make]
