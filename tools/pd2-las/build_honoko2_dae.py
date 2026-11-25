#!/usr/bin/env python3
"""Build the Honoka "Secret Report" `.dae` outfit as PD2 LAS packs: OfficeSuite.

Unlike the earlier TMC-only build (deleted 2026-11-15, D40), which merged the raw
`.TMC` meshes into 3 material slots and overlaid the unbuttoned `WGT_cap2` jacket
on top of the buttoned `WGT_headdress2` suit, this driver builds from the Collada
export `references/Honoka/Honoka_DOAXVV_Secret_Reportout.dae`:

* **Clean garment selection + per-submesh materials** — uses the complete
  buttoned suit + skirt (`WGT_headdress2_0..5`) together with all body, bra,
  high-heel, and gold-jewelry submeshes (`WGT_new_aya_body_1..8`), avoiding the
  overlapping `WGT_cap2` shell that z-fights on the torso and back.
* **6 proper material slots per pack** parsed from the `.dae` bindings and paired
  with their source normal maps (`references/Honoka/L_*.dds`, plus `Tex_07(L_7) 2.dds`
  and `Tex_07(L_7)3.dds` for `Honoko4` and `OfficeSuite`):
  - `<id>_body`: `L_3.dds` / `L_4.dds`
  - `<id>_suit`: `L_7.dds` (or variant `Tex_07`) / `L_8.dds`
  - `<id>_panties`: `L_14.dds` / `L_15.dds`
  - `<id>_bra`: `L_17.dds` / `L_18.dds`
  - `<id>_shoes`: `L_20.dds` / `L_21.dds`
  - `<id>_jewelry`: `L_23.dds` (or `Tex_23(L_23)2.dds` in OfficeSuite) / `L_24.dds`
* **Skinning transfer from `.TMC`** — the Noesis `.dae` export omits
  `<library_controllers>`, while every `.dae` vertex matches its corresponding
  vertex in `Honoka_DOAXVV_Secret_Report.TMC` to ~0.0001 cm. Exact 4-weight +
  palette-remapped influences are transferred from the TMC, then retargeted onto
  the 2B PD2 skeleton via `tmc_skeleton_map.json` + `build_models.retarget_maps`.
* **One third-person BODY_ONLY LAS pack (`LegendaryArmours.officesuite`)** — the
  alternate suit and jewelry diffuses plus waist/hip/cuff fit adjustments, and a
  deterministic `dist/Honoka/OfficeSuite.zip` + `.sha256`. `Honoko2`..`Honoko4`, the
  earlier base/slim/alternate-suit builds of this same source, are no longer tracked
  (D57); their bytes are in git history. `OfficeSuite` cuts the hands where the palms
  begin (`PackSpec.hands="palm_cut"`, D59/D60): the plane is perpendicular to the palm,
  through the rig's `Hand` joint, and the mesh is clipped *on* it rather than at the
  last wholly-proximal triangle, so the palm and fingers go, the sleeve cuff and the
  outfit's bracelet stay, and no wrist is left standing above the cut. The rim is
  capped. The pack registers `own_hands` - no default glove unit, no stock hands, and
  no bare-forearm adapter - so the outfit's body simply has no hands and a glove the
  player picks is what puts hands on the character (D60). It additionally ships the
  first-person arms unit (`fps_officesuite.model`) from the same slim/cleared arms,
  registered with `fps_unit`, DEPTH_SCALING materials, no head, and the same palm cut.
* **One whole-character pack (`LegendaryArmours.officesuite_head`, D56)** — that same
  body and palm cut with the Miranda Romance head, built by `--only officesuite_head`.

Earlier builds were inspected in game (`docs/renders/honoka/in-game/`).
The latest OfficeSuite jewelry is not verified in game; see `docs/pd2-las/HANDOFF.md`.

Usage:
  make -sC tools/pd2-las env
  .venv/bin/python tools/pd2-las/build_honoko2_dae.py
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import determinism  # noqa: E402
import extract_2b  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from pack_checksum import write_pack_checksum  # noqa: E402

DEFAULT_TEMPLATES = extract_2b.TEMPLATES
DEFAULT_OUT = REPO / "dist" / "Honoka"
DEFAULT_WORK = REPO / "build" / "honoko2"
DAE_PATH = REPO / "references" / "Honoka" / "Honoka_DOAXVV_Secret_Reportout.dae"
SOURCE_ZIP = REPO / "references" / "Outfit for Honoka-109-1-1-1628020933.zip"
TMC_NAME = "Honoka_DOAXVV_Secret_Report.TMC"
TEX_DIR = REPO / "references" / "Honoka"

@dataclass(frozen=True)
class PackSpec:
    """One LAS pack built from the same Collada outfit.

    ``item_id`` names everything inside the pack (unit path, material slots, hook file), and
    ``slim`` is the factor the finished mesh is scaled by around the rig's bones: 1.0 ships the
    source's own proportions, 0.95 is the slimmer sibling pack.
    """

    item_id: str
    pack_dir: str
    display_name: str
    description: str
    slim: float = 1.0
    clearance: bool = False
    # "own" keeps the source's palms and fingers on the PD2 hand and finger bones;
    # "palm_cut" clips them off exactly where the palm begins (D59/D60), so the
    # outfit's body has no hands and the player's gloves are the hands on screen
    hands: str = "own"
    tex_override: dict = field(default_factory=dict)  # garment kind -> diffuse DDS name
    # ships a first-person arms unit (the outfit's sleeves down to the wrist cut,
    # gloves spawning on top, DEPTH_SCALING materials); the TPP body is unchanged
    fps: bool = False
    # adds a head drawable to the body, re-skinned from another unit's `g_head`,
    # and registers as a WHOLE_CHARACTER pack (`replace_all`): the skin replaces
    # the body, head and mask instead of borrowing the heister's head
    head: bool = False

    @property
    def unit_base(self) -> str:
        return f"units/{self.item_id}/skins/{self.item_id}"

    @property
    def gui_base(self) -> str:
        return f"guis/dlcs/{self.item_id}/armor_skins"

    @property
    def tpp_unit(self) -> str:
        return f"{self.unit_base}/{self.item_id}"

    @property
    def fps_unit(self) -> str | None:
        return f"{self.unit_base}/fps_{self.item_id}" if self.fps else None

    @property
    def fps_stem(self) -> str | None:
        return f"fps_{self.item_id}" if self.fps else None

    def slot(self, kind: str) -> str:
        """Material slot (and texture stem) for one source garment kind."""
        return f"{self.item_id}_{kind}"

    @property
    def head_slots(self) -> tuple[str, ...]:
        """The head drawable's two material slots: skin, then lashes.

        The skin is a diffuse+normal pair like every garment slot; the lashes
        are one diffuse whose alpha is the cutout.
        """
        return tuple(f"{self.slot(name)}" for name in HEAD_SLOTS)

    @property
    def head_textures(self) -> tuple[str, ...]:
        """The head's maps registered on their own: the face pair, then the lashes."""
        skin, lashes = self.head_slots
        return (f"{skin}_df", f"{skin}_nm", lashes)

    def slots(self) -> list[str]:
        return [self.slot(kind) for kind in MAT_TEXTURE_SOURCES]

    def mat_sources(self) -> dict[str, tuple[str, str]]:
        """Material slot -> (diffuse, normal) source DDS, in the emission order."""
        return {self.slot(kind): (self.tex_override.get(kind, df), nm)
                for kind, (df, nm) in MAT_TEXTURE_SOURCES.items()}


#: garment kinds the shadow-caster drawable omits: both shells are fully enclosed by the suit
#: and the body, so they add no silhouette (D44)
SHADOW_DROPS = {"bra", "panties"}

#: How far past the palm line the arm is kept, along the palm axis, in cm (D62/D63).
#: D60 cut exactly on the crease and the game then showed a gap: the heister's glove cuff
#: starts below where the outline of a hand would be, so the arm ended in mid-air, capped,
#: with nothing between it and the glove (user screenshots, 2026-11-25). Keeping some of
#: the palm continues the arm down into the glove instead.
#:
#: The amount is set by the glove's own geometry (D63) and then by what the game showed (D65).
#: The vanilla `g_hands` glove that the game draws starts 0.42 cm past the crease and is 3.5 cm
#: in radius there, widening to 4.0 at 2 cm and 4.3 at 3 cm; this outfit's wrist is 3.46 cm and
#: its palm passes the glove at about 2 cm. D63 tucked the arm 1.5 cm into the glove - a
#: centimetre inside the rim - and the in-game screenshots of 2026-11-25 still showed a wedge of
#: skin coming through the darker glove's cuff at the wrist bend: the arm is still growing
#: (3.46 cm at the crease, 4.4 at 2 cm) where the glove's cuff is narrow, and the last
#: half-centimetre of it is the fattest part. Cutting a little more takes that back - 1.25 cm,
#: which after the 5% slim still reaches 0.6 cm, comfortably past the glove's 0.42 cm rim, so
#: the D60 gap does not return.
PALM_EXTEND_CM = 1.25

#: The outfit's one tracked pack: the slim, cleared geometry in the user's third colourway,
#: `references/Honoka/Tex_07(L_7)3.dds` (revised black jacket and light shirt), updated by
#: the user at `main` 526480e (D45/D46), hands cut where the palms begin (D59, clipped on the
#: plane since D60; they were the outfit's own from D55 until then).
#:
#: `Honoko2` (base proportions), `Honoko3` (5% slim) and `Honoko4` (slim, alternate suit)
#: were built from this same source until D57; their last bytes stay reachable through git
#: history. `SHADOW_DROPS` below, and the slim and clearance passes, were written for them
#: and are still what OfficeSuite is built with.
OFFICE_SUITE = PackSpec(
    item_id="officesuite",
    pack_dir="OfficeSuite",
    display_name="OfficeSuite",
    description="OfficeSuite [LAS]",
    slim=0.95,
    clearance=True,
    hands="palm_cut",
    tex_override={"suit": "Tex_07(L_7)3.dds", "jewelry": "Tex_23(L_23)2.dds"},
    fps=True,
)

#: OfficeSuite plus the Miranda Romance head, as one whole-character LAS pack: the
#: skin brings its own head and registers `replace_all`, so the heister's head and
#: the mask are out of the picture (D56). Its body is OfficeSuite's, palm cut included.
#: Like OfficeSuite it ships its first-person arms unit (D53/D55): a whole-character
#: pack replaces the FP arms too, so without one the first-person view has no hands.
OFFICE_SUITE_HEAD = PackSpec(
    item_id="officesuite_head",
    pack_dir="OfficeSuite_Head",
    display_name="OfficeSuite + Miranda Head",
    description=(
        "OfficeSuite [LAS] as a complete character: the black suit and light shirt from "
        "OfficeSuite with the Miranda Romance head and lashes. Replaces the body, head and "
        "mask. Legendary Armour Skins whole-character outfit."
    ),
    slim=0.95,
    clearance=True,
    hands="palm_cut",
    head=True,
    fps=True,
    tex_override={"suit": "Tex_07(L_7)3.dds", "jewelry": "Tex_23(L_23)2.dds"},
)

#: ``PACKS`` is what `make honokodae` builds: OfficeSuite alone. The head pack is a
#: target of its own (``build_honoko2_dae.py --only officesuite_head``), so OfficeSuite's
#: bytes stay identical; `HEAD_PACKS` is what the runner adds when asked.
HEAD_PACKS = (OFFICE_SUITE_HEAD,)
PACKS = (OFFICE_SUITE,)

#: The donor drawable the head pack re-skins, its source materials, and the unit
#: inside the donor ZIP the head is read from (the native Hila override's unit).
HEAD_DONOR = "OfficeSuite_Miranda_Romance_over_Hila.zip"
HEAD_SLOTS = ("head", "lashes")
HILA_HEAD_UNIT = "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female"

# Source garment kinds, in the deterministic order the material slots are emitted in; every DAE
# submesh maps to exactly one kind, and each pack names its slots `<item_id>_<kind>`.
MAT_TEXTURE_SOURCES = {
    "body": ("L_3.dds", "L_4.dds"),
    "suit": ("L_7.dds", "L_8.dds"),
    "panties": ("L_14.dds", "L_15.dds"),
    "bra": ("L_17.dds", "L_18.dds"),
    "shoes": ("L_20.dds", "L_21.dds"),
    "jewelry": ("L_23.dds", "L_24.dds"),
}

# Submeshes kept from Honoka_DOAXVV_Secret_Reportout.dae -> (TMC parent mesh, out slot).
# Expected DAE texture filenames are verified against the XML scene bindings.
SUBMESH_SPEC = {
    "WGT_new_aya_body_1": ("WGT_new_aya_body_decl0", "body", "L_3.dds"),
    "WGT_new_aya_body_2": ("WGT_new_aya_body_decl0", "jewelry", "L_23.dds"),
    "WGT_new_aya_body_3": ("WGT_new_aya_body_decl0", "shoes", "L_20.dds"),
    "WGT_new_aya_body_4": ("WGT_new_aya_body_decl0", "jewelry", "L_23.dds"),
    "WGT_new_aya_body_5": ("WGT_new_aya_body_decl0", "jewelry", "L_23.dds"),
    "WGT_new_aya_body_6": ("WGT_new_aya_body_decl0", "jewelry", "L_23.dds"),
    "WGT_new_aya_body_7": ("WGT_new_aya_body_decl0", "jewelry", "L_23.dds"),
    "WGT_new_aya_body_8": ("WGT_new_aya_body_decl0", "bra", "L_17.dds"),
    "WGT_headdress2_0": ("WGT_headdress2", "suit", "L_7.dds"),
    "WGT_headdress2_1": ("WGT_headdress2", "suit", "L_7.dds"),
    "WGT_headdress2_2": ("WGT_headdress2", "suit", "L_7.dds"),
    "WGT_headdress2_3": ("WGT_headdress2", "suit", "L_7.dds"),
    "WGT_headdress2_4": ("WGT_headdress2", "suit", "L_7.dds"),
    "WGT_headdress2_5": ("WGT_headdress2", "panties", "L_14.dds"),
}

EXCLUDED_DAE = {
    "WGT_cap2_0..3": "unbuttoned jacket overlay (z-fights with buttoned WGT_headdress2 suit)",
    "WGT_new_aya_body_0": "280-vertex uniform-weight debug slab (decl1)",
    "WGT_sweat_chest_0": "chest emblem decal",
}


def _parse_dae_submeshes(dae_path: Path) -> list[dict]:
    """Parse geometry submeshes and material->DDS bindings from Collada XML."""
    ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
    root = ET.parse(dae_path).getroot()

    eff_img = {
        e.attrib["id"]: e.find(".//c:init_from", ns).text
        for e in root.findall(".//c:library_effects/c:effect", ns)
    }
    img_file = {
        im.attrib["id"]: urllib.parse.unquote(im.find("c:init_from", ns).text.split("/")[-1])
        for im in root.findall(".//c:library_images/c:image", ns)
    }
    mat_dds = {}
    for m in root.findall(".//c:library_materials/c:material", ns):
        eid = m.find("c:instance_effect", ns).attrib["url"].lstrip("#")
        fn = img_file[eff_img[eid]]
        dds = fn.split("(")[1].split(")")[0] + ".dds" if "(" in fn and ")" in fn else fn
        mat_dds[m.attrib["id"]] = dds

    geom_dds = {}
    for node in root.findall(".//c:library_visual_scenes//c:node", ns):
        ig = node.find("c:instance_geometry", ns)
        if ig is None:
            continue
        gid = ig.attrib["url"].lstrip("#")
        tgt = ig.find(".//c:instance_material", ns).attrib["target"].lstrip("#")
        geom_dds[gid] = mat_dds[tgt]

    import numpy as np

    out = []
    for g in root.findall(".//c:library_geometries/c:geometry", ns):
        gname = g.attrib.get("name", g.attrib["id"])
        if gname not in SUBMESH_SPEC:
            continue
        mesh = g.find("c:mesh", ns)
        tris_el = mesh.find("c:triangles", ns)
        srcs = {
            s.attrib["id"]: np.fromstring(s.find("c:float_array", ns).text, sep=" ")
            for s in mesh.findall("c:source", ns)
        }
        vinp = {
            i.attrib["semantic"]: i.attrib["source"].lstrip("#")
            for i in mesh.find("c:vertices", ns).findall("c:input", ns)
        }
        pos = srcs[vinp["POSITION"]].reshape(-1, 3)
        nrm = srcs[vinp["NORMAL"]].reshape(-1, 3)
        uv = srcs[vinp["TEXCOORD"]].reshape(-1, 2)
        tris = np.fromstring(tris_el.find("c:p", ns).text, sep=" ", dtype=np.int64).reshape(-1, 3)
        out.append({
            "name": gname,
            "dds": geom_dds[g.attrib["id"]],
            "pos_m": pos,
            "nrm": nrm,
            "uv": uv,
            "tris": tris,
        })
    return out


def _build_tmc_lookup(mesh):
    """Build quantized (0.1 mm) lookup table + raw arrays for fast vertex skin transfer."""
    import numpy as np

    pos_m = np.asarray(mesh.positions, dtype=np.float64) / 100.0
    pal = np.asarray(mesh.palette, dtype=np.int64) if mesh.palette is not None else None
    gidx = np.asarray(mesh.bone_indices, dtype=np.int64)
    if pal is not None:
        gidx = pal[gidx]
    wgt = np.asarray(mesh.weights, dtype=np.float64)

    table: dict[tuple[int, int, int], int] = {}
    q = np.rint(pos_m * 10000.0).astype(np.int64)
    for i in range(len(pos_m)):
        key = (int(q[i, 0]), int(q[i, 1]), int(q[i, 2]))
        if key not in table:
            table[key] = i
    return pos_m, gidx, wgt, table


def _match_skin_indices(pos_m, tmc_lookup) -> tuple[list[int], float]:
    import numpy as np

    ref_pos, _, _, table = tmc_lookup
    q = np.rint(pos_m * 10000.0).astype(np.int64)
    matched = [-1] * len(pos_m)
    miss = []
    for i in range(len(pos_m)):
        hit = table.get((int(q[i, 0]), int(q[i, 1]), int(q[i, 2])))
        if hit is not None:
            matched[i] = hit
        else:
            miss.append(i)
    max_err = 0.0
    if miss:
        sub = pos_m[miss]
        for start in range(0, len(sub), 256):
            chunk = sub[start : start + 256]
            d2 = ((chunk[:, None, :] - ref_pos[None, :, :]) ** 2).sum(axis=2)
            idx = np.argmin(d2, axis=1)
            err = float(np.sqrt(d2[np.arange(len(chunk)), idx]).max())
            max_err = max(max_err, err)
            for k, orig_i in enumerate(miss[start : start + 256]):
                matched[orig_i] = int(idx[k])
    if max_err > 1e-4:
        raise ValueError(f"DAE->TMC vertex match exceeded 0.1 mm: max_err={max_err:.6f} m")
    return matched, max_err


def _scale_leg_fits_to_floor(fits: dict, model, skel_map: dict, template, target_z: float = -0.47) -> float:
    """Scale leg retarget fits about each hip joint so the heels stand on `target_z`."""
    import numpy as np

    import diesel_model as dm

    # Find lowest vertex in honoko2_shoes after initial retargeting
    shoe_sub = next(m for m in model.meshes if m.material == "shoes")
    shoe_vi = sorted({i for i in shoe_sub.triangle_indices})
    z_min = float("inf")
    for vi in shoe_vi:
        v = model.vertices[vi]
        p = np.zeros(3, dtype=np.float64)
        wsum = 0.0
        for b_idx, w in v.weights:
            if b_idx in fits:
                p += w * np.array(dm.mat_apply_point(fits[b_idx], v.pos), dtype=np.float64)
                wsum += w
        if wsum > 0:
            p /= wsum
            if p[2] < z_min:
                z_min = float(p[2])

    hip_l = np.array(template.worlds[template.name_id["LeftUpLeg"]][12:15], dtype=np.float64)
    z_hip = float(hip_l[2])
    k = (z_hip - target_z) / max(1e-6, z_hip - z_min)

    for side in ("Left", "Right"):
        anchor = np.array(template.worlds[template.name_id[f"{side}UpLeg"]][12:15], dtype=np.float64)
        s_mat = np.eye(4, dtype=np.float64)
        s_mat[:3, :3] = k * np.eye(3, dtype=np.float64)
        s_mat[3, :3] = (1.0 - k) * anchor
        scaled_legs: set[int] = set()
        for tname in (f"{side}UpLeg", f"{side}Leg", f"{side}Foot", f"{side}ToeBase"):
            for bi, bone in enumerate(model.bones):
                if skel_map["map"].get(bone.name) == tname and bi in fits and bi not in scaled_legs:
                    fits[bi] = dm.mat_mul(fits[bi], tuple(float(x) for x in s_mat.reshape(-1)))
                    scaled_legs.add(bi)
    return k


def _dominant_bones(weights, palette, vertex_ids) -> dict[str, int]:
    """How many of the given vertices each bone dominates: what a cut removed, by bone."""
    counts: dict[str, int] = {}
    for vi in vertex_ids:
        infl = weights[vi]
        if not infl:
            continue
        name = palette[max(infl, key=lambda kv: kv[1])[0]]
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _last_kept_cm(g, palm, r_max: float = 28.0) -> float:
    """How far past the palm plane the surviving geometry reaches (cm, along the axis)."""
    import numpy as np

    verts = np.asarray(g.verts, dtype=np.float64)
    origin = np.asarray(palm["origin"], dtype=np.float64)
    axis = np.asarray(palm["axis"], dtype=np.float64)
    rel = verts - origin
    axial = rel @ axis
    perp = np.linalg.norm(rel - np.outer(axial, axis), axis=1)
    near = perp < r_max
    return round(float(axial[near].max()), 2) if near.any() else 0.0


def _cap_cut_rims(g, planes, margin: float = 0.0) -> int:
    """Cap the open rim a palm-base cut leaves on `honoko2_body`, inside its slice block."""
    import numpy as np

    if not g.slices or g.slices[0][0] != "body":
        return 0
    src_mat, base_v, base_i, tri_count, nverts = g.slices[0]
    verts = np.asarray(g.verts, dtype=np.float64)
    sl_faces = np.asarray(g.faces[:tri_count], dtype=np.int64)

    # Directed edges used by exactly one triangle on honoko2_body slice
    counts: dict[tuple[int, int], int] = {}
    directed: list[tuple[int, int]] = []
    for a, b, c in sl_faces:
        for x, y in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            key = (x, y) if x < y else (y, x)
            counts[key] = counts.get(key, 0) + 1
            directed.append((x, y))
    bedges = [(x, y) for (x, y) in directed if counts[(x, y) if x < y else (y, x)] == 1]
    if not bedges:
        return 0

    added_verts = []
    added_normals = []
    added_uvs = []
    added_weights = []
    added_faces = []

    for origin, axis in planes:
        origin = np.asarray(origin, dtype=np.float64)
        axis = np.asarray(axis, dtype=np.float64)
        rim_edges = []
        for x, y in bedges:
            mid = 0.5 * (verts[x] + verts[y])
            rel = mid - origin
            t = float(rel @ axis)
            perp = float(np.linalg.norm(rel - t * axis))
            if margin - 1.5 <= t <= margin + 0.5 and perp < 10.0:
                rim_edges.append((x, y))
        if len(rim_edges) < 4:
            continue
        ring_idx = sorted({v for e in rim_edges for v in e})
        ctr = verts[ring_idx].mean(axis=0)
        c_idx = base_v + nverts + len(added_verts)
        added_verts.append((float(ctr[0]), float(ctr[1]), float(ctr[2])))
        added_normals.append((float(axis[0]), float(axis[1]), float(axis[2])))
        added_uvs.append(tuple(g.uvs[ring_idx[0]]))
        w_acc: dict[int, float] = {}
        for vi in ring_idx:
            for bi, w in g.weights[vi]:
                w_acc[bi] = w_acc.get(bi, 0.0) + w / len(ring_idx)
        top_w = sorted(w_acc.items(), key=lambda kv: kv[1], reverse=True)[:4]
        ws = sum(w for _, w in top_w) or 1.0
        added_weights.append([(bi, w / ws) for bi, w in top_w])

        # Fan every directed boundary edge in opposite orientation (y, x, c_idx)
        for x, y in rim_edges:
            added_faces.append((y, x, c_idx))

    if not added_verts:
        return 0

    nv = len(added_verts)
    nf = len(added_faces)
    # Insert cap verts at end of slice 0 vertex block and shift later slices/faces
    ins_v = base_v + nverts
    g.verts = g.verts[:ins_v] + added_verts + g.verts[ins_v:]
    g.normals = g.normals[:ins_v] + added_normals + g.normals[ins_v:]
    g.uvs = g.uvs[:ins_v] + added_uvs + g.uvs[ins_v:]
    g.weights = g.weights[:ins_v] + added_weights + g.weights[ins_v:]

    shifted_tail = [tuple(vi + nv if vi >= ins_v else vi for vi in f) for f in g.faces[tri_count:]]
    g.faces = list(g.faces[:tri_count]) + added_faces + shifted_tail

    new_slices = [(src_mat, base_v, base_i, tri_count + nf, nverts + nv)]
    for (m, bv, bi, tc, nl) in g.slices[1:]:
        new_slices.append((m, bv + nv, bi + nf * 3, tc, nl))
    g.slices = new_slices
    return nf


def dae_to_model_data(dae_submeshes: list[dict], tmc):
    """Build a `source_model.ModelData` from `.dae` geometry + `.TMC` skin weights.

    The meshes carry the garment *kinds* (`body`, `suit`, ...) as their material names, not a
    pack's slots: one `ModelData` (and its expensive retarget fits) is shared by every pack, and
    `build_pack` renames the kinds to `<item_id>_<kind>` when it transfers them.
    """
    import tmc_las
    from source_model import Bone, ModelData, SkinVertex, SubMesh

    M = tmc_las.basis_matrix()
    model = ModelData(name="honoko2_dae")
    for i, name in enumerate(tmc.node_names):
        model.bones.append(
            Bone(name=name, parent=int(tmc.hie_parent[i]), pos=(0.0, 0.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0))
        )

    tmc_by_name = {m.source_id: _build_tmc_lookup(m) for m in tmc.load_meshes()}

    # Merge DAE submeshes by garment kind, in the deterministic MAT_TEXTURE_SOURCES order
    slot_verts: dict[str, list] = {kind: [] for kind in MAT_TEXTURE_SOURCES}
    slot_tris: dict[str, list] = {kind: [] for kind in MAT_TEXTURE_SOURCES}
    max_match_err = 0.0

    for sub in dae_submeshes:
        tmc_name, slot, want_dds = SUBMESH_SPEC[sub["name"]]  # slot is a garment kind here
        if sub["dds"] != want_dds:
            raise ValueError(f"{sub['name']}: DAE texture {sub['dds']} != expected {want_dds}")
        lookup = tmc_by_name[tmc_name]
        _, gidx, wgt, _ = lookup
        matched, err = _match_skin_indices(sub["pos_m"], lookup)
        max_match_err = max(max_match_err, err)

        pos_d = (sub["pos_m"] * 100.0) @ M.T
        nrm_d = sub["nrm"] @ M.T
        uv = sub["uv"]
        vbase = len(slot_verts[slot])
        for n in range(len(pos_d)):
            ti = matched[n]
            infl = tuple(
                (int(gidx[ti, k]), float(wgt[ti, k]))
                for k in range(4)
                if wgt[ti, k] > 1e-6
            )
            slot_verts[slot].append(
                SkinVertex(
                    pos=(float(pos_d[n, 0]), float(pos_d[n, 1]), float(pos_d[n, 2])),
                    normal=(float(nrm_d[n, 0]), float(nrm_d[n, 1]), float(nrm_d[n, 2])),
                    uv=(float(uv[n, 0]), float(uv[n, 1])),
                    weights=infl,
                )
            )
        slot_tris[slot].extend(int(i) + vbase for i in sub["tris"].reshape(-1))

    for slot in MAT_TEXTURE_SOURCES:
        v0 = len(model.vertices)
        model.vertices.extend(slot_verts[slot])
        model.meshes.append(
            SubMesh(material=slot, triangle_indices=tuple(i + v0 for i in slot_tris[slot]))
        )
    return model, max_match_err


def _reduce_half(arr):
    h, w = arr.shape[:2]
    fh = 2 if h > 1 else 1
    fw = 2 if w > 1 else 1
    return arr.reshape(h // fh, fh, w // fw, fw, -1).mean(axis=(1, 3))


def _full_mip_levels(image, colour: bool) -> list:
    """All mip levels of RGBA `image` down to 1x1, supporting rectangular dims."""
    import numpy as np

    from dds_encode import linear_to_srgb, srgb_to_linear

    image = np.asarray(image, dtype=np.uint8)
    levels = [image]
    if colour:
        light = srgb_to_linear(image[..., :3] / 255.0)
        alpha = image[..., 3].astype(np.float64)
        while max(light.shape[:2]) > 1:
            light = _reduce_half(light)
            alpha = _reduce_half(alpha[..., None])[..., 0]
            rgb = np.clip(linear_to_srgb(light) * 255.0, 0.0, 255.0)
            levels.append(np.dstack([rgb, alpha]).round().astype(np.uint8))
    else:
        cur = image.astype(np.float64)
        while max(cur.shape[:2]) > 1:
            cur = _reduce_half(cur)
            levels.append(np.clip(cur, 0.0, 255.0).round().astype(np.uint8))
    return levels


def build_textures(spec: "PackSpec") -> tuple[dict[str, bytes], dict]:
    """Decode all 6 diffuse+normal DDS pairs into PD2 BC3 `.texture`s with full mips."""
    import hashlib as _hl

    import numpy as np
    from PIL import Image

    import dds_encode

    textures: dict[str, bytes] = {}
    report: dict[str, dict] = {}
    for slot, (df_dds, nm_dds) in sorted(spec.mat_sources().items()):
        for kind, dds_name in (("df", df_dds), ("nm", nm_dds)):
            stem = f"{slot}_{kind}"
            src_bytes = (TEX_DIR / dds_name).read_bytes()
            pil_im = Image.open(io.BytesIO(src_bytes)).convert("RGBA")
            if pil_im.width != pil_im.height:
                sq = min(pil_im.width, pil_im.height, 512) if kind == "nm" else min(max(pil_im.width, pil_im.height), 512)
                pil_im = pil_im.resize((sq, sq), Image.Resampling.LANCZOS)
            im = np.asarray(pil_im, dtype=np.uint8)
            if kind == "df":
                alpha = np.full(im.shape[:2], 20, dtype=np.uint8)
                img = np.dstack([im[..., :3], alpha]).astype(np.uint8)
                levels = _full_mip_levels(img, colour=True)
            else:
                x = im[..., 0].astype(np.int16)
                y = 255 - im[..., 1].astype(np.int16)
                img = np.dstack([
                    np.full(im.shape[:2], 255, np.uint8),
                    np.clip(y, 0, 255).astype(np.uint8),
                    np.zeros(im.shape[:2], np.uint8),
                    x.astype(np.uint8),
                ])
                levels = _full_mip_levels(img, colour=False)
            textures[f"{stem}.texture"] = dds_encode.bc3_dds_from_levels(levels)
            report[stem] = {
                "source": f"references/Honoka/{dds_name}",
                "source_sha256": _hl.sha256(src_bytes).hexdigest(),
                "size": list(im.shape[:2]),
                "mips": len(levels),
                "out_sha256": _hl.sha256(textures[f"{stem}.texture"]).hexdigest(),
            }
    return textures, report


def render_material_config(spec: "PackSpec") -> str:
    def contour_mat(slot: str) -> str:
        return (
            f'    <material name="{slot}" unique="true" version="2"\n'
            '              render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{spec.unit_base}/{slot}_df"/>\n'
            f'        <bump_normal_texture file="{spec.unit_base}/{slot}_nm"/>\n'
            '        <variable value="1 1 1" type="vector3" name="contour_color"/>\n'
            '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
            "    </material>\n"
        )

    # The head's skin uses the same shader as the body's; its lashes are cut out
    # by the diffuse alpha, exactly as the donor's own `mtr_lashes` was.
    head_slot, lashes_slot = spec.head_slots if spec.head else (None, None)
    head_skin = head_slot          # already the "_df" stem: the pair names the base
    lashes_single = lashes_slot

    def lash_mat(slot: str) -> str:
        return (
            f'    <material name="{slot}" unique="true" version="2"\n'
            '              render_template="opacity:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{spec.unit_base}/{slot}"/>\n'
            "    </material>\n"
        )

    parts = [f'<materials version="3" group="{spec.item_id}">\n\n']
    for slot in spec.slots():
        parts.append(contour_mat(slot) + "\n")
    if spec.head:
        parts.append(contour_mat(head_skin) + "\n")
        parts.append(lash_mat(lashes_single) + "\n")
    parts.append('    <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n')
    parts.append("</materials>")
    return "".join(parts)


def render_fps_material_config(spec: "PackSpec", slots: list[str]) -> str:
    """The first-person unit's material config: DEPTH_SCALING, no contour, no unique."""
    def fps_mat(slot: str) -> str:
        return (
            f'    <material name="{slot}" version="2"\n'
            '              render_template="generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{spec.unit_base}/{slot}_df"/>\n'
            f'        <bump_normal_texture file="{spec.unit_base}/{slot}_nm"/>\n'
            "    </material>\n"
        )

    parts = [f'<materials version="3" group="{spec.fps_stem}">\n\n']
    for slot in slots:
        parts.append(fps_mat(slot) + "\n")
    parts.append('    <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n')
    parts.append("</materials>")
    return "".join(parts)


def registration(spec: "PackSpec"):
    import las_outfit_pack as lop

    return lop.Registration(
        item_id=spec.item_id,
        display_name=spec.display_name,
        description=spec.description,
        unit=spec.tpp_unit,
        # A pack that brings its own head replaces the whole character: body,
        # head and mask. One that does not is a body skin and leaves the
        # heister's head and mask alone.
        flags=lop.WHOLE_CHARACTER if spec.head else lop.BODY_ONLY,
        fps_unit=spec.fps_unit,
        category=spec.item_id,
        icon=f"{spec.gui_base}/{spec.item_id}",
        hook_file=f"{spec.item_id}_las.lua",
        pairs=tuple(f"{spec.unit_base}/{slot}" for slot in spec.slots()),
        # The head's lashes sample a diffuse whose cutout lives in its alpha, so
        # that one travels as a single texture next to the df/nm pairs.
        textures=tuple(f"{spec.unit_base}/{slot}" for slot in spec.head_textures) if spec.head else (),
        # No default glove for either mode, and no stock hands beside the outfit's
        # own body (D58/D60). A glove the player picks by hand still spawns and
        # wins, which is the whole point of a pack with no hands in it.
        #
        # The glove *adapter* stays off: it spawns the vanilla bare-forearm piece
        # (`hnd_forearms`) to bridge a glove cuff and a short sleeve, and on this
        # outfit that piece is a second, vanilla skin at the wrist - the thing the
        # user rejected twice (D59's adapter, then D60).
        glove_adapter=False,
        own_hands=True,
    )


def _head_meshes(model_path: Path, spec: "PackSpec") -> list[dict]:
    """The head drawable as one part per atom, material keyed by the pack's slots."""
    import numpy as np

    import diesel_model as dm

    mf = dm.ModelFile.read_path(model_path)
    parts = []
    sid = next((s.id for s in mf.by_type(dm.MODEL_DATA)
                if (d := dm.decode_model_data(s.payload))["name_hash"] == dm.hash64("g_head")
                and d["version"] == 3), None)
    if sid is None:
        raise ValueError("a pack with head=True has no g_head drawable to render")
    data = dm.decode_model_data(mf.by_id(sid).payload)
    gp = dm.decode_passthroughgp(mf.by_id(data["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    top = np.asarray(dm.decode_topology(mf.by_id(gp["topology"]).payload)["indices"],
                     dtype=np.int64).reshape(-1, 3)
    verts = np.asarray(geo["verts"], dtype=np.float64)
    normals = np.asarray(geo["normals"], dtype=np.float64)
    uvs = np.asarray(geo["uv0"], dtype=np.float64)
    for atom, slot in zip(data["atoms"], spec.head_slots):
        start = atom["base_index"] // 3
        tris = top[start:start + atom["tri_count"]]
        used = np.unique(tris)
        remap = np.full(len(verts), -1, np.int64)
        remap[used] = np.arange(len(used))
        parts.append({"material": slot, "vertices": verts[used], "normals": normals[used],
                      "uvs": uvs[used], "triangles": remap[tris]})
    return parts


def _render_icon_bytes(spec: "PackSpec", model_path: Path, textures: dict[str, bytes]) -> bytes:
    import numpy as np
    from PIL import Image

    import las_outfit_pack as lop
    import preview_textured as pt

    # `material_meshes` returns the one multi-material drawable (the body). A
    # whole-character pack also has a head, so that gets its own textured parts
    # or the icon shows a headless character.
    mesh_list = pt.material_meshes(model_path)
    tex_by_mat = {}
    for slot in spec.slots():
        data = textures[f"{slot}_df.texture"]
        tex_by_mat[slot] = np.asarray(Image.open(io.BytesIO(data)).convert("RGBA"), dtype=np.float32) / 255.0

    if spec.head:
        skin, lashes = spec.head_slots
        mesh_list = mesh_list + _head_meshes(model_path, spec)
        for slot, stem in ((skin, f"{skin}_df"), (lashes, lashes)):
            tex_by_mat[slot] = np.asarray(
                Image.open(io.BytesIO(textures[f"{stem}.texture"])).convert("RGBA"),
                dtype=np.float32) / 255.0

    size = 256
    imgs = [
        pt.render(mesh_list, tex_by_mat, view, size, 1.18, np.array([0.0, 2.0, 97.0]), flip_v=True, cull=True)
        for view in ("front", "side", "back", "threequarter")
    ]
    sheet = Image.new("RGB", (4 * size, size))
    for i, img in enumerate(imgs):
        sheet.paste(img, (i * size, 0))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return lop.build_icon(buf.getvalue(), view=3)


def _slim_groups(groups: dict, template, factor: float) -> dict:
    """Scale every vertex's offset from its skinned bone rest point by `factor`.

    A skinned outfit cannot simply be scaled in world space: the game animates it through the
    2B skeleton, so a smaller mesh has to keep the joints where the rig puts them, or the collar
    drops away from the heister's head, the wrist cuts leave the gloves and the soles leave the
    floor. Each vertex is therefore pulled toward the rest position of the bones it is weighted
    to - the weights blend the anchors, so the surface stays continuous - and only its offset
    from them shrinks. Height, joint placement and bone lengths are untouched; girth is not.
    """
    import numpy as np

    moved = 0
    total = 0
    shift_max = 0.0
    for g in groups.values():
        worlds = template.worlds
        rest = g.rest_worlds or {}
        anchors = {}
        for name in g.palette:
            world = rest.get(name)
            if world is None:
                world = worlds[template.name_id[name]]
            anchors[name] = np.asarray(world, dtype=np.float64)[12:15]

        v = np.asarray(g.verts, dtype=np.float64)
        anchor = np.zeros_like(v)
        wsum = np.zeros(len(v), dtype=np.float64)
        for vi, infl in enumerate(g.weights):
            for pal_idx, w in infl:
                if w <= 0.0:
                    continue
                anchor[vi] += w * anchors[g.palette[pal_idx]]
                wsum[vi] += w
        weighted = wsum > 1e-9
        anchor[weighted] /= wsum[weighted, None]
        anchor[~weighted] = v[~weighted]  # nothing moves a vertex the skin ignores

        out = anchor + factor * (v - anchor)
        delta = np.linalg.norm(out - v, axis=1)
        moved += int((delta > 1e-6).sum())
        total += int(len(v))
        shift_max = max(shift_max, float(delta.max()) if len(delta) else 0.0)
        g.verts = [tuple(float(c) for c in row) for row in out]

    # Scaling pulls the soles up by a few millimetres (they hang below the ankle bones); set the
    # outfit back on the floor so the shoes still touch it.
    z_min = min(min(vertex[2] for vertex in g.verts) for g in groups.values())
    drop = -0.47 - z_min
    if abs(drop) > 1e-9:
        for g in groups.values():
            g.verts = [(x, y, z + drop) for x, y, z in g.verts]
    return {
        "factor": factor,
        "vertices": total,
        "vertices_moved": moved,
        "max_shift_cm": round(shift_max, 4),
        "floor_shift_cm": round(drop, 4),
    }


def _clearance_pass(groups: dict, spec: PackSpec) -> dict:
    """Open the layer gaps the in-game captures showed closing (D44).

    The 2026-11-15 close-ups of the outfit in game showed dark angular flakes where two shells of
    the pack sat within a fraction of a millimetre of each other: measured on the built mesh, the
    bra shell stood 0.2 mm off the skin, the necklace chain 0.7 mm and the collar 3.6 mm, and the
    5% slim of Honoko3 pressed every pair together a little more, which is why the flakes appeared
    with it. At those gaps the depth test and the shadow map alternate between the two surfaces and
    the engine draws one shell's unlit inside through the other. This pass sinks the torso and neck
    skin 2 mm along its own normals and the bra 0.5 mm along its own, which opens >= 1.2 mm of air
    at every measured contact while moving nothing the eye sees: all of it sits under the suit,
    except the necklace, which now floats 2.7 mm off the skin instead of cutting into it.

    The matching half of the fix is in `build_pack`: the shadow-caster drawable no longer carries
    the bra and panties shells. Both are fully enclosed by the suit and the body, so they add
    nothing to the pack's silhouette but did cast shadow-map depth through those sub-millimetre
    gaps - the classic source of angular acne flakes on the surface above them.
    """
    import numpy as np

    skin_shrink, bra_shrink = 0.20, 0.05  # cm, along each shell's own normals
    moved = 0
    max_shift = 0.0
    for g in groups.values():
        v = np.asarray(g.verts, dtype=np.float64)
        faces = np.asarray(g.faces, dtype=np.int64)
        nrm = np.zeros_like(v)
        cr = np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]])
        for k in range(3):
            np.add.at(nrm, faces[:, k], cr)
        ln = np.linalg.norm(nrm, axis=1)
        ln[ln == 0] = 1.0
        nrm /= ln[:, None]

        rad = np.hypot(v[:, 0], v[:, 1])
        off = np.zeros(len(v))
        for (src, base_v, base_i, tris, nverts), slot in zip(g.slices, g.mat_slots):
            sl = slice(base_v, base_v + nverts)
            if slot == spec.slot("body"):
                z, r = v[sl, 2], rad[sl]
                off[sl] += np.where((z > 108.0) & (r < 12.0), skin_shrink, 0.0)
            elif slot == spec.slot("bra"):
                off[sl] += bra_shrink
        out = v - nrm * off[:, None]
        delta = np.linalg.norm(out - v, axis=1)
        moved += int((delta > 1e-6).sum())
        max_shift = max(max_shift, float(delta.max()) if len(delta) else 0.0)
        g.verts = [tuple(float(c) for c in row) for row in out]
    return {
        "skin_shrink_cm": skin_shrink,
        "bra_shrink_cm": bra_shrink,
        "shadow_caster_drops": sorted(SHADOW_DROPS),
        "vertices_moved": moved,
        "max_shift_cm": round(max_shift, 4),
    }


def build_pack(
    spec: PackSpec,
    template,
    model,
    skel_map: dict,
    fits: dict,
    leg_floor_scale: float,
    work: Path,
    out: Path,
    no_previews: bool,
    source: dict,
    fps_template=None,
    head_donor=None,
) -> Path:
    """Transfer the shared source model into `spec`'s skeleton, package it, and write its zip."""
    import hashlib as _hl

    import build_models as bm
    import las_outfit_pack as lop
    import tmc_las

    kinds = list(MAT_TEXTURE_SOURCES)
    # the bra and panties shells are fully enclosed by the suit and the body: keeping them in the
    # shadow caster adds no silhouette, only shadow-map acne through the sub-millimetre gaps (D44).
    # Honoko2 (clearance=False) kept the old shadow caster so its bytes in git history stand;
    # the clearance flag and this branch survive D57 for OfficeSuite's passes.
    shadow_kinds = [k for k in kinds if k not in SHADOW_DROPS] if spec.clearance else kinds
    pack_specs = {
        "outfit": {
            "drawables": ["g_body", "g_body_lod1"],
            "materials": kinds,
            "out_materials": spec.slots(),
            "mat_slots": {kind: spec.slot(kind) for kind in kinds},
        },
        "shadow": {
            "drawables": ["s_body"],
            "materials": shadow_kinds,
            "out_materials": ["shadow_caster"],
        },
    }

    # Where each palm begins: the rig's Hand joint and the axis to its knuckles (D59).
    # It is a property of the skeleton, not of this outfit, so it is measured once.
    palms = bm.palm_planes(template) if spec.hands != "own" else None
    palm_planes = ([(palms[side]["origin"], palms[side]["axis"]) for side in (-1, 1)]
                   if palms else [])

    groups = {}
    share = {}
    cut_report = {}
    for gname, gspec in pack_specs.items():
        g = bm.transfer_group(model, gspec, skel_map, template, gname, fits=fits, swap_winding=False)
        cut = {}
        if palms is not None:
            # Before the cut, so the report can say what it took away by bone.
            weights, palette = list(g.weights), list(g.palette)
            cut = tmc_las.clip_group_at_palm_bases(g, palms, margin=PALM_EXTEND_CM)
            cut["removed_bones"] = _dominant_bones(weights, palette, cut["removed_vertex_ids"])
            del cut["removed_vertex_ids"]
            # The only vertices a palm cut may take are hand and finger ones and, if
            # the plane sits near the crease, forearm ones. Cutting `PALM_EXTEND_CM`
            # into the palm takes none of the forearm's; anything that is neither a
            # hand, a finger nor an arm bone means the plane is wrong - a leg inside
            # the 28 cm cone, say.
            stray = sorted(b for b in cut["removed_bones"] if not bm.is_fps_arm_bone(b))
            if stray:
                raise SystemExit(f"[{gname}] the palm cut took geometry off {stray}, "
                                 "which is not a hand, finger or arm bone")
            cut["palm_base"] = {("left" if side < 0 else "right"): {
                "origin_cm": [round(v, 3) for v in palms[side]["origin"]],
                "axis": [round(v, 4) for v in palms[side]["axis"]],
                "deg_from_forearm": round(palms[side]["deg_from_forearm"], 2),
            } for side in (-1, 1)}
        thin = tmc_las.drop_long_thin_triangles(g)
        # The rim a palm cut leaves is capped: with no hands in the pack the cut end
        # is what the game draws until a glove spawns, and an open rim would show the
        # inside of the sleeve in first person and in the shadow map. The rim is
        # `PALM_EXTEND_CM` past the crease, inside the palm, so the cap looks for it
        # there rather than at the plane.
        cap_tris = _cap_cut_rims(g, palm_planes, PALM_EXTEND_CM) if palms is not None else 0
        cut["long_thin"] = thin
        cut["rim_cap_tris"] = cap_tris
        cut["leg_floor_scale"] = leg_floor_scale
        cut["hands"] = spec.hands
        cut_report[gname] = cut
        groups[gname] = g
        for d in gspec["drawables"]:
            share[d] = gname

    if palms is not None:
        # Straight after the cut, before the slim and the clearance pass: how far
        # the surviving surface reaches past the palm line. A clip lands on the plane
        # it was given - `PALM_EXTEND_CM` (4.00) into the palm since D62; the D60 clip
        # landed on the crease itself (0.00), and the drop it replaced at -2.22/-2.27.
        for side, key in ((-1, "left"), (1, "right")):
            cut_report["outfit"]["palm_base"][key]["clipped_to_cm"] = _last_kept_cm(
                groups["outfit"], palms[side])

    slim_report = _slim_groups(groups, template, spec.slim) if spec.slim != 1.0 else None
    clear_report = _clearance_pass(groups, spec) if spec.clearance else None

    if palms is not None:
        # Where the shipped mesh ends, after slim and clearance: the most distal
        # vertex left within the 28 cm radius, measured from the palm plane. The cut
        # itself is on the plane (`clipped_to_cm`, 0.00); the 5% slim then pulls the
        # whole arm in towards its bones, so the rim ends a few millimetres
        # proximal of it. This is the number "where the palm begins" resolves to.
        for side, key in ((-1, "left"), (1, "right")):
            cut_report["outfit"]["palm_base"][key]["kept_to_cm"] = _last_kept_cm(groups["outfit"], palms[side])

    head = None
    if spec.head:
        import las_head

        if head_donor is None:
            raise SystemExit("a pack with head=True needs the head donor (--head-donor)")
        head, head_source = las_head.load(head_donor, template, spec.item_id, HILA_HEAD_UNIT)
        # Repo-relative when the donor lives in the repo: `fresh` builds in a copy of the
        # tree, and an absolute path would make its bytes differ from the tracked ones.
        donor = (head_donor.relative_to(REPO).as_posix() if head_donor.is_relative_to(REPO)
                 else str(head_donor))
        source = {**source, "head": head.report, "head_donor": donor}
        if len(head.slots) != 2:
            raise ValueError(f"expected the head's two material atoms, got {head.slots}")
        groups["head"] = head.group
        share["g_head"] = "head"

    # The template's own head goes unless this pack brings one: a drawable that is
    # present but disabled would still carry someone else's character in the pack.
    drop = ("g_head_lod1",) if spec.head else ("g_head", "g_head_lod1")
    tpp_mf = bm.assemble_model(template, groups, share, drop_drawables=drop)

    # The first-person unit: the same slimmed, cleared outfit arms as the
    # third-person body (the FPS skeleton shares the PD2 bind pose, so the same
    # geometry lands where the viewmodel skeleton expects it), with the same palm
    # cut, so the heister's own glove shows in the viewmodel too. No head
    # drawables.
    fps: dict = {}
    if spec.fps:
        if fps_template is None:
            raise SystemExit("a pack with fps=True needs the fps 2B template (--templates)")
        arms = bm.extract_bones(groups["outfit"], bm.is_fps_arm_bone, "arms")
        arm_shadow = bm.extract_bones(groups["shadow"], bm.is_fps_arm_bone, "arm_shadow")
        fps_mf = bm.assemble_model(
            fps_template,
            {"arms": arms, "shadow": arm_shadow},
            {"g_body": "arms", "g_body_lod1": "arms", "s_body": "shadow"},
            drop_drawables=("g_head", "g_head_lod1"),
        )
        fps = {"arms": arms, "shadow": arm_shadow, "mf": fps_mf}
        work.mkdir(parents=True, exist_ok=True)
        work_tmp = work / f".{spec.item_id}_fps_audit_tmp.model"
        work_tmp.write_bytes(fps_mf.write())
        fps["audit"] = bm.audit_model(work_tmp)
        work_tmp.unlink()

    work.mkdir(parents=True, exist_ok=True)
    tpp_path = work / f"{spec.item_id}.model"
    tpp_path.write_bytes(tpp_mf.write())
    fps_path = None
    if spec.fps:
        if fps["audit"]:
            raise ValueError(f"{spec.item_id} fps model fails the audit: {fps['audit']}")
        fps_path = work / f"fps_{spec.item_id}.model"
        fps_path.write_bytes(fps["mf"].write())

    textures, tex_report = build_textures(spec)
    if head is not None:
        # The donor's head maps are already PD2 `.texture` files with full mips,
        # so they travel unchanged; only their stem follows the pack's slots.
        for slot, data in head.textures.items():
            textures[slot] = data
        tex_report.update(head.report.get("textures", {}))
    reg = registration(spec)

    pack = work / spec.pack_dir
    if pack.exists():
        shutil.rmtree(pack)
    unit_dir = pack / "assets" / spec.unit_base
    gui_dir = pack / "assets" / spec.gui_base
    (pack / "hooks").mkdir(parents=True)
    (pack / "localization").mkdir(parents=True)
    unit_dir.mkdir(parents=True)
    gui_dir.mkdir(parents=True)

    (pack / "main.xml").write_bytes(lop.main_xml(reg).encode("utf-8"))
    (pack / "hooks" / f"{spec.item_id}_las.lua").write_bytes(lop.hook_lua(reg).encode("utf-8"))
    if reg.glove_adapter:
        (pack / "hooks" / f"{spec.item_id}_glove_adapter.lua").write_bytes(
            lop.render_glove_adapter_lua(spec.item_id, spec.display_name).encode("utf-8")
        )
    if reg.own_hands:
        (pack / "hooks" / f"{spec.item_id}_own_hands.lua").write_bytes(
            lop.render_own_hands_lua(spec.item_id, spec.display_name).encode("utf-8")
        )
    (pack / "localization" / "english.txt").write_bytes(lop.localization(reg).encode("utf-8"))

    if not no_previews:
        icon = _render_icon_bytes(spec, tpp_path, textures)
    else:
        icon = tmc_las.fallback_icon()
    (gui_dir / f"{spec.item_id}.texture").write_bytes(icon)
    for name, data in sorted(textures.items()):
        (unit_dir / name).write_bytes(data)

    (unit_dir / f"{spec.item_id}.model").write_bytes(tpp_path.read_bytes())
    (unit_dir / f"{spec.item_id}.unit").write_bytes(lop.render_unit_xml(spec.tpp_unit).encode("utf-8"))
    drawables = lop.model_drawables(tpp_path.read_bytes())
    (unit_dir / f"{spec.item_id}.object").write_bytes(
        lop.render_object_xml(spec.tpp_unit, drawables,
                              also_visible=("g_head",) if spec.head else ()).encode("utf-8")
    )
    (unit_dir / f"{spec.item_id}.material_config").write_bytes(
        render_material_config(spec).encode("utf-8")
    )

    if spec.fps:
        assert fps_path is not None
        fps_stem = spec.fps_stem
        fps_unit = spec.fps_unit
        fps_bytes = fps_path.read_bytes()
        fps_drawables = lop.model_drawables(fps_bytes)
        fps_slots = sorted(set(fps["arms"].mat_slots))
        (unit_dir / f"{fps_stem}.model").write_bytes(fps_bytes)
        (unit_dir / f"{fps_stem}.unit").write_bytes(lop.render_unit_xml(fps_unit).encode("utf-8"))
        (unit_dir / f"{fps_stem}.object").write_bytes(
            lop.render_object_xml(fps_unit, fps_drawables).encode("utf-8")
        )
        (unit_dir / f"{fps_stem}.material_config").write_bytes(
            render_fps_material_config(spec, fps_slots).encode("utf-8")
        )

    payload = {
        path.relative_to(pack).as_posix(): _hl.sha256(path.read_bytes()).hexdigest()
        for path in sorted(pack.rglob("*"))
        if path.is_file()
    }
    build_info = {
        "pack": spec.pack_dir,
        "item_id": spec.item_id,
        "registration": {
            "hook_source": lop.HOOK_SOURCE,
            "table": f"LegendaryArmours.{spec.item_id}",
            "flags": list(reg.flags),
            "unit": spec.tpp_unit,
            "fps_unit": spec.fps_unit,
            "glove_adapter": reg.glove_adapter,
            "own_hands": reg.own_hands,
        },
        "models_present": True,
        "runtime_verified": False,
        "source": {
            **source,
            "submeshes": sorted(SUBMESH_SPEC),
            "excluded": EXCLUDED_DAE,
            "textures": tex_report,
        },
        "payload_sha256": payload,
    }
    if spec.fps:
        build_info["fps"] = {
            "model": f"{spec.fps_stem}.model",
            "unit": spec.fps_stem,
            "drawables": lop.model_drawables(fps_path.read_bytes()),
            "slots": sorted(set(fps["arms"].mat_slots)),
            "arms": {"verts": len(fps["arms"].verts), "tris": len(fps["arms"].faces)},
            "shadow": {"verts": len(fps["shadow"].verts), "tris": len(fps["shadow"].faces)},
        }
    # How the hands were treated, and - for a cut - the plane it was made on, so
    # "where the palm begins" is a number in the pack and not a claim in a doc.
    build_info["hands"] = spec.hands
    if palms is not None:
        body_cut = cut_report.get("outfit", {})
        build_info["palm_cut"] = {
            "plane": body_cut.get("palm_base"),
            "margin_cm": PALM_EXTEND_CM,
            "extend_cm": PALM_EXTEND_CM,
            # the cut splits the triangles it crosses instead of dropping them whole
            "exact": True,
            "tris_split": body_cut.get("tris_split"),
            "verts_added": body_cut.get("verts_added"),
            "removed_tris": body_cut.get("tris_dropped"),
            "removed_bones": body_cut.get("removed_bones"),
            "rim_cap_tris": body_cut.get("rim_cap_tris"),
        }
    if slim_report is not None:
        build_info["slim"] = slim_report
    if clear_report is not None:
        build_info["clearance"] = clear_report
    (pack / "BUILD_INFO.json").write_text(
        json.dumps(build_info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    out.mkdir(parents=True, exist_ok=True)
    zip_out = out / f"{spec.pack_dir}.zip"
    built_zip = lop.zip_pack(pack)
    if built_zip != zip_out:
        shutil.copy2(built_zip, zip_out)
    zip_sha256 = write_pack_checksum(zip_out, REPO)
    sha_rel = zip_out.relative_to(REPO).as_posix() if zip_out.is_relative_to(REPO) else zip_out.name

    report = {
        "runtime_verified": False,
        "pack": spec.pack_dir,
        "zip": sha_rel,
        "zip_sha256": zip_sha256,
        "drawables": drawables,
        "cut": cut_report,
        "fps": ({
            "drawables": lop.model_drawables(fps_path.read_bytes()),
            "arms": {"verts": len(fps["arms"].verts), "tris": len(fps["arms"].faces)},
            "shadow": {"verts": len(fps["shadow"].verts), "tris": len(fps["shadow"].faces)},
            "slots": sorted(set(fps["arms"].mat_slots)),
        } if spec.fps else None),
        "groups": {
            gname: {"verts": len(g.verts), "tris": len(g.faces), "palette": list(g.palette)}
            for gname, g in groups.items()
        },
    }
    if slim_report is not None:
        report["slim"] = slim_report
    if clear_report is not None:
        report["clearance"] = clear_report
    (work / f"{spec.item_id}_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {zip_out} ({zip_out.stat().st_size} bytes) sha256={zip_sha256[:16]}...")
    return zip_out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES,
                    help="directory containing 2b.model (default: where extract_2b.py unpacks it)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="directory for the Honoko*.zip packs + .sha256 (default: dist/Honoka)")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK,
                    help="working directory for intermediate model/pack tree (default: build/honoko2)")
    ap.add_argument("--dae", type=Path, default=DAE_PATH)
    ap.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    ap.add_argument("--no-previews", action="store_true",
                    help="skip the 3D render used to generate the HUD icon")
    ap.add_argument("--head-donor", type=Path, default=None,
                    help="unit ZIP the --only head packs re-skin their head from "
                         "(default: the tracked native Hila override)")
    ap.add_argument("--only", default="",
                    help="comma-separated item ids to build; the default is the tracked "
                         "pack, and 'officesuite_head' builds the whole-character one")
    args = ap.parse_args(argv)
    determinism.enter(__file__)

    import hashlib as _hl

    import build_models as bm
    import tmc as tmc_mod
    import tmc_las

    need_fps = any(spec.fps for spec in PACKS)
    require = bm.require_templates(
        args.templates, ("2b.model", "fps_2b.model") if need_fps else ("2b.model",)
    ) / "2b.model"
    if not args.dae.is_file():
        raise SystemExit(f"missing Collada input: {args.dae}")
    if not args.source_zip.is_file():
        raise SystemExit(f"missing TMC archive: {args.source_zip}")
    template = bm.load_template(require)
    fps_template = bm.load_template(args.templates / "fps_2b.model") if need_fps else None

    dae_bytes = args.dae.read_bytes()
    dae_sha = _hl.sha256(dae_bytes).hexdigest()
    zip_sha = _hl.sha256(args.source_zip.read_bytes()).hexdigest()

    with tempfile.TemporaryDirectory(prefix="honoko2_tmc_") as td:
        with zipfile.ZipFile(args.source_zip) as zf:
            tmc_bytes = zf.read(TMC_NAME)
        tmc_sha = _hl.sha256(tmc_bytes).hexdigest()
        tmc_path = Path(td) / TMC_NAME
        tmc_path.write_bytes(tmc_bytes)
        tmc = tmc_mod.TmcFile(str(tmc_path))
        src_worlds = tmc_las.glbl_to_diesel(tmc.global_raw)
        dae_subs = _parse_dae_submeshes(args.dae)
        model, max_match_err = dae_to_model_data(dae_subs, tmc)

    skel_map = json.loads((HERE / "tmc_skeleton_map.json").read_text())
    fits = bm.retarget_maps(model, skel_map, template, src_worlds=src_worlds)
    leg_floor_scale = _scale_leg_fits_to_floor(fits, model, skel_map, template, target_z=-0.47)

    source = {
        "dae": str(args.dae.relative_to(REPO)) if args.dae.is_relative_to(REPO) else str(args.dae),
        "dae_sha256": dae_sha,
        "skin_archive": str(args.source_zip.relative_to(REPO))
        if args.source_zip.is_relative_to(REPO) else str(args.source_zip),
        "skin_archive_sha256": zip_sha,
        "tmc_sha256": tmc_sha,
        "dae_to_tmc_max_match_err_m": max_match_err,
    }

    wanted = {name.strip() for name in args.only.split(",") if name.strip()}
    known = {spec.item_id: spec for spec in PACKS + HEAD_PACKS}
    if unknown := wanted - known.keys():
        raise SystemExit(f"unknown pack(s): {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(sorted(known))}")
    specs = [known[name] for name in sorted(wanted, key=lambda n: list(known).index(n))] if wanted else PACKS

    head_donor = None
    if any(spec.head for spec in specs):
        head_donor = args.head_donor or dist_path(REPO, HEAD_DONOR)
        if not head_donor.is_file():
            raise SystemExit(f"missing head donor: {head_donor}")

    for spec in specs:
        build_pack(
            spec,
            template,
            model,
            skel_map,
            fits,
            leg_floor_scale,
            args.work_dir / spec.item_id,
            args.out,
            args.no_previews,
            source,
            fps_template=fps_template,
            head_donor=head_donor,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
