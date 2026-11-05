"""Assemble a Skyrim-derived outfit as a PAYDAY 2 LAS pack folder.

Same registration contract as `las_pack.py` (the 2B reference, studied as a
spec), with fresh IDs so both packs can be installed side by side:

    LegendaryArmours.skyrim_outfit
      units/skyrim_outfit/skins/skyrim_outfit/{skyrim_outfit,fps_skyrim_outfit}

What this module owns is the *layout*: manifest, hook, locales, unit/object
XMLs, material configs, textures, icon and `BUILD_INFO.json` with a hash per
file. Model authoring lives in `build_skyrim_outfit.py`.

The first-person unit is optional: `fps_available` in `BUILD_INFO.json` records
whether it was built, because an LAS entry whose `fps_unit` points at a missing
file is worse than one without it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ITEM_ID = "skyrim_outfit"
CATEGORY = "skyrim_outfit"
PACK_DIR_NAME = "SkyrimOutfit_LAS"
UNIT_BASE = f"units/{ITEM_ID}/skins/{ITEM_ID}"
GUI_BASE = f"guis/dlcs/{ITEM_ID}/armor_skins"
# the unit path ends in the file stem, exactly like units/2b/skins/2b/2b:
# LAS looks this up as a unit, so a directory here loads nothing at all
TPP_UNIT = f"{UNIT_BASE}/{ITEM_ID}"
FPS_UNIT = f"{UNIT_BASE}/fps_{ITEM_ID}"
HOOK_SOURCE = "lib/tweak_data/armorskinstweakdata"

# LAS maps each flag onto the character parts it replaces (see the mod's
# hooks/outfits/loader.lua): replace_all sets head=true as well, replace_body
# only body/hands/arms. This outfit ships no head — the source archives carry
# none and the template's is someone else's character — so it must not claim
# replace_all, or LAS drops the heister's head and the unit is decapitated.
FLAG_KEYS = (
    "hide_mask",
    "hide_armor",
    "replace_body",
    "fps_hide_armor",
    "fps_replace_body",
)

DISPLAY_NAME = "Skyrim Outfit"


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def render_hook_lua(with_fps: bool = False, hands: str = "adapter") -> str:
    flags = ",\n".join(f"\t{k} = true" for k in FLAG_KEYS)
    lines = [
        "LegendaryArmours = LegendaryArmours or {}",
        "la = LegendaryArmours",
        "",
        f"la.{ITEM_ID} = {{",
        f'\tcategory = "{CATEGORY}",',
        "",
        f'\tunit = "{TPP_UNIT}",',
    ]
    if with_fps:
        lines.append(f'\tfps_unit = "{FPS_UNIT}",')
    lines += ["", flags]
    if hands == "adapter":
        # Intent flag. LAS 4.1.9's loader drops it (it reads a fresh `output`
        # table, not this data), so the companion hook
        # `<item>_glove_adapter.lua` is what actually re-enables the adapter.
        lines[-1] += ","
        lines += ["", "\tglove_adapter = true"]
    lines += ["}", ""]
    return "\n".join(lines)


def render_glove_adapter_lua() -> str:
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
    restores the vanilla mechanism: a real ``default_glove_id``, the adapter
    re-enabled, the exclude entry removed, and ``body_replacement.hands`` set to
    ``false`` so the heister's own stock hands remain visible as a guaranteed
    fallback (the glove spawn is not reliable in-game); any glove unit that does
    spawn sets ``var_hands_replace = 1`` and replaces the stock hands, so there
    are no double hands. Works in both TPP and FPS — BeardLib retargets the same
    glove/adapter spawn to the camera unit for the local peer.

    Traps it avoids:

    * the adapter is enabled with an empty *table*, never a boolean ``true``:
      BeardLib does ``table.merge(final_adapter_data, ...adapter_data)`` and its
      ``table.merge`` calls ``pairs(new_table)``, so a boolean would raise
      ``pairs(true)``. An empty table keeps the default ``hnd_forearms`` adapter.
    * ``default_glove_id`` cannot be set through the outfit's data.xml — LAS's
      fresh-table read drops it — so a PostHook override is the only route.
    """
    key = f"las_{ITEM_ID}"
    return f"""-- SkyrimOutfit LAS: vanilla-suit glove behaviour for {key}.
-- Restores a real default glove (LAS forces default_glove_id = false, which
-- leaves "Default" gloves with no hands) and re-enables the glove adapter.
-- See las_outfit_pack.render_glove_adapter_lua for the full rationale.
Hooks:PostHook(BlackMarketTweakData, "init", "SkyrimOutfit_GloveAdapter", function(self)
\tlocal ps = self.player_styles and self.player_styles["{key}"]
\tif not ps then return end

\t-- The base game keeps a suit's hands visible by giving the style a REAL
\t-- default glove (suit_default_gloves -> default_glove_id), so "Default"
\t-- gloves resolve to an actual hand mesh. LAS sets default_glove_id = false,
\t-- so "Default" gloves spawn nothing and the suit has no hands. Restore a
\t-- real default glove, exactly like the vanilla/DLC suits.
\tps.default_glove_id = "heist_default"

\t-- Enable the adapter with a table (NOT a boolean: BeardLib's table.merge
\t-- would call pairs(true)). An empty table keeps the default hnd_forearms.
\tps.glove_adapter = {{}}

\t-- Drop the exclude-list entry LAS added for replace_body.
\tlocal list = self.glove_adapter and self.glove_adapter.player_style_exclude_list
\tif list then
\t\tfor i = #list, 1, -1 do
\t\t\tif list[i] == "{key}" then table.remove(list, i) end
\t\tend
\tend

\t-- Do NOT hide the stock hands. LAS forces default_glove_id = false and the
\t-- glove spawn above is not reliable in-game; the old approach hid the stock
\t-- hands (body_replacement.hands = true) and relied solely on the glove unit,
\t-- so when it failed to appear the suit had NO hands. Keeping hands = false
\t-- lets the heister's own stock hands show through the sleeves as a guaranteed
\t-- fallback (nothing is authored). When a glove unit DOES spawn (default or
\t-- equipped) it sets var_hands_replace = 1 and replaces the stock hands, so
\t-- there are no double hands.
\tif ps.body_replacement then ps.body_replacement.hands = false end
\tif ps.third_body_replacement then ps.third_body_replacement.hands = false end
end)
"""


def render_localization() -> str:
    return json.dumps(
        {
            f"bm_menu_{ITEM_ID}_armor_skins": DISPLAY_NAME,
            f"bm_askn_{ITEM_ID}": DISPLAY_NAME,
            f"bm_askn_{ITEM_ID}_desc": (
                "a Skyrim SE 3BA outfit as a Legendary Armour Skins outfit."
            ),
        },
        indent=2,
    )


def render_main_xml(texture_stems: list[str], with_fps: bool = False,
                    hands: str = "adapter") -> str:
    # <df_nm> names the pair by its stem; the engine appends _df/_nm itself.
    # Passing the full "outfit_body_df" makes it look for outfit_body_df_df.texture,
    # which silently leaves every material untextured (flat black in game).
    pairs = "\n".join(
        f'\t\t\t\t<df_nm path="{UNIT_BASE}/{stem[:-3]}"/>'
        for stem in texture_stems
        if stem.endswith("_df")
    )
    units = [TPP_UNIT] + ([FPS_UNIT] if with_fps else [])
    unit_lines = "\n".join(f'\t\t\t\t<unit_mat path="{u}"/>' for u in units)
    hooks = [f'\t\t<hook file="{ITEM_ID}_las.lua" source_file="{HOOK_SOURCE}"/>']
    if hands == "adapter":
        # The compat hook runs on blackmarkettweakdata (after LAS's loader),
        # not armorskinstweakdata where the outfit is declared.
        hooks.append(f'\t\t<hook file="{ITEM_ID}_glove_adapter.lua" '
                     f'source_file="lib/tweak_data/blackmarkettweakdata"/>')
    hook_lines = "\n".join(hooks)
    return (
        f'<table name="{DISPLAY_NAME}" image="{GUI_BASE}/{ITEM_ID}">\n'
        "\n"
        '\t<Localization directory="localization" default="english.txt"/>\n'
        "\n"
        '\t<Hooks directory="hooks">\n'
        f"{hook_lines}\n"
        "\t</Hooks>\n"
        "\n"
        '\t<AddFiles directory="assets">\n'
        "\n"
        f'\t\t\t\t<texture path="{GUI_BASE}/{ITEM_ID}"/>\n'
        f"{pairs}\n"
        "\n"
        f"{unit_lines}\n"
        "\n"
        "\t\t\t\t</AddFiles>\n"
        "</table>\n"
    )


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


def render_object_xml(unit_base: str, drawables: list[str]) -> str:
    """An object file that lists exactly what the model has.

    Listing an object the model does not contain is at best noise in the log
    and at worst a load failure, so the list is derived from the built model
    rather than hard-coded. `g_body` (or the first drawable) is the visible
    one; LODs stay off, and `g_head` is only declared when a head exists —
    LAS supplies the heister's own head when the outfit hides the mask.
    """
    lines = []
    primary = "g_body" if "g_body" in drawables else (drawables[0] if drawables else "")
    for name in drawables:
        if name.startswith("s_") or name.startswith("c_"):
            continue                       # shadow meshes and colliders are engine-owned
        enabled = "true" if name == primary else "false"
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
# assemble
# ---------------------------------------------------------------------------
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_pack(out_root: Path, model: bytes, textures: dict[str, bytes],
               icon: bytes, material_config: str, fps_config: str | None,
               fps_model: bytes | None = None, extra: dict | None = None,
               drawables: list[str] | None = None,
               fps_drawables: list[str] | None = None,
               hands: str = "adapter") -> Path:
    """Write the installable folder (no zip; see `zip_pack`).

    `drawables` / `fps_drawables` are read back out of the model files when not
    given; passing them explicitly keeps this callable with synthetic models in
    tests.

    `hands` selects the hand route: ``"adapter"`` ships no hands and re-enables
    the vanilla glove adapter via a compat hook (gloves stay changeable);
    ``"graft"`` is the legacy baked-in-hands route.
    """
    pack = Path(out_root) / PACK_DIR_NAME
    if pack.exists():
        # a rebuild must not ship files from the previous one: dropping a
        # garment (--jacket bustier) leaves its textures behind otherwise
        shutil.rmtree(pack)
    unit_dir = pack / "assets" / UNIT_BASE
    gui_dir = pack / "assets" / GUI_BASE
    unit_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    (pack / "hooks").mkdir(exist_ok=True)
    (pack / "localization").mkdir(exist_ok=True)

    with_fps = fps_model is not None and fps_config is not None

    (unit_dir / f"{ITEM_ID}.model").write_bytes(model)
    (unit_dir / f"{ITEM_ID}.unit").write_text(render_unit_xml(TPP_UNIT))
    if drawables is None:
        drawables = model_drawables(model)
    (unit_dir / f"{ITEM_ID}.object").write_text(
        render_object_xml(TPP_UNIT, drawables))
    (unit_dir / f"{ITEM_ID}.material_config").write_text(material_config)
    if with_fps:
        (unit_dir / f"fps_{ITEM_ID}.model").write_bytes(fps_model)
        (unit_dir / f"fps_{ITEM_ID}.unit").write_text(render_unit_xml(FPS_UNIT))
        if fps_drawables is None:
            fps_drawables = model_drawables(fps_model)
        (unit_dir / f"fps_{ITEM_ID}.object").write_text(
            render_object_xml(FPS_UNIT, fps_drawables))
        (unit_dir / f"fps_{ITEM_ID}.material_config").write_text(fps_config)

    for stem, data in sorted(textures.items()):
        (unit_dir / f"{stem}.texture").write_bytes(data)
    (gui_dir / f"{ITEM_ID}.texture").write_bytes(icon)

    (pack / "main.xml").write_text(
        render_main_xml(sorted(textures), with_fps, hands))
    (pack / "hooks" / f"{ITEM_ID}_las.lua").write_text(
        render_hook_lua(with_fps, hands))
    if hands == "adapter":
        (pack / "hooks" / f"{ITEM_ID}_glove_adapter.lua").write_text(
            render_glove_adapter_lua())
    (pack / "localization" / "english.txt").write_text(render_localization())

    payload = {}
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "BUILD_INFO.json":
            # the manifest cannot carry its own hash
            payload[path.relative_to(pack).as_posix()] = _sha(path.read_bytes())
    info = {
        "pack": PACK_DIR_NAME,
        "item_id": ITEM_ID,
        "display_name": DISPLAY_NAME,
        "registration": {
            "hook_source": HOOK_SOURCE,
            "table": f"LegendaryArmours.{ITEM_ID}",
            "flags": list(FLAG_KEYS) + (["glove_adapter"] if hands == "adapter" else []),
            "unit": TPP_UNIT,
            "fps_unit": FPS_UNIT if with_fps else None,
        },
        "hands": hands,
        "glove_adapter": hands == "adapter",
        # the compat hook restores a real default glove so "Default" gloves
        # spawn hands (LAS forces default_glove_id = false -> no hands)
        "default_glove_id": "heist_default" if hands == "adapter" else None,
        "models_present": True,
        "fps_available": with_fps,
        "runtime_verified": False,
        "payload_sha256": payload,
    }
    info.update(extra or {})
    (pack / "BUILD_INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return pack


def zip_pack(pack: Path) -> Path:
    """Reproducible zip: fixed timestamps, sorted entries, stored content."""
    out = pack.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(pack.rglob("*")):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(pack.parent).as_posix(),
                                        date_time=(2020, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                zf.writestr(entry, path.read_bytes())
    return out
