#!/usr/bin/env python3
"""Audit a built LAS pack against the ModWorkshop LAS/MOOG outfit guide.

Guide: "Legendary Armor Skins/LAS/MOOG/Outfit Module Guide" (Columbus),
https://wiki.modworkshop.net/books/payday-2-mod-creation/page/legendary-armor-skinslasmoogoutfit-module-guide

Every check carries the guide rule it enforces, so a failure says *what* the
guide prescribes and *what* the pack does instead. Rules that the guide
leaves open (or that only the running game can settle) are reported as WARN,
never as a silent pass.

Usage:
    python tools/pd2-port/check_guide_compliance.py            # dist/lawson_las.zip
    python tools/pd2-port/check_guide_compliance.py FILE.zip
    python tools/pd2-port/check_guide_compliance.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import dds  # noqa: E402
from dmodel import DieselModel, hash_str  # noqa: E402

RIG_JSON = HERE / "reference" / "las_rig.json"
DEFAULT_PACK = ROOT / "dist" / "lawson_las.zip"
UNIT_DIR = "units/lawson/skins/lawson"
GUI_DIR = "guis/dlcs/lawson/armor_skins"

# Render templates the guide attests (its material_config example, its
# first-person example, plus the ones the 2B reference pack ships). Anything
# else risks a black material - guide: "You cannot create your own render
# templates ... will cause your material to appear black in-game".
TEMPLATES = {
    "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS",
    "generic:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS",
    "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS",
    "generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_1WEIGHT",
    "shadow_caster_only:SKINNED_1WEIGHT",
}

# the PD2 skeleton the guide enumerates (54 bones)
NAMED_BONES = [
    "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
    "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase",
]

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, status: str, cid: str, rule: str, detail: str) -> None:
        self.checks.append({"id": cid, "status": status, "rule": rule,
                            "detail": detail})

    def ok(self, cid, rule, detail):
        self.add(PASS, cid, rule, detail)

    def warn(self, cid, rule, detail):
        self.add(WARN, cid, rule, detail)

    def fail(self, cid, rule, detail):
        self.add(FAIL, cid, rule, detail)

    def counts(self) -> dict[str, int]:
        out = {PASS: 0, WARN: 0, FAIL: 0}
        for c in self.checks:
            out[c["status"]] += 1
        return out


# --------------------------------------------------------------------- utils
def rig_maps() -> tuple[dict[int, str], dict[int, dict]]:
    """name_hash -> name and id -> bone record, from the rig contract."""
    data = json.loads(RIG_JSON.read_text())
    by_hash: dict[int, str] = {}
    by_id: dict[int, dict] = {}
    for b in data["bones"]:
        by_id[b["id"]] = b
        if b.get("name"):
            by_hash[int(b["name_hash"], 16)] = b["name"]
    return by_hash, by_id


def model_of(path: Path) -> DieselModel:
    return DieselModel(str(path))


def object3d_tree(model: DieselModel) -> tuple[dict[int, dict], dict[int, list[int]]]:
    objs: dict[int, dict] = {}
    kids: dict[int, list[int]] = {}
    for s in model.sections:
        if s.tag != "object3D" or s.obj is None:
            continue
        objs[s.id] = {"hash": s.obj.name_hash, "parent": s.obj.parent_id}
        kids.setdefault(s.obj.parent_id, []).append(s.id)
    return objs, kids


def descendants(objs, kids, root: int) -> list[int]:
    out, stack = [], list(kids.get(root, []))
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(kids.get(n, []))
    return out


def drawable_of(model: DieselModel, sec) -> dict:
    """model_data section -> geometry/skinbones/material ids."""
    passthrough = model.by_id.get(sec.obj.passthrough_id)
    geo_id = None
    if passthrough and passthrough.obj is not None:
        geo_id = passthrough.obj.geometry_id
    mg = model.by_id.get(sec.obj.matgroup_id)
    mat_ids = list(mg.obj.items) if mg and mg.obj is not None else []
    mats = []
    for mid in mat_ids:
        m = model.by_id.get(mid)
        if m is not None and m.obj is not None:
            mats.append(m.obj.name_hash)
    return {
        "name_hash": sec.obj.name_hash,
        "atoms": sec.obj.render_atoms,
        "geometry_id": geo_id,
        "skinbones_id": sec.obj.skinbones_id,
        "material_hashes": mats,
        "matgroup_id": sec.obj.matgroup_id,
    }


def atom_influences(geometry, base: int, count: int) -> int:
    """Largest number of bones with weight > 0.001 in an atom's vertex range."""
    worst = 0
    for i in range(base, min(base + count, len(geometry.weights3))):
        w = geometry.weights3[i]
        worst = max(worst, sum(1 for x in w if x > 0.001))
    return worst


# ---------------------------------------------------------------- the checks
def check_skeleton(rep: Report, model: DieselModel, by_hash, by_id) -> None:
    objs, kids = object3d_tree(model)
    named = {by_hash[h] for h in (o["hash"] for o in objs.values()) if h in by_hash}
    missing = [b for b in NAMED_BONES if b not in named]
    if missing:
        rep.fail("S1", "guide: the PD2 rig is 1 pelvis + 3 spine + shoulders/arms/"
                       "forearms/hands + 3-bone fingers + legs/feet/toebases",
                 f"missing bones: {missing}")
    else:
        rep.ok("S1", "guide: the PD2 rig is 1 pelvis + 3 spine + shoulders/arms/"
                     "forearms/hands + 3-bone fingers + legs/feet/toebases",
               f"all {len(NAMED_BONES)} named PD2 bones present in the model")

    # finger chains: children of each Hand bone, three levels deep
    hands = [sid for sid, o in objs.items()
             if by_hash.get(o["hash"]) in ("LeftHand", "RightHand")]
    finger_total = 0
    for h in hands:
        chains = kids.get(h, [])
        per = sum(1 + len(descendants(objs, kids, c)) for c in chains)
        finger_total += per
    if finger_total >= 30:
        rep.ok("S2", "guide: 3 bones per finger, 5 fingers, both hands (30)",
               f"{finger_total} finger bones in the skeleton")
    else:
        rep.fail("S2", "guide: 3 bones per finger, 5 fingers, both hands (30)",
                 f"only {finger_total} finger bones in the skeleton")

    # locators / effect objects: the unnamed object3Ds that are not fingers
    finger_ids = set()
    for h in hands:
        for c in kids.get(h, []):
            finger_ids.add(c)
            finger_ids.update(descendants(objs, kids, c))
    locators = [sid for sid, o in objs.items()
                if o["hash"] not in by_hash and sid not in finger_ids]
    if locators:
        rep.ok("S3", "guide: leave locator/effect objects (Aim, e_taser, ...) alone",
               f"{len(locators)} unnamed locator objects kept in the unit")
    else:
        rep.warn("S3", "guide: leave locator/effect objects (Aim, e_taser, ...) alone",
                 "no locator objects in the unit - tase/bag interactions may break")


def check_finger_binds(rep: Report, model: DieselModel, rig) -> None:
    """The PD2 finger bones must carry the hands' weight, or the hands are mittens.

    The guide puts 3 bones per finger into the PD2 rig and asks you to rename
    your bones to the PD2 names (merging only the twist bones). A ported model
    whose finger joints are folded into the Hand bone keeps the rig bones but
    loses the articulation.
    """
    kids: dict[int, list[int]] = {}
    for b in rig["bones"]:
        if b["id"] >= 10000:
            continue
        kids.setdefault(b["parent_id"], []).append(b["id"])
    by_name = {b["name"]: b["id"] for b in rig["bones"] if b.get("name")}
    hash_to_id = {int(b["name_hash"], 16): b["id"] for b in rig["bones"]
                  if b["id"] < 10000}
    finger_ids: set[int] = set()
    for hand in ("LeftHand", "RightHand"):
        stack = list(kids.get(by_name.get(hand, -1), []))
        while stack:
            n = stack.pop()
            finger_ids.add(n)
            stack.extend(kids.get(n, []))
    if not finger_ids:
        rep.warn("S6", "guide: 3 bones per finger - the finger chains exist so the "
                       "ported fingers keep their own bones",
                 "the rig contract has no finger chains")
        return
    sec_rig: dict[int, int] = {}
    for s in model.sections:
        if s.tag == "object3D" and s.obj is not None:
            rid = hash_to_id.get(s.obj.name_hash)
            if rid is not None:
                sec_rig[s.id] = rid
    used: set[int] = set()
    for s in model.sections:
        if s.tag != "skinbones" or s.obj is None:
            continue
        for oid in s.obj.object_ids:
            rid = sec_rig.get(oid)
            if rid in finger_ids:
                used.add(rid)
    if used:
        rep.ok("S6", "guide: 3 bones per finger - the finger chains exist so the "
                     "ported fingers keep their own bones",
               f"{len(used)} finger bone(s) carry weight")
    else:
        rep.fail("S6", "guide: 3 bones per finger - the finger chains exist so the "
                       "ported fingers keep their own bones",
                 f"the skeleton has {len(finger_ids)} finger bones but none of them "
                 "carries a vertex: every hand vertex is bound to the Hand bone, "
                 "so the fingers will not articulate (mitten hands)")


def check_tangents(rep: Report, model: DieselModel) -> None:
    """Tangents on, or the normal maps look wrong (guide's export checklist)."""
    from dmodel import BR
    sizes = [0, 4, 8, 12, 16, 4, 4, 8, 4, 4]
    total = zeros = 0
    missing = []
    for s in model.sections:
        if s.tag != "geometry" or s.obj is None:
            continue
        g = s.obj
        types = [t for _sz, t in g.headers]
        if 22 not in types or 23 not in types:
            missing.append(g.name or str(s.id))
            continue
        br = BR(model.data)
        br.p = s.start
        n = br.u32()
        hc = br.u32()
        headers = [(br.u32(), br.u32()) for _ in range(hc)]
        for isz, ity in headers:
            stride = sizes[isz]
            if ity in (22, 23):
                for _ in range(n):
                    b = br.bytes(4)
                    total += 1
                    if b[0] == 0 and b[1] == 0 and b[2] == 0 and b[3] == 0:
                        zeros += 1
            else:
                br.p += stride * n
    if missing:
        rep.fail("S7", "guide: export with tangents on, or the normal maps look "
                       "wrong in-game",
                 f"geometry without tangent channels: {missing}")
        return
    if total and zeros:
        rep.warn("S7", "guide: export with tangents on, or the normal maps look "
                       "wrong in-game",
                 f"{zeros} of {total} tangent vectors are zero (degenerate UVs "
                 "there) - the normal map has no direction to work with")
    else:
        rep.ok("S7", "guide: export with tangents on, or the normal maps look "
                     "wrong in-game",
               f"tangent and bitangent channels present and non-degenerate "
               f"({total} vectors)")


def check_skinning(rep: Report, model: DieselModel, by_hash) -> None:
    """Weights: at most 3 influences, no twist bones, skinning keyword match."""
    max_inf = 0
    fourth = False
    for s in model.sections:
        if s.tag != "geometry" or s.obj is None:
            continue
        g = s.obj
        if g.fourth:
            fourth = True
        for w in g.weights3:
            max_inf = max(max_inf, sum(1 for x in w if x > 0.001))
        if (3, 19) not in g.headers:
            rep.fail("S4", "guide: PAYDAY 2 supports 3 weight influences per vertex",
                     f"geometry {g.name or s.id} has no 3-float BLENDWEIGHT0 channel")
            return
    if fourth:
        rep.fail("S4", "guide: PAYDAY 2 supports 3 weight influences per vertex",
                 "a 4th weight channel is present")
        return
    rep.ok("S4", "guide: PAYDAY 2 supports 3 weight influences per vertex",
           f"every vertex carries at most {max_inf} influence(s), 3-float channel")

    # twist bones: the guide says merge them into the parent bone
    rolls = []
    for s in model.sections:
        if s.tag != "skinbones" or s.obj is None:
            continue
        for oid in s.obj.object_ids:
            sec = model.by_id.get(oid)
            if sec is None or sec.obj is None:
                continue
            name = by_hash.get(sec.obj.name_hash)
            if name and "Roll" in name:
                rolls.append(name)
    if rolls:
        rep.warn("S5", "guide: merge twist bones into their parent bone",
                 f"skeleton still carries twist bones ({sorted(set(rolls))}); "
                 "check they carry no weight")
    else:
        rep.ok("S5", "guide: merge twist bones into their parent bone",
               "no twist bone in any skin palette")


def check_materials(rep: Report, pack: dict[str, bytes],
                    model: DieselModel, cfg: str, fps: bool) -> None:
    """material_config against the guide's rules."""
    mats = re.findall(r"<material\b([^>]*)>", cfg)
    if not mats:
        rep.fail("M1", "guide: .material_config declares one material per mesh material",
                 f"{cfg}: no <material> entries")
        return
    attrs = [dict(re.findall(r'(\w+)="([^"]*)"', a)) for a in mats]

    if 'version="3"' in cfg.split(">")[0]:
        rep.ok("M1", "guide: header <materials version=\"3\" group=\"...\">",
               "version 3 header with a group attribute")
    else:
        rep.fail("M1", "guide: header <materials version=\"3\" group=\"...\">",
                 "missing version=\"3\" in the materials header")
    if 'group="' in cfg.split(">")[0]:
        group = re.search(r'group="([^"]*)"', cfg.split(">")[0]).group(1)
        if fps and not group.startswith("fps"):
            rep.fail("M2", "guide: the FPS config uses a fps_* group",
                     f"FPS group is {group!r}")
        else:
            rep.ok("M2", "guide: each config has its own group= attribute",
                   f"group={group!r}")
    else:
        rep.fail("M2", "guide: each config has its own group= attribute",
                 "no group attribute on the materials header")

    # names must match the model's materials (hash comparison)
    model_hashes = {s.obj.name_hash for s in model.sections
                    if s.tag == "material" and s.obj is not None}
    cfg_hashes = {hash_str(a.get("name", "")) for a in attrs}
    if model_hashes == cfg_hashes:
        rep.ok("M3", "guide: material names must match the model's material names",
               f"{len(cfg_hashes)} material(s), names match the model exactly")
    else:
        only_cfg = {a.get("name") for a in attrs} - {
            n for n in ("",) }
        rep.fail("M3", "guide: material names must match the model's material names",
                 f"config has {len(cfg_hashes)} materials, model has "
                 f"{len(model_hashes)}; unmatched: {sorted(only_cfg)}")

    # render templates
    bad = [a.get("render_template") for a in attrs
           if a.get("render_template") not in TEMPLATES]
    if bad:
        rep.fail("M4", "guide: only attested render templates - invented keyword "
                       "combinations render black",
                 f"unattested templates: {sorted(set(bad))}")
    else:
        rep.ok("M4", "guide: only attested render templates - invented keyword "
                     "combinations render black",
               f"all {len(attrs)} materials use attested templates")

    # contour rules
    contour_bad = []
    for a in attrs:
        t = a.get("render_template", "")
        if "CONTOUR" in t:
            if a.get("unique") != "true":
                contour_bad.append(f"{a.get('name')}: missing unique=\"true\"")
            if 'name="contour_color"' not in cfg:
                contour_bad.append(f"{a.get('name')}: no contour_color variable")
            if 'name="contour_opacity"' not in cfg:
                contour_bad.append(f"{a.get('name')}: no contour_opacity variable")
    if contour_bad:
        rep.fail("M5", "guide: CONTOUR needs unique=\"true\" plus contour_color "
                       "and contour_opacity variables",
                 "; ".join(contour_bad))
    else:
        rep.ok("M5", "guide: CONTOUR needs unique=\"true\" plus contour_color "
                     "and contour_opacity variables",
               "every contour material carries unique=true and both variables")

    # FPS depth scaling
    if fps:
        tpl = {a.get("render_template", "") for a in attrs}
        if any("DEPTH_SCALING" in t for t in tpl):
            rep.ok("M6", "guide: the FPS material_config needs DEPTH_SCALING",
                   "FPS templates carry DEPTH_SCALING")
        else:
            rep.fail("M6", "guide: the FPS material_config needs DEPTH_SCALING",
                     "no DEPTH_SCALING in the FPS templates")

    # texture paths: no extension, and they must resolve inside the pack
    unresolved = []
    for path in re.findall(r'file="([^"]+)"', cfg):
        if "." in path.rsplit("/", 1)[-1]:
            unresolved.append(f"{path}: file extension in the path")
            continue
        hits = [k for k in pack if k.endswith(f"{path}.texture")
                or k.endswith(f"{path}.material_config")
                or k.endswith(f"{path}.model") or k.endswith(f"{path}.unit")]
        if not hits:
            unresolved.append(f"{path}: no file in the pack")
    if unresolved:
        rep.fail("M7", "guide: texture paths in material_config carry no file "
                       "extension and must resolve",
                 "; ".join(unresolved))
    else:
        rep.ok("M7", "guide: texture paths in material_config carry no file "
                     "extension and must resolve",
               "every texture path is extensionless and resolves in the pack")


def check_skinning_keyword(rep: Report, model: DieselModel, cfg: str,
                            label: str) -> None:
    """SKINNED_nWEIGHTS must not claim fewer influences than the geometry uses."""
    name_by_hash = {}
    for m in re.finditer(r'<material\b([^>]*)>', cfg):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        name_by_hash[hash_str(a.get("name", ""))] = a.get("render_template", "")
    worst = []
    for s in model.sections:
        if s.tag != "model_data" or s.obj is None or not s.obj.render_atoms:
            continue
        d = drawable_of(model, s)
        geo = model.by_id.get(d["geometry_id"])
        if geo is None or geo.obj is None:
            continue
        for atom in d["atoms"]:
            base = atom["base_vertex"]
            nverts = atom["geo_len"]
            mat_id = atom["material_id"]
            tpl = name_by_hash.get(d["material_hashes"][mat_id], "")
            m = re.search(r"SKINNED_(\d)WEIGHT", tpl)
            if not m:
                continue
            claim = int(m.group(1))
            used = atom_influences(geo.obj, base, nverts)
            if used > claim:
                worst.append(f"{d['material_hashes'][mat_id] and name_by_hash and ''}"
                             f"material #{mat_id} claims {claim} weight(s), "
                             f"geometry uses {used}")
    if worst:
        rep.fail("K1", "guide: the skinning keyword must match the geometry "
                       "(SKINNED_1WEIGHT reads a single influence)",
                 "; ".join(worst))
    else:
        rep.ok("K1", "guide: the skinning keyword must match the geometry "
                     "(SKINNED_1WEIGHT reads a single influence)",
               f"{label}: every material's skinning keyword covers its geometry")


def check_fps(rep: Report, pack: dict[str, bytes], fps_model: DieselModel,
              fps_cfg: str) -> None:
    """The FPS unit must contain arms and nothing else."""
    names = []
    for s in fps_model.sections:
        if s.tag == "model_data" and s.obj is not None and s.obj.render_atoms:
            names.append(s.obj.name_hash)
    if len(names) == 1:
        rep.ok("F1", "guide: a separate unit with just the arm mesh - nothing else",
               "the FPS model has a single drawable (arms only)")
    else:
        rep.fail("F1", "guide: a separate unit with just the arm mesh - nothing else",
                 f"the FPS model has {len(names)} drawables")
    fps_mats = re.findall(r'<material name="([^"]+)"', fps_cfg)
    extra = [m for m in fps_mats if m not in ("mtr_body1", "mtr_body2",
                                              "shadow_caster")]
    if extra:
        rep.fail("F2", "guide: the FPS unit carries no head/face materials",
                 f"unexpected FPS materials: {extra}")
    else:
        rep.ok("F2", "guide: the FPS unit carries no head/face materials",
               f"FPS materials: {fps_mats}")


def check_textures(rep: Report, pack: dict[str, bytes]) -> None:
    """DXT5 + full mip pyramid + PD2 normal-map layout."""
    dxt_bad, normal_bad, flat_maps = [], [], []
    normals_checked = 0
    for path, data in sorted(pack.items()):
        if not path.endswith(".texture"):
            continue
        problems = dds.validate_dxt5_texture(data)
        if problems:
            dxt_bad.append(f"{path}: {problems}")
            continue
        size = struct.unpack_from("<I", data, 12)[0]
        if path.endswith("_nm.texture"):
            normals_checked += 1
            mip0 = data[dds.DDS_HEADER_SIZE:]
            img = dds.decode_dxt5(mip0, size, size)
            flat = img.reshape(-1, 4) if hasattr(img, "reshape") else img
            ch = list(zip(*flat))
            r, g, b, a = ch[0], ch[1], ch[2], ch[3]
            is_flat = (max(r) - min(r) < 4 and max(g) - min(g) < 4
                       and max(b) - min(b) < 4 and max(a) - min(a) < 4)
            if is_flat:
                # a synthesized flat normal (the source has no normal map for
                # this material): the layout rules do not apply to it
                flat_maps.append(path.rsplit("/", 1)[-1])
                continue
            if min(r) < 250:
                normal_bad.append(f"{path}: red is not white (min {min(r)})")
            if max(b) > 8:
                normal_bad.append(f"{path}: blue is not black (max {max(b)})")
            if max(a) - min(a) < 8:
                normal_bad.append(f"{path}: alpha is flat - X is not in alpha")
            if max(g) - min(g) < 4:
                normal_bad.append(f"{path}: green is flat - no Y in the normal map")
    if dxt_bad:
        rep.fail("T1", "guide: compress with DXT5 (DXT1 discards alpha)",
                 "; ".join(dxt_bad))
    else:
        rep.ok("T1", "guide: compress with DXT5 (DXT1 discards alpha)",
               f"every .texture is DXT5 with a full mip pyramid "
               f"({normals_checked} normal maps)")
    if normal_bad:
        rep.fail("T2", "guide: PD2 normal maps put X in alpha, red white, blue "
                       "black, green Y",
                 "; ".join(normal_bad))
    else:
        rep.ok("T2", "guide: PD2 normal maps put X in alpha, red white, blue "
                     "black, green Y",
               f"{normals_checked - len(flat_maps)} normal map(s) in the PD2 "
               f"layout"
               + (f"; {len(flat_maps)} synthesized flat (no source normal map)"
                  if flat_maps else ""))


def check_packaging(rep: Report, pack: dict[str, bytes]) -> None:
    main = pack.get("Lawson_LAS/main.xml", b"").decode()
    if not main:
        rep.fail("P1", "guide: the mod_overrides folder is a BeardLib table with "
                       "Localization, Hooks and AddFiles",
                 "no main.xml in the pack")
        return
    for needle, label in (("<Localization", "Localization"),
                           ("<Hooks", "Hooks"),
                           ("<AddFiles", "AddFiles"),
                           ('source_file="lib/tweak_data/armorskinstweakdata"',
                            "the armorskinstweakdata hook")):
        if needle in main:
            rep.ok("P1", "guide: the mod_overrides folder is a BeardLib table "
                         "with Localization, Hooks and AddFiles",
                   f"main.xml carries {label}")
        else:
            rep.fail("P1", "guide: the mod_overrides folder is a BeardLib table "
                           "with Localization, Hooks and AddFiles",
                     f"main.xml lacks {label}")

    # AddFiles entries must resolve (paths are relative to the table root,
    # i.e. the pack's Lawson_LAS/ folder, and carry no extension)
    missing = []
    for kind, path in re.findall(r'<(texture|df_nm|unit_mat) path="([^"]+)"', main):
        if kind == "texture":
            if f"Lawson_LAS/{path}.texture" not in pack:
                missing.append(f"texture {path}")
        elif kind == "df_nm":
            for suffix in ("_df.texture", "_nm.texture"):
                if f"Lawson_LAS/{path}{suffix}" not in pack:
                    missing.append(f"df_nm {path}{suffix}")
        else:
            if f"Lawson_LAS/{path}.material_config" not in pack:
                missing.append(f"unit_mat {path}")
    if missing:
        rep.fail("P2", "guide: AddFiles registers the pack's own files",
                 f"unresolved: {missing}")
    else:
        rep.ok("P2", "guide: AddFiles registers the pack's own files",
               "every texture, df_nm and unit_mat entry resolves in the pack")

    hook = pack.get("Lawson_LAS/hooks/lawson.lua", b"").decode()
    need = ["category", "unit", "fps_unit", "hide_mask", "hide_armor",
            "replace_all", "fps_hide_armor", "fps_replace_body"]
    gone = [n for n in need if n not in hook]
    if gone:
        rep.fail("P3", "guide: the LAS registration hides the mask and armour "
                       "and replaces the body in third person and first person",
                 f"hook lacks {gone}")
    else:
        rep.ok("P3", "guide: the LAS registration hides the mask and armour "
                     "and replaces the body in third person and first person",
               "hook registers the full 2B flag set")

    loc = pack.get("Lawson_LAS/localization/english.txt", b"").decode()
    try:
        keys = set(json.loads(loc))
    except Exception:
        keys = set()
    want = {"bm_menu_lawson_armor_skins", "bm_askn_lawson", "bm_askn_lawson_desc"}
    if want <= keys:
        rep.ok("P4", "guide: the outfit needs its menu strings in the pack's "
                     "localization",
               "localization carries the menu, name and description keys")
    else:
        rep.fail("P4", "guide: the outfit needs its menu strings in the pack's "
                       "localization",
                 f"missing keys: {sorted(want - keys)}")


def check_notes(rep: Report, pack: dict[str, bytes]) -> None:
    """The manifest and the credits must state the pack's real status."""
    try:
        man = json.loads(pack["Lawson_LAS/build_manifest.json"])
    except Exception:
        rep.warn("N1", "guide: nothing - but a shipped pack should say what it is",
                 "no readable build_manifest.json")
        return
    if man.get("runtime_verified") is False and man.get("status"):
        rep.ok("N1", "guide: nothing - but a shipped pack should say what it is",
               f"manifest states version {man.get('version')}, "
               f"status {man.get('status')!r}")
    else:
        rep.warn("N1", "guide: nothing - but a shipped pack should say what it is",
                 "the manifest does not state the verification status")
    credits = pack.get("Lawson_LAS/CREDITS.txt", b"").decode()
    if "Mass Effect" in credits and ("rights" in credits.lower()
                                     or "licens" in credits.lower()):
        rep.ok("N2", "guide: nothing - but a shipped pack must credit its sources",
               "CREDITS.txt names the source and the rights position")
    else:
        rep.warn("N2", "guide: nothing - but a shipped pack must credit its sources",
                 "CREDITS.txt does not state the source and rights position")


# ------------------------------------------------------------------- driver
def audit(pack_path: Path) -> Report:
    rep = Report()
    with zipfile.ZipFile(pack_path) as z:
        pack = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    by_hash, _by_id = rig_maps()
    rig = json.loads(RIG_JSON.read_text())

    tpp_bytes = pack.get(f"Lawson_LAS/{UNIT_DIR}/lawson.model")
    fps_bytes = pack.get(f"Lawson_LAS/{UNIT_DIR}/fps_lawson.model")
    tpp_cfg = pack.get(f"Lawson_LAS/{UNIT_DIR}/lawson.material_config", b"").decode()
    fps_cfg = pack.get(f"Lawson_LAS/{UNIT_DIR}/fps_lawson.material_config", b"").decode()

    with tempfile.TemporaryDirectory() as tmp:
        tpp_path = Path(tmp) / "lawson.model"
        tpp_path.write_bytes(tpp_bytes or b"")
        fps_path = Path(tmp) / "fps_lawson.model"
        fps_path.write_bytes(fps_bytes or b"")
        tpp = model_of(tpp_path)
        fps = model_of(fps_path)

        check_skeleton(rep, tpp, by_hash, _by_id)
        check_finger_binds(rep, tpp, rig)
        check_tangents(rep, tpp)
        check_skinning(rep, tpp, by_hash)
        check_materials(rep, pack, tpp, tpp_cfg, fps=False)
        check_materials(rep, pack, fps, fps_cfg, fps=True)
        check_skinning_keyword(rep, tpp, tpp_cfg, "TPP")
        check_skinning_keyword(rep, fps, fps_cfg, "FPS")
        check_fps(rep, pack, fps, fps_cfg)
        check_textures(rep, pack)
        check_packaging(rep, pack)
        check_notes(rep, pack)

    # the guide's open question the pack cannot settle offline
    rep.warn("G1", "guide: invert the green channel if the source map is "
                   "DirectX-style (PD2 wants OpenGL-style Y+)",
             "the pack's normal maps are built with the green channel inverted "
             "(source assumed DirectX). Only the running game can confirm the "
             "source's convention; rebuild with --keep-nm-green if the lighting "
             "looks inverted in game")
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack", nargs="?", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not args.pack.exists():
        raise SystemExit(f"no such pack: {args.pack} (build it with "
                         f"build_las_pack.py first)")
    rep = audit(args.pack)
    if args.json:
        print(json.dumps(rep.checks, indent=1))
    else:
        print(f"LAS pack compliance vs the ModWorkshop LAS/MOOG guide")
        print(f"pack: {args.pack}\n")
        for c in rep.checks:
            print(f"{c['status']:<4} {c['id']:<3} {c['rule']}")
            print(f"     {c['detail']}\n")
        n = rep.counts()
        print(f"summary: {n[PASS]} pass, {n[WARN]} warn, {n[FAIL]} fail")
    raise SystemExit(1 if any(c["status"] == FAIL for c in rep.checks) else 0)


if __name__ == "__main__":
    main()
