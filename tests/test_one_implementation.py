"""One job, one implementation.

Three jobs used to be done by more than one piece of code under tools/ and were
merged on 2026-11-12 (docs/audits/2026-11-12-tool-merge.md). Each test here
fails when a second copy, or the difference between the copies, comes back.
"""
from __future__ import annotations

import ast
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAS, PORT = REPO / "tools" / "pd2-las", REPO / "tools" / "pd2-port"
for directory in (PORT, LAS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import diesel_model  # noqa: E402
import dmodel  # noqa: E402

SEED = 0x9E3779B97F4A7C13      # the constant the idstring hash starts from


def _tools() -> list:
    return sorted((REPO / "tools").rglob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _integers(path: Path) -> set:
    return {node.value for node in ast.walk(_tree(path))
            if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool)}


def _defines(path: Path, name: str) -> bool:
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in ast.walk(_tree(path)))


# ---------------------------------------------------------------- .model
def test_the_idstring_hash_is_written_once():
    """`dmodel` carried its own port of Hash64.cs next to the one in `diesel_model`.

    The two gave the same value for every name in every model of the 16 packs
    and of the 2B templates, and for 20,000 random byte strings. A second copy
    is a second place to get it wrong, and the first sign would be a pack whose
    objects the game cannot find.
    """
    holders = [path.relative_to(REPO).as_posix() for path in _tools() if SEED in _integers(path)]
    assert holders == ["tools/pd2-las/diesel_model.py"], holders
    assert dmodel.hash64 is diesel_model.hash64
    assert dmodel.hash_str("g_body") == diesel_model.hash64(b"g_body")


def test_the_hash_is_the_one_the_tracked_models_were_named_with():
    """A model lists its names, and its objects carry the hashes of those names."""
    for name in ("Miranda_LAS", "Christie_LAS"):
        with zipfile.ZipFile(REPO / "dist" / f"{name}.zip") as z:
            member = next(n for n in z.namelist() if n.endswith(".model") and "/fps_" not in n)
            model = diesel_model.ModelFile.read(z.read(member))
        listed = {diesel_model.hash64(text) for section in model.by_type(diesel_model.CUSTOM_HASHLIST)
                  for text in diesel_model.decode_custom_hashlist(section.payload)["names"]}
        carried = [diesel_model.decode_object3d(section.payload)["name_hash"] for section in model.by_type(diesel_model.OBJECT3D)]
        assert sum(1 for value in carried if value in listed) >= 100, name
    with zipfile.ZipFile(REPO / "dist" / "lawson_las.zip") as z:
        lawson = dmodel.DieselModel.from_bytes(z.read(next(n for n in z.namelist() if n.endswith("/lawson.model"))))
    assert lawson.find_by_name("Hips"), "the reader of the port no longer finds a bone of its own pack by name"


def test_the_tag_numbers_are_written_once():
    """The 13 section kinds both readers know have one number each, in `diesel_model.TAG_NAMES`."""
    shared = set(diesel_model.TAG_NAMES)
    assert len(shared) == 13 and len(dmodel.TAGS) == 20
    assert all(dmodel.TAGS[number] == name for number, name in diesel_model.TAG_NAMES.items())
    assert not shared & _integers(PORT / "dmodel.py"), "dmodel.py spells a tag number that diesel_model.TAG_NAMES has"
    assert dmodel.TAGS_INV["geometry"] == diesel_model.GEOMETRY


def test_the_reader_of_the_port_has_no_inverse_of_its_own():
    """`dmodel.minv` was `me2_dae.minv` a second time, and nothing called it."""
    assert not hasattr(dmodel, "minv")
    assert [path.name for path in sorted(PORT.glob("*.py")) if _defines(path, "minv")] == ["me2_dae.py"]
