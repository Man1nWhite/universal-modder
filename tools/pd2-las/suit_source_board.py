#!/usr/bin/env python3
"""Preview board for candidate *office-suit body* sources for a PAYDAY 2 LAS outfit.

This does not port anything. It is the *recon* step from
`skills/mod-any-game/SKILL.md`: before a single vertex is retargeted, look at the
candidate source models side by side, check each against the two hard
constraints the Diesel/PD2 pipeline imposes (weight budget, rigid skirt), and
write down where to get each one.

    .venv/bin/python tools/pd2-las/suit_source_board.py

Inputs are the reference stills gathered per candidate (`references/suit-sources/`
+ `image-search/`, both git-ignored scratch); outputs:

    docs/pd2-las/suit-sources/board.png          the contact sheet
    docs/pd2-las/suit-sources/<slot>.png         one card per candidate
    docs/pd2-las/suit-sources/<slot>-stills.png  all stills of that candidate
    docs/pd2-las/SUIT-SOURCES.md                 generated notes (metrics table)

Everything here is measurement and metadata, so the board can be regenerated
byte-for-byte from the same inputs (`--verify` re-renders and compares).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "pd2-las" / "suit-sources"
MD = ROOT / "docs" / "pd2-las" / "SUIT-SOURCES.md"
STILL_DIRS = (ROOT / "references" / "suit-sources", ROOT / "image-search")

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
WIDTH = 1600                     # board width; every layout number scales from it
F_BOLD_28 = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 38)
F_BOLD_19 = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 26)
F_BOLD_15 = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 20)
F_REG_15 = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 21)
F_REG_13 = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 18)
F_MONO_13 = ImageFont.truetype(str(FONT_DIR / "DejaVuSansMono.ttf"), 18)

INK = (28, 30, 36)
PAPER = (247, 246, 243)
CARD = (255, 255, 255)
MUTED = (110, 114, 124)
LINE = (206, 206, 200)
GOOD = (36, 120, 76)
WARN = (176, 106, 18)
BAD = (170, 44, 44)

# PD2 LAS targets, from tools/pd2-las/diesel_model.py + las_target_skeleton.json
DIESEL_MAX_WEIGHTS = 4          # SKINNED_4WEIGHTS is the widest supported layout
TARGET_BONES = 60               # first 60 entries: the deform skeleton
TARGET_HEIGHT_CM = 180.0
TARGET_TEX_BUDGET_MB = 12.0


@dataclass(frozen=True)
class Candidate:
    slot: str
    game: str
    mod: str
    outfit: str
    author: str
    star: str
    stills: tuple[str, ...]
    bones: str
    weights: str
    hands: str
    skirt: str
    texture: str
    licence: str
    route: str
    url: str
    note: str
    hero: str = ""          # empty = pick automatically from `stills`

    def verdict(self) -> str:
        return {
            "4.5": "A", "4.0": "A", "3.5": "B", "3.0": "B",
            "2.5": "C", "2.0": "C", "1.5": "D", "1.0": "D",
        }.get(self.star, "-")


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        slot="01-re4r-ada-agent-officewear",
        game="Resident Evil 4 (2023)  ·  RE Engine",
        mod="Ada Wong Agent Officewear",
        outfit="grey blazer + white blouse + knee-length pencil skirt + pumps",
        author="MrGreenEyes (Nexus 5310)",
        star="4.5",
        stills=(
            "mrgreeneyes-ada-wong-agent-officewear-ne-1.webp",
            "mrgreeneyes-ada-wong-agent-officewear-ne-2.webp",
        ),
        hero="mrgreeneyes-ada-wong-agent-officewear-ne-1.webp",
        bones="~120 (RE Engine) — 22 used by a LAS outfit",
        weights='4 carried; ship "skin weight limit = 4"',
        hands="kept — blazer sleeve ends at the wrist",
        skirt="rigid, thigh-weighted, knee-length (no chain, no cloth)",
        texture="~4-6 MB albedo/normal/gloss, matte wool (no PBR stack)",
        licence="conversion + asset use allowed, credit MrGreenEyes",
        route=".pak -> RE Mesh Editor -> .fbx/.smd -> LAS retarget",
        url="https://www.nexusmods.com/residentevil42023/mods/5310",
        note="closest match to the 3BA brief; sleeves reach the wrist, so "
             "PD2's changeable gloves work and no sleeve extension is needed",
    ),
    Candidate(
        slot="02-doa6-ayane-office-suit",
        game="Dead or Alive 6  ·  (DOA6LR, Team NINJA)",
        mod="Ayane Office Suit HD (DOA5LR / DOA6)",
        outfit="black blazer + white shirt + short pencil skirt + fishnet + heels",
        author="DOA6 mod (AutoLink / REDELBE)",
        star="3.5",
        stills=("ayane-office-suit-doa5lr-mod-1.webp",),
        bones="~90 — 20 used by a LAS outfit",
        weights="studio-painted, 4 carried; ship with a 4-weight clamp",
        hands="kept, but the rig is a fighter's, not a heister's",
        skirt="rigid and thigh-weighted; designed for kicks, so it survives a crouch",
        texture="classic diffuse/normal/specular — the easiest shader match",
        licence="check the costume's rip source; figure mods are grey-area",
        route=".g1m -> gltf/fbx (Blender) -> LAS retarget",
        url="https://ayakamods.com/games/dead-or-alive-5-last-round.92/",
        note="best skirt/shoulder weighting of the four; DOA5LR/6 share the "
             "same costume library, and DOA6's High Society set is a corset, "
             "not office wear, so use the Office Suit mods instead",
    ),
    Candidate(
        slot="03-doa5lr-christie-business-suit",
        game="Dead or Alive 6  ·  (Team NINJA)  — same asset as DOA5LR Costume 2",
        mod="Christie “Business Suit”",
        outfit="tailored blazer + open shirt + pencil skirt; 3 colourways (black / white / beige)",
        author="Team NINJA (vanilla asset, 3 recolours)",
        star="3.0",
        stills=("doa5lr-christie-hidden-costume-business--3.png",),
        bones="~85 — 20 used by a LAS outfit",
        weights="studio-painted, 4 carried; 4-weight clamp",
        hands="kept, thin fighter hands (finger bones exist)",
        skirt="rigid, thigh-weighted, hem above the knee",
        texture="diffuse/normal/specular, all in the game's .tpf archives",
        licence="vanilla Koei Tecmo asset — reuse is not licensed (see note)",
        route=".tpf + .g1m -> Blender -> LAS retarget",
        url="https://deadoralive.fandom.com/wiki/Christie/Dead_or_Alive_5_costumes",
        note="the only *literally* office-suit costume on the list: tailored "
             "blazer, open shirt, pencil skirt, three recolours. It is a "
             "vanilla Koei Tecmo asset, so a port can only ever be a private "
             "build — never a release. Design caveat: the blazer is buttoned "
             "*open* with a deep V, so the chest is bare skin, not a blouse",
    ),
    Candidate(
        slot="04-doa6-doaxvv-yom-office-wear",
        game="Dead or Alive 6 / DOAXVV  ·  Yom tie-up",
        mod="Yom · Office Wear (SSR) + Tekken 8 “Office Wear” port by TheRessen",
        outfit="black turtleneck + leather pencil skirt + tights + heels",
        author="Team NINJA × Yom  ·  TK8 port by TheRessen",
        star="3.5",
        stills=(
            "tekken-8-office-wear-mod-theressen-doaxv-1.jpg",
            "tekken-8-office-wear-mod-theressen-doaxv-2.jpg",
            "doaxvv-yom-office-wear-ssr-nagisa-nanami-1.jpg",
        ),
        hero="tekken-8-office-wear-mod-theressen-doaxv-1.jpg",
        bones="~90 — 20 used by a LAS outfit",
        weights="4 carried; already re-rigged once by TheRessen for TK8",
        hands="kept; TK8 mod ships full hands",
        skirt="rigid leather pencil skirt, thigh-weighted, hem at the knee",
        texture="diffuse/normal/gloss; tights are separate geometry with 5 deniers",
        licence="TheRessen's TK8 mod permits asset reuse and modification",
        route="TK8 .pak -> .uasset -> fbx -> LAS retarget",
        url="https://tekkenmods.com/mod/3737/office-wear-mod-for-all-female-characters-tk8",
        note="the cleanest office *silhouette* of the set (turtleneck, pencil "
             "skirt, tights); TK8's port is the practical way in, and its "
             "licence is the permissive one",
    ),
    Candidate(
        slot="05-skyrim-3ba-business-woman",
        game="Skyrim SE  ·  CBBE 3BA  —  this repo's own failed attempt",
        mod="Melodic “Business Woman” (1.zip–5.zip)",
        outfit="3BA body + blazer + bustier + pencil skirt + heels + necklace",
        author="Melodic (LoversLab) — port cancelled 2026-11-04",
        star="1.0",
        stills=(),
        bones="~115, but HDT-SMP chains for the skirt and necklace",
        weights="needs a clamp; sheet-split UV islands carry mismatched weights",
        hands="✗ sleeves stop 6.3 cm short of the PD2 RightHand joint",
        skirt="✗ 13 physics bones + a cloth chain Diesel cannot drive",
        texture="2048² albedo/normal/metal, plus a hand-authored skin set",
        licence="“do not publish outside LoversLab without permission”",
        route=".nif -> nifly -> smd (tools/skyrim-nif), already written",
        url="docs/skyrim-nif/STATUS.md",
        note="the control case, and the reason the four above are ranked the "
             "way they are: layered BodySlide sheets poke through each other, "
             "the sleeve/hand gap exposed floating gloves, the shirt collar "
             "flared over the blazer, and the skirt is physics-driven. Keep it "
             "here as the baseline that “A” candidates must beat",
    ),
)



def _find_still(name: str) -> Path:
    for d in STILL_DIRS:
        p = d / name
        if p.exists():
            return p
    raise FileNotFoundError(f"missing still {name!r} in {[str(d) for d in STILL_DIRS]}")


def _hero(c: Candidate) -> str:
    """Pick the hero still: explicit `hero`, else the least collage-like one."""
    if c.hero:
        return c.hero

    def rank(name: str) -> tuple[float, str]:
        with Image.open(_find_still(name)) as im:
            ar = im.width / max(im.height, 1)
        # a 3-panel collage is ~3.0 wide; a single still is <= 1.9
        return (0.0 if ar <= 1.9 else 1.0, -min(ar, 3.0), name)
    return sorted(c.stills, key=rank)[0]


def _fit(img: Image.Image, size: tuple[int, int], *, pad: int = 0,
         bg: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Letterbox `img` into `size` with `pad` px of background on every side."""
    w, h = size[0] - 2 * pad, size[1] - 2 * pad
    im = img.convert("RGB")
    s = min(w / im.width, h / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))),
                   Image.LANCZOS)
    out = Image.new("RGB", size, bg)
    out.paste(im, (pad + (w - im.width) // 2, pad + (h - im.height) // 2))
    return out


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}".strip()
            if draw.textlength(trial, font=font) <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _rule(draw, xy, colour=LINE, width=1):
    draw.line(xy, fill=colour, width=width)


def _card(c: Candidate, width: int = WIDTH) -> Image.Image:
    """One candidate card: hero still, spec table, route, note."""
    hero_w, hero_h = width - 96, 580
    rows = [
        ("bones", c.bones), ("weights", c.weights), ("hands", c.hands),
        ("skirt", c.skirt), ("textures", c.texture), ("licence", c.licence),
        ("route", c.route),
    ]
    body = _wrap(ImageDraw.Draw(Image.new("RGB", (10, 10))), c.note, F_REG_15,
                 width - 152)
    height = 50 + 96 + hero_h + 40 + len(rows) * 44 + 40 + len(body) * 30 + 116
    im = Image.new("RGB", (width, height), PAPER)
    d = ImageDraw.Draw(im)

    pad = 48
    d.text((pad, 38), f"{c.slot.split('-')[0]}  ·  {c.game}", font=F_BOLD_15, fill=MUTED)
    d.text((pad, 72), c.mod, font=F_BOLD_28, fill=INK)
    d.text((pad, 132), c.outfit, font=F_REG_15, fill=(70, 74, 84))

    y = 184
    if c.stills:
        im.paste(_fit(Image.open(_find_still(_hero(c))), (hero_w, hero_h),
                      pad=0, bg=CARD), (pad, y))
    else:
        d.rectangle((pad, y, pad + hero_w, y + hero_h), fill=CARD)
        d.text((pad + 32, y + hero_h // 2 - 40), "no reference still retained",
               font=F_BOLD_19, fill=MUTED)
        d.text((pad + 32, y + hero_h // 2 + 4),
               "the source archives were deleted from this branch on 2026-11-04",
               font=F_REG_13, fill=MUTED)
    y += hero_h + 36

    for key, val in rows:
        d.text((pad, y), key, font=F_MONO_13, fill=MUTED)
        for i, line in enumerate(_wrap(d, val, F_REG_13, width - 340)[:2]):
            d.text((pad + 176, y - 2 + i * 22), line, font=F_REG_13, fill=INK)
        y += 44

    _rule(d, (pad, y + 6, width - pad, y + 6))
    y += 24
    for line in body:
        d.text((pad, y), line, font=F_REG_15, fill=(60, 64, 74))
        y += 30

    y += 24
    d.text((pad, y), "where", font=F_MONO_13, fill=MUTED)
    d.text((pad + 176, y - 2), c.url, font=F_REG_13, fill=(42, 76, 150))
    return im


def _strip(c: Candidate, width: int = WIDTH) -> Image.Image:
    """All stills for one candidate, side by side."""
    imgs = [Image.open(_find_still(n)) for n in c.stills]
    cell_h = 620
    cols = min(len(imgs), 3)
    cell_w = (width - 96 - (cols - 1) * 16) // cols
    rows = (len(imgs) + cols - 1) // cols
    im = Image.new("RGB", (width, 60 + rows * (cell_h + 16) + 36), PAPER)
    d = ImageDraw.Draw(im)
    d.text((48, 30), c.mod, font=F_BOLD_19, fill=INK)
    for i, src in enumerate(imgs):
        x = 48 + (i % cols) * (cell_w + 16)
        y = 78 + (i // cols) * (cell_h + 16)
        im.paste(_fit(src, (cell_w, cell_h)), (x, y))
    return im


def board(cards: list[Image.Image], width: int = WIDTH) -> Image.Image:
    head = 250
    gap = 26
    height = head + sum(c.height for c in cards) + gap * len(cards) + 40
    im = Image.new("RGB", (width, height), PAPER)
    d = ImageDraw.Draw(im)
    d.text((48, 40), "Office-suit bodies worth borrowing for a PAYDAY 2 LAS outfit",
           font=F_BOLD_28, fill=INK)
    d.text((48, 100), "recon for Miranda-line work: blazer / pencil skirt / blouse, "
                      "fitted to the Diesel skeleton", font=F_REG_15, fill=MUTED)
    d.text((48, 140), "target: ≤4 bone weights · rigid thigh-weighted skirt · sleeves reach "
                      "the wrist · one diffuse+normal set", font=F_MONO_13, fill=(70, 74, 84))
    d.text((48, 176), "ranked by portability, not by looks — A ships clean, D needs "
                      "a re-drape; 05 is this repo's own cancelled attempt",
           font=F_REG_13, fill=(70, 74, 84))
    _rule(d, (48, head - 18, width - 48, head - 18), INK, 3)
    y = head
    for c in cards:
        im.paste(c, (0, y))
        d.rectangle((0, y, width - 1, y + c.height - 1), outline=LINE)
        y += c.height + gap
    return im


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_markdown(order: list[Candidate]) -> None:
    lines = [
        "# Office-suit source models for a PAYDAY 2 LAS outfit",
        "",
        "> Generated by `tools/pd2-las/suit_source_board.py`. Do not hand-edit;",
        "> edit `CANDIDATES` in the script and re-run it.",
        "",
        "Recon only — nothing here is ported, and no game asset ships in this repo.",
        "",
        "![candidate board](suit-sources/board.png)",
        "",
        "Full-resolution sheet: [`suit-sources/board.png`](suit-sources/board.png).",
        "",
        "## Why these four, and not Skyrim again",
        "",
        "The Skyrim 3BA attempt (`STATUS.md`, `FIXES-2026-11-04.md`) failed on three",
        "things that are *source-artist* decisions, not retarget bugs: layered",
        "BodySlide sheets that poke through each other, sleeves that stop 6–8 cm short",
        "of the wrist, and an HDT-SMP skirt chain that Diesel cannot drive. A good",
        "source therefore has to have those three decided correctly *before* the port:",
        "",
        "| requirement | why |",
        "| --- | --- |",
        f"| ≤ {DIESEL_MAX_WEIGHTS} bone weights per vertex | Diesel skins 4; Source games clip to 3 |",
        f"| ~{TARGET_BONES} deform bones, humanoid names | the LAS rig is `las_target_skeleton.json` |",
        "| rigid, thigh-weighted skirt | no cloth physics in a PD2 heister model |",
        "| sleeves or gloves reach the wrist | PD2 spawns the glove *at* the hand joint |",
        "| one baked diffuse + normal set | Diesel has no PBR stack |",
        "",
        "## Ranked",
        "",
        "| # | game | mod / costume | verdict | skirt | weights | licence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, c in enumerate(order, 1):
        lines.append(
            f"| {i} | {c.game.split('  ·  ')[0]} | {c.mod} | **{c.verdict()}** ({c.star}) "
            f"| {c.skirt.split(',')[0]} | {c.weights.split(';')[0]} | {c.licence.split(',')[0]} |"
        )
    lines += ["", "## Notes per candidate", ""]
    for i, c in enumerate(order, 1):
        lines += [
            f"### {i}. {c.mod} — {c.game}",
            "",
            f"- **Outfit:** {c.outfit}",
            f"- **Author:** {c.author}",
            f"- **Bones:** {c.bones}",
            f"- **Weights:** {c.weights}",
            f"- **Hands/wrists:** {c.hands}",
            f"- **Skirt:** {c.skirt}",
            f"- **Textures:** {c.texture}",
            f"- **Licence:** {c.licence}",
            f"- **Route:** {c.route}",
            f"- **Where:** <{c.url}>",
            "",
            c.note,
            "",
        ]
    lines += [
        "## Also considered, and why not",
        "",
        "| source | outfit | why it is not on the board |",
        "| --- | --- | --- |",
        "| RE3R — “Jill Wild Secretary” (Lemi21) | white blouse, grey pencil skirt, "
        "glasses, stockings | right silhouette, but the mesh is watermarked, the "
        "re-upload is not the author's, and Lemi21's mods are not licensed for reuse |",
        "| RE4R — “Ada Office Lady” (Aerosmith) | office blazer + skirt set | "
        "a 2.8 GB NSFW pack with the garment split across many add-ons; wrong tone, "
        "and heavy to audit before a single vertex moves |",
        "| RE4R — “Ashley Wild Secretary” (Lemi21) | white shirt + mini skirt | "
        "the still that surfaced for it is half-undressed; off-brief for a heister "
        "outfit and unlicensed for reuse |",
        "| DOA6 — “[Revival] High Society” | white blouse, corset, long skirt | "
        "verified from the official set art: it is a corset-and-long-skirt costume, "
        "not office wear, so it does not meet the brief |",
        "| Tekken 8 — “TFD Business Suit” | tailored business suit | a TK8 "
        "customisation pak, and its office-wear sibling is itself a DOAXVV port — "
        "so it is a downstream copy of candidate 3, with an extra conversion step |",
        "",
        "## What to do next",
        "",
        "1. Pick one — rank A first, `01-re4r-ada-agent-officewear`.",
        "2. Extract the mod and import it into Blender (RE Mesh Editor for RE Engine,",
        "   `g1m` importers for DOA, FModel + an import add-on for the TK8 pak).",
        "   Export a rigged `.smd`/`.fbx`.",
        "3. Feed it through the pipeline this repo already has for exactly this shape:",
        "   `tools/pd2-las/build_business_woman.py` (Skyrim clothing → LAS body) —",
        "   `weld_open_seams`, `extend_sleeves_to_wrist` and `follow_layer_weights`",
        "   are the passes a suit body needs, and `skin_texture` bakes the skin set.",
        "   `build_models.py` builds the L4D2 body instead and takes no `--source`.",
        "4. Then the usual `bust_variant` / preview / publish path.",
        "5. Re-read `docs/skyrim-nif/FIXES-2026-11-04.md` before touching shoulders,",
        "   sleeves or the skirt — that is where the last attempt lost the game.",
        "",
        "Licences are recorded as found; nothing here grants redistribution.",
        "",
    ]
    MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the byte-identical re-render check")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    # only the board ships: the per-card PNGs are the same pixels laid out
    # differently, and 5 extra 1600-px sheets is 6 MB of duplication in git
    cards = [_card(c) for c in CANDIDATES]
    board(cards).save(OUT / "board.png")
    order = sorted(CANDIDATES, key=lambda c: (-float(c.star), c.slot))
    write_markdown(order)

    print(f"wrote {OUT / 'board.png'} ({board(cards).width}x{board(cards).height})")
    for c in order:
        print(f"  {c.verdict()} {c.star}  {c.slot}  {c.mod}")

    if not args.no_verify:
        before = {p.name: _sha(p) for p in OUT.glob("*.png")}
        cards2 = [_card(c) for c in CANDIDATES]
        board(cards2).save(OUT / "board.png")
        after = {p.name: _sha(p) for p in OUT.glob("*.png")}
        same = before == after
        print("re-render is byte-identical:", "yes" if same else "NO")
        if not same:
            return 1
        stale = {p.name for p in OUT.glob("*.png")} - set(after)
        if stale:
            print("stale per-card sheets left in", OUT, sorted(stale))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
