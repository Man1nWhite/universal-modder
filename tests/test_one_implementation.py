"""One job, one implementation.

Three jobs used to be done by more than one piece of code under tools/ and were
merged on 2026-11-12 (docs/audits/2026-11-12-tool-merge.md). Each test here
fails when a second copy, or the difference between the copies, comes back.
"""
from __future__ import annotations

import ast
import json
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


# ---------------------------------------------------------------- the files that register a pack
WRITERS = [LAS / "las_pack.py", LAS / "las_outfit_pack.py", LAS / "build_christie_las.py", REPO / "tools" / "build_joy_head_mods.py"]


def _strings(path: Path) -> str:
    """Every string in the code of a file, docstrings left out."""
    tree = _tree(path)
    docs = {id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
    return "\n".join(node.value for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs)


def _pack(name: str) -> dict:
    with zipfile.ZipFile(REPO / "dist" / f"{name}.zip") as z:
        return {info.filename: z.read(info) for info in z.infolist()}


def _registrations() -> dict:
    """The four packs of tools/pd2-las, each as its own builder describes it to the one writer."""
    import build_christie_las as christie
    import las_pack

    strings = json.loads(next(data for member, data in _pack("Miranda_Busty_LAS").items() if member.endswith("english.txt")))
    busty = las_pack.PackIdentity("miranda_busty", strings["bm_askn_miranda_busty"], strings["bm_askn_miranda_busty_desc"],
                                  pack_dir_name="Miranda_Busty_LAS")
    told = {"Miranda_LAS": las_pack.registration(), "Miranda_Busty_LAS": las_pack.registration(busty)}
    for identity in christie.IDENTITIES.values():
        textures = [member.rsplit("/", 1)[-1] for member in _pack(identity.pack_dir_name)
                    if member.endswith(".texture") and "/units/" in member]
        told[identity.pack_dir_name] = christie.registration(identity, textures, True)
    return told


def test_the_registration_files_have_one_writer():
    """main.xml, the hook, the strings, the unit file, the glove adapter and the zip are written in one place.

    las_pack.py, las_outfit_pack.py and build_christie_las.py each wrote the
    first three, two of them the unit file and the zip, two the glove adapter;
    build_joy_head_mods.py had a zip writer of its own. For the same pack they
    gave the same bytes but for the differences that are now `Registration`.
    (tools/pd2-port/build_las_pack.py writes lawson_las in another layout and
    stays apart: docs/audits/2026-11-12-tool-merge.md.)
    """
    marks = {'<Hooks directory="hooks">': "main.xml", "LegendaryArmours = LegendaryArmours or {}": "the hook",
             "bm_menu_": "the strings", '<unit type="dah" slot="1">': "the unit file", "_GloveAdapter": "the glove adapter"}
    for mark, what in marks.items():
        assert [path.name for path in WRITERS if mark in _strings(path)] == ["las_outfit_pack.py"], what
    zippers = [path.name for path in WRITERS
               if any(isinstance(node, ast.Attribute) and node.attr == "ZipInfo" for node in ast.walk(_tree(path)))]
    assert zippers == ["las_outfit_pack.py"], zippers


def test_that_writer_gives_each_tracked_pack_its_files():
    """What the one writer gives for a pack is what the tracked pack has, byte for byte, and so is the zip."""
    import las_outfit_pack as writer

    for name, told in _registrations().items():
        files = _pack(name)

        def text(end):
            return next(data for member, data in files.items() if member.endswith(end)).decode("utf-8")

        assert writer.main_xml(told) == text("/main.xml"), name
        assert writer.hook_lua(told) == text(f"/hooks/{told.item_id}_las.lua"), name
        assert writer.localization(told) == text("/localization/english.txt"), name
        for unit in (told.unit, told.fps_unit):
            assert writer.render_unit_xml(unit) == text(f"/{unit.rsplit('/', 1)[-1]}.unit"), (name, unit)
        if told.glove_adapter:
            assert writer.render_glove_adapter_lua(told.item_id, name) == text(f"/hooks/{told.item_id}_glove_adapter.lua"), name
    for name in ("Miranda_LAS", "Christie_LAS_Slim", "Miranda_L4D2_over_Joy"):
        assert writer.zip_bytes(_pack(name).items()) == (REPO / "dist" / f"{name}.zip").read_bytes(), name


def test_the_flag_follows_whether_the_pack_has_a_head():
    """`replace_all` makes LAS replace the heister's head as well; `replace_body` leaves it.

    The copies of the hook differed in exactly this line, and it is no drift:
    the Miranda packs carry a head and the Christie packs do not.
    """
    import las_outfit_pack as writer

    assert set(writer.WHOLE_CHARACTER) ^ set(writer.BODY_ONLY) == {"replace_all", "replace_body"}
    for name, told in _registrations().items():
        objects = b"".join(data for member, data in _pack(name).items() if member.endswith(".object") and "/fps_" not in member)
        assert told.flags is (writer.WHOLE_CHARACTER if b'name="g_head"' in objects else writer.BODY_ONLY), name
