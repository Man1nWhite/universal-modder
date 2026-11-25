"""The files that register a PAYDAY 2 LAS pack, written once for every pack built here.

The registration contract is the 2B reference's, studied as a spec: a hook on
`HOOK_SOURCE` that fills `LegendaryArmours.<item id>`, a BeardLib `main.xml`,
the menu strings, and per unit a `.unit` and an `.object`. What a pack chooses
is a `Registration`; `las_pack.py` (the Miranda packs) calls them, and so does any
future body-only LAS pack. The icon and the reproducible zip are here too.

A unit path ends in the file stem, exactly like `units/2b/skins/2b/2b`: LAS
looks it up as a unit, so a directory there loads nothing at all. The
first-person unit is optional, because an LAS entry whose `fps_unit` points at
a missing file is worse than one without it.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

HOOK_SOURCE = "lib/tweak_data/armorskinstweakdata"
#: the glove adapter is hooked here, which runs after LAS's loader; hooked where the
#: outfit is declared it would run before it
GLOVE_HOOK_SOURCE = "lib/tweak_data/blackmarkettweakdata"

# LAS maps each flag onto the character parts it replaces (see the mod's
# hooks/outfits/loader.lua): replace_all sets head=true as well, replace_body
# only body/hands/arms. An outfit that ships no head must not claim
# replace_all, or LAS drops the heister's head and the unit is decapitated.
BODY_ONLY = (
    "hide_mask",
    "hide_armor",
    "replace_body",
    "fps_hide_armor",
    "fps_replace_body",
)
#: for an outfit that brings its own head: the one line in which the hook of a
#: pack with a head and the hook of a pack without one differ
WHOLE_CHARACTER = (
    "hide_mask",
    "hide_armor",
    "replace_all",
    "fps_hide_armor",
    "fps_replace_body",
)


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Registration:
    """What one pack tells BeardLib and LAS about itself: main.xml, the hook, the strings.

    Every pack built here is registered by the functions
    below. What a pack chooses is here, as data: `registration` in las_pack.py
    says what each family chooses.
    """
    item_id: str
    display_name: str
    description: str
    unit: str                       # the third-person unit, the way LAS loads it
    flags: tuple                    # BODY_ONLY or WHOLE_CHARACTER
    fps_unit: str | None = None     # None: no first-person unit is registered
    category: str | None = None     # None: the item id
    icon: str | None = None         # None: guis/dlcs/<item id>/armor_skins/<item id>
    hook_file: str | None = None    # None: <item id>_las.lua
    # <df_nm> names a pair by its base name; the engine appends _df/_nm itself.
    # Given the full "outfit_body_df" it looks for outfit_body_df_df.texture,
    # which silently leaves every material untextured (flat black in game).
    pairs: tuple = ()
    textures: tuple = ()            # textures registered on their own, by full name
    glove_adapter: bool = False     # the pack ships <item id>_glove_adapter.lua
    # <item id>_own_hands.lua: default gloves resolve to no unit and the stock hands
    # stay hidden, so the outfit's own body is what shows - its modelled hands, or
    # the cut where they would be. A glove the player picks by hand still spawns and
    # wins (the user's rule, D58/D60).
    own_hands: bool = False

    def __post_init__(self) -> None:
        lua_keywords = {"and", "break", "do", "else", "elseif", "end", "false", "for",
                        "function", "goto", "if", "in", "local", "nil", "not", "or",
                        "repeat", "return", "then", "true", "until", "while"}
        if (not isinstance(self.item_id, str)
                or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.item_id) is None
                or self.item_id in lua_keywords):
            raise ValueError(f"item_id must be a non-keyword Lua identifier: {self.item_id!r}")
        if self.glove_adapter and self.own_hands:
            raise ValueError("glove_adapter and own_hands are mutually exclusive")


def hook_lua(told: Registration) -> str:
    """The hook on `HOOK_SOURCE` that adds the outfit to `LegendaryArmours`."""
    flags = ",\n".join(f"\t{k} = true" for k in told.flags)
    lines = [
        "LegendaryArmours = LegendaryArmours or {}",
        "la = LegendaryArmours",
        "",
        f"la.{told.item_id} = {{",
        f'\tcategory = "{told.category or told.item_id}",',
        "",
        f'\tunit = "{told.unit}",',
    ]
    if told.fps_unit:
        lines.append(f'\tfps_unit = "{told.fps_unit}",')
    lines += ["", flags]
    lines += ["}", ""]
    return "\n".join(lines)


def localization(told: Registration) -> str:
    return json.dumps(
        {
            f"bm_menu_{told.item_id}_armor_skins": told.display_name,
            f"bm_askn_{told.item_id}": told.display_name,
            f"bm_askn_{told.item_id}_desc": told.description,
        },
        indent=2,
    )


def _xml_attr(value: str) -> str:
    """Escape text for a double-quoted XML attribute."""
    return xml_escape(str(value), {'"': "&quot;"})


def main_xml(told: Registration) -> str:
    """The BeardLib mod table: the strings, the hooks, and every file under assets/ by name."""
    icon = told.icon or f"guis/dlcs/{told.item_id}/armor_skins/{told.item_id}"
    hook_file = told.hook_file or f"{told.item_id}_las.lua"
    hooks = [f'\t\t<hook file="{_xml_attr(hook_file)}" source_file="{_xml_attr(HOOK_SOURCE)}"/>']
    if told.glove_adapter:
        adapter_hook = f"{told.item_id}_glove_adapter.lua"
        hooks.append(f'\t\t<hook file="{_xml_attr(adapter_hook)}" '
                     f'source_file="{_xml_attr(GLOVE_HOOK_SOURCE)}"/>')
    if told.own_hands:
        own_hands_hook = f"{told.item_id}_own_hands.lua"
        hooks.append(f'\t\t<hook file="{_xml_attr(own_hands_hook)}" '
                     f'source_file="{_xml_attr(GLOVE_HOOK_SOURCE)}"/>')
    hook_lines = "\n".join(hooks)
    pairs = "\n".join(f'\t\t\t\t<df_nm path="{_xml_attr(base)}"/>' for base in told.pairs)
    singles = "".join(f'\t\t\t\t<texture path="{_xml_attr(name)}"/>\n' for name in told.textures)
    units = [told.unit] + ([told.fps_unit] if told.fps_unit else [])
    unit_lines = "\n".join(f'\t\t\t\t<unit_mat path="{_xml_attr(u)}"/>' for u in units)
    return (
        f'<table name="{_xml_attr(told.display_name)}" image="{_xml_attr(icon)}">\n'
        "\n"
        '\t<Localization directory="localization" default="english.txt"/>\n'
        "\n"
        '\t<Hooks directory="hooks">\n'
        f"{hook_lines}\n"
        "\t</Hooks>\n"
        "\n"
        '\t<AddFiles directory="assets">\n'
        "\n"
        f'\t\t\t\t<texture path="{icon}"/>\n'
        f"{pairs}\n"
        f"{singles}"
        "\n"
        f"{unit_lines}\n"
        "\n"
        "\t\t\t\t</AddFiles>\n"
        "</table>\n"
    )


def render_glove_adapter_lua(item_id: str, label: str) -> str:
    """Compat hook that gives the outfit vanilla-suit glove behaviour.

    LAS 4.1.9's `hooks/outfits/loader.lua` breaks changeable gloves for every
    outfit it registers (verified against the mod's real source):

    * ``output.default_glove_id = output.default_glove_id or false`` reads the
      fresh ``output`` table instead of the outfit's ``data``, so every LAS
      outfit ends up with ``default_glove_id = false``. BeardLib's
      ``GloveTweakData:get_glove_value`` returns ``false`` for "Default" gloves
      when the style's ``default_glove_id`` is ``false`` — no glove unit spawns,
      and with ``body_replacement.hands = true`` the stock hands are hidden, so
      the character has NO HANDS AT ALL. Vanilla changeable-glove suits avoid
      this via ``suit_default_gloves[style] = "heist_default"`` (BeardLib copies
      it into ``default_glove_id``), so "Default" always resolves to a real
      glove unit (``hnd_glv_heistwrinkled``).
    * ``output.glove_adapter = output.glove_adapter or false`` has the same
      fresh-table bug, disabling the bare-forearm adapter; and
    * any ``replace_body`` / ``replace_all`` outfit is inserted into
      ``tweak_data.blackmarket.glove_adapter.player_style_exclude_list``.

    This PostHook runs after LAS (the pack loads after its dependency) and
    restores the vanilla mechanism on both the style and each remapped character
    override: a real ``default_glove_id``, the adapter re-enabled, every exclude
    entry removed, and ``body_replacement.hands`` set to ``false`` so the
    heister's own stock hands remain visible as a guaranteed fallback (the glove
    spawn is not reliable in-game); any glove unit that does spawn sets
    ``var_hands_replace = 1`` and replaces the stock hands, so there are no
    double hands. Works in both TPP and FPS — BeardLib retargets the same
    glove/adapter spawn to the camera unit for the local peer.

    Traps it avoids:

    * the adapter is enabled with an empty *table*, never a boolean ``true``:
      BeardLib does ``table.merge(final_adapter_data, ...adapter_data)`` and its
      ``table.merge`` calls ``pairs(new_table)``, so a boolean would raise
      ``pairs(true)``. An empty table keeps the default ``hnd_forearms`` adapter.
    * ``default_glove_id`` cannot be set through the outfit's data.xml — LAS's
      fresh-table read drops it — so a PostHook override is the only route.

    One text serves every pack built in this directory: `item_id` names the
    outfit, `label` the pack in the first line of the file.
    """
    key = f"las_{item_id}"
    return f"""-- {label} LAS: vanilla-suit glove behaviour for {key}.
-- This outfit ships NO hands (cut at the wrist), so the heister's own gloves
-- must spawn: LAS forces default_glove_id = false (no hands at all) and
-- disables the glove adapter. Restore a real default glove, re-enable the
-- adapter, and keep the stock hands visible as fallback.
-- See las_outfit_pack.render_glove_adapter_lua for the full rationale.
Hooks:PostHook(BlackMarketTweakData, "init", "{item_id}_GloveAdapter", function(self)
\tlocal ps = self.player_styles and self.player_styles["{key}"]
\tif not ps then return end

\tlocal function restore_gloves(style)
\t\tif not style then return end

\t\t-- A real default glove, exactly like the vanilla/DLC suits (LAS's
\t\t-- fresh-table read drops this, leaving "Default" gloves with no unit).
\t\tstyle.default_glove_id = "heist_default"

\t\t-- Enable the adapter with a table (NOT a boolean: BeardLib's table.merge
\t\t-- would call pairs(true)). An empty table keeps the default hnd_forearms.
\t\tstyle.glove_adapter = {{}}

\t\t-- Keep stock hands visible as a guaranteed fallback.
\t\tif style.body_replacement then style.body_replacement.hands = false end
\t\tif style.third_body_replacement then style.third_body_replacement.hands = false end
\tend

\t-- LAS remaps every character_override independently, so character-specific
\t-- values take precedence over the style-level values in get_player_style_value.
\trestore_gloves(ps)
\tfor _, character in pairs(ps.characters or {{}}) do
\t\trestore_gloves(character)
\tend

\t-- LAS inserts once for the style and again for each replace_body character.
\t-- Walk backwards so every copy is removed without skipping adjacent entries.
\tlocal list = self.glove_adapter and self.glove_adapter.player_style_exclude_list
\tif list then
\t\tfor i = #list, 1, -1 do
\t\t\tif list[i] == "{key}" then table.remove(list, i) end
\t\tend
\tend
end)
"""


def render_own_hands_lua(item_id: str, label: str) -> str:
    """Hook that gives an outfit no default glove, so nothing is drawn over it.

    The rule (D58, extended by D60): the outfit's own body is what shows on the
    arms. An outfit that models hands into its unit shows those hands; an outfit
    whose hands are cut off shows the cut - and in neither case does the game
    spawn a glove the player did not ask for. A glove the player deliberately
    equips still spawns and wins, the way the game normally treats a chosen
    glove, and that is the only thing that puts a hand on a handless outfit.

    What this pins, and why it needs saying at all:

    * LAS 4.1.9's loader sets ``default_glove_id = false`` on every outfit it
      registers (a fresh-table read, ``las_loader_4.1.9.lua:30``), and
      BeardLib's ``get_glove_value`` returns ``false`` for "Default" gloves when
      that field is ``false``. So "Default" already resolves to no unit and the
      outfit's own hands show — but that is an *upstream bug* that this pack
      depends on, not a promise from the pack. If LAS ever fixes the fresh-table
      read, ``default_glove_id`` would pick up a real glove
      (``heist_default``), a glove unit would spawn over the modelled hands, and
      nothing in this pack would say so.
    * Setting it to ``false`` *here*, after LAS has run, makes that the pack's
      stated default: no glove unit for "Default", whatever LAS does now or
      later.
    * ``body_replacement.hands`` stays **true**, as LAS sets it for
      ``replace_all``/``replace_body``. That is not a detail: BeardLib treats
      ``get_glove_value() == false`` as "no glove unit", and the stock hands are
      hidden only while ``hands`` is true - so what the outfit's own body has on
      its arms is all there is. Setting ``hands = false`` here (the opposite of
      the adapter hook) would reveal the heister's bare stock hands next to the
      modelled ones, and on a cut-handed outfit it would leave a strip of vanilla
      wrist skin between the sleeve and the cut, which is the double-hands
      failure the adapter hook warns about.

    What it deliberately does **not** do: it does not touch the glove
    *exclude* list, the ``glove_adapter`` entry, or the glove entries
    themselves. A named glove (``bonemittens`` and the like) still resolves to
    its unit and replaces the hands - the player's explicit choice wins.

    In particular it does **not** re-enable the bare-forearm adapter the way
    :func:`render_glove_adapter_lua` does. That adapter spawns ``hnd_forearms``,
    a vanilla bare forearm, to bridge a glove cuff and a short sleeve; on an
    outfit whose sleeve ends mid-forearm it draws a second, vanilla skin band at
    the wrist, above the glove and below the sleeve. That is D59's mistake and
    the reason this hook is the one the OfficeSuite packs ship (D60).

    ``item_id`` names the outfit; ``label`` is the pack in the file's first line.
    """
    key = f"las_{item_id}"
    return f"""-- {label} LAS: no default glove over the outfit's own body, hands or no hands.
-- D58/D60. "Default" gloves must resolve to no glove unit, so what this pack
-- models on the arms is what shows - and this pack models no hands. A glove the
-- player picks by hand still spawns and wins. No bare-forearm adapter: it would
-- put a vanilla skin band at the wrist. See render_own_hands_lua for the rest.
Hooks:PostHook(BlackMarketTweakData, "init", "{item_id}_OwnHands", function(self)
\tlocal ps = self.player_styles and self.player_styles["{key}"]
\tif not ps then return end

\t-- No glove unit for "Default". BeardLib reads this value, and `false`
\t-- means "spawn nothing"; the outfit's own body stays as built.
\tps.default_glove_id = false

\t-- The body still replaces the stock hands. This is what makes the outfit's
\t-- own body the only thing on the arms: with the stock hands visible there
\t-- would be doubles, and on a cut-handed outfit a strip of vanilla skin.
\tif ps.third_body_replacement then ps.third_body_replacement.hands = true end
\tif ps.body_replacement then ps.body_replacement.hands = true end
end)
"""


def render_unit_xml(unit_base: str) -> str:
    return (
        '<?xml version="1.0"?>\n'
        '<unit type="dah" slot="1">\n'
        f'\t<object file="{unit_base}" />\n'
        "\n"
        "\t<extensions>\n"
        '\t\t<extension name="unit_data" class="ScriptUnitData" />\n'
        '\t\t<extension name="contour" class="ContourExt"/>\n'
        "\t</extensions>\n"
        "</unit>"
    )


def model_drawables(model: bytes) -> list[str]:
    """Names of the drawables a built `.model` actually contains, in order."""
    from diesel_model import (CUSTOM_HASHLIST, MODEL_DATA, decode_custom_hashlist,
                              decode_model_data, hash64)
    from diesel_model import ModelFile

    mf = ModelFile.read(model)
    names = {hash64(n): n for n in
             decode_custom_hashlist(mf.by_type(CUSTOM_HASHLIST)[0].payload)["names"]}
    out = []
    for shape in mf.by_type(MODEL_DATA):
        md = decode_model_data(shape.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue                       # colliders and empty sockets
        out.append(names.get(md["name_hash"], ""))
    return [n for n in out if n]


def render_object_xml(unit_base: str, drawables: list[str], also_visible: tuple = ()) -> str:
    """An object file that lists exactly what the model has.

    Listing an object the model does not contain is at best noise in the log
    and at worst a load failure, so the list is derived from the built model
    rather than hard-coded. `g_body` (or the first drawable) is the visible
    one; LODs stay off, and `g_head` is only declared when a head exists —
    LAS supplies the heister's own head when the outfit hides the mask.
    `also_visible` names further drawables to switch on, for the whole-character
    packs that ship a head of their own.
    """
    lines = []
    primary = "g_body" if "g_body" in drawables else (drawables[0] if drawables else "")
    visible = {primary, *also_visible}
    for name in drawables:
        if name.startswith("s_") or name.startswith("c_"):
            continue                       # shadow meshes and colliders are engine-owned
        enabled = "true" if name in visible else "false"
        lines.append(f'\t\t\t<object name="{name}" enabled="{enabled}" />\n')
    return (
        '<?xml version="1.0"?>\n'
        "<dynamic_object>\n"
        f'\t<diesel materials="{unit_base}" orientation_object="root_point" />\n'
        "\n"
        "\t<graphics>\n"
        '\t\t<graphic_group name="character" enabled="true" culling_object="c_block">\n'
        f"{''.join(lines)}"
        "\t\t\n"
        "\t\t</graphic_group>\n"
        "\t</graphics>\n"
        "</dynamic_object>\n"
    )


# ---------------------------------------------------------------------------
# icon
# ---------------------------------------------------------------------------
def build_icon(png: bytes, size: int = 256, view: int = 3) -> bytes:
    """Menu icon: our own render of the outfit, cut out and framed.

    Deliberately not a game asset — the tile is the pack's own model and
    textures, so nothing shipped here belongs to anyone else. The four-view
    sheet is [front, side, back, three-quarter]; the default takes the
    three-quarter view because a frontal bind pose reads as a mannequin.

    The outfit is black, so it is composited on a soft gradient rather than on
    the sheet's flat near-black background; otherwise the tile is a black blob.
    """
    import io

    import numpy as np
    from PIL import Image, ImageFilter

    from dds_encode import rgba_to_bc3_dds

    sheet = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = sheet.size
    panel = np.asarray(sheet.crop((view * (w // 4), 0, (view + 1) * (w // 4), h)),
                       dtype=np.int16)

    # the sheet's background is one flat colour. Threshold on *difference* from
    # it, not on brightness: a black suit is only a few levels above the fill.
    bg = panel[2, 2].astype(np.int16)
    mask = np.abs(panel - bg).max(axis=2) > 8
    mask[:24] = False            # the sheet's view label is not part of the figure
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if not len(rows) or not len(cols):             # pragma: no cover - blank input
        rows, cols = np.array([0, panel.shape[0] - 1]), np.array([0, panel.shape[1] - 1])
    top, bottom = int(rows[0]), int(rows[-1])
    left, right = int(cols[0]), int(cols[-1])

    # background: a cool vertical gradient, light enough to separate a black suit
    yy = np.linspace(0.0, 1.0, size, dtype=np.float32)[:, None, None]
    top_rgb = np.array([44, 50, 62], np.float32)
    bottom_rgb = np.array([96, 104, 116], np.float32)
    canvas = np.broadcast_to(
        top_rgb * (1.0 - yy) + bottom_rgb * yy, (size, size, 3)).copy()

    # full figure with a small margin, cropped to the pixels that differ from
    # the sheet background (the arms are spread, so the box is wide)
    figure = Image.fromarray(panel.astype(np.uint8)).crop(
        (left, top, right + 1, bottom + 1))
    fw, fh = figure.size
    scale = (size * 0.82) / max(fw, fh)
    figure = figure.resize((max(int(fw * scale), 1), max(int(fh * scale), 1)),
                           Image.LANCZOS)

    # the crop is rectangular but the figure is not: keep the sheet's background
    # out of the tile with the same difference test
    fig = np.asarray(figure, dtype=np.int16)
    keep = np.abs(fig - bg).max(axis=2) > 8
    keep[:6] = False
    keep = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).filter(
        ImageFilter.MaxFilter(3)), dtype=np.float32) / 255.0
    x0 = max(size // 2 - figure.size[0] // 2, 0)
    y0 = max((size - figure.size[1]) // 2, 0)
    region = canvas[y0:y0 + figure.size[1], x0:x0 + figure.size[0]]
    mixer = keep[..., None]
    region[:] = fig * mixer + region * (1.0 - mixer)

    rgba = np.dstack([np.clip(canvas, 0, 255),
                      np.full((size, size), 255, np.float32)]).astype(np.uint8)
    return rgba_to_bc3_dds(rgba)


# ---------------------------------------------------------------------------
# zip
# ---------------------------------------------------------------------------
def zip_bytes(entries, stamp: tuple = (2020, 1, 1, 0, 0, 0)) -> bytes:
    """A zip that is the same bytes whenever its content is.

    `entries` are (name, bytes) pairs in the order they go in. Every entry
    carries the same time and mode 0644 and is deflated, so nothing of the
    machine or of the day reaches the archive.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            entry = zipfile.ZipInfo(name, date_time=stamp)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            zf.writestr(entry, data)
    return buffer.getvalue()


def zip_pack(pack: Path) -> Path:
    """The pack folder as an installable zip next to it (top level = the folder's name)."""
    out = pack.with_suffix(".zip")
    out.write_bytes(zip_bytes((path.relative_to(pack.parent).as_posix(), path.read_bytes())
                              for path in sorted(pack.rglob("*")) if path.is_file()))
    return out
