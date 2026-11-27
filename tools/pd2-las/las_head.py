"""A second character's head drawable, re-skinned onto the 2B skeleton.

`OfficeSuite_Head_LAS` is a whole-character LAS pack: the OfficeSuite body plus a
head, so the skin ships a complete character instead of borrowing the heister's.

The head donor is the native Hila override's unit, whose `g_head` is the Miranda
Romance head: 4,454 vertices in two atoms, the face on `mtr_head` and the lashes
on `mtr_lashes`. It was authored against Hila's skeleton, so its skin palette
names Hila's section ids; the 2B template has no such ids. Every check this
module makes is therefore by bone *rest position*, never by section id, and the
resolved 2B bone names are recorded so a different donor fails loudly instead of
producing a head welded to the wrong bone.

The donor's four palette bones sit on Hips, Spine2, Neck and Head. The first
three contribute one vertex each (the head's neck plug); the rest ride `Head`.
On the 2B rig those four rest positions agree with the donor's to 0.01 cm, so the
weights transfer unchanged and only the palette is rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import build_models as bm
import diesel_model as dm

#: donor palette bone -> 2B bone, resolved by rest position and checked below.
HEAD_BONES = ("Hips", "Spine2", "Neck", "Head")

#: The donor's four bones must land this close to a 2B bone's rest position.
MATCH_CM = 0.05

#: Name of the drawable in the donor unit and in the built unit.
DRAWABLE = "g_head"

#: Source material names, in the order the donor's atoms use them.
SLOTS = ("head", "lashes")


@dataclass
class Head:
    """Everything the pack builder needs to add the head to the 2B unit."""

    group: bm.Group
    slots: tuple[str, ...]              # out material names, one per atom
    textures: dict[str, bytes] = field(default_factory=dict)  # "<slot>_df.texture" -> data
    report: dict = field(default_factory=dict)


def _drawable(model: dm.ModelFile, name: str) -> tuple[dm.Section, dict, dict, dict, dict, dict]:
    """The one v3 MODEL_DATA called `name`, with its decoded mesh blocks."""
    sid = dm.hash64(name)
    matches = [(s, d) for s in model.by_type(dm.MODEL_DATA)
               if (d := dm.decode_model_data(s.payload))["name_hash"] == sid and d["version"] == 3]
    if len(matches) != 1:
        raise ValueError(f"expected one drawable named {name}, found {len(matches)}")
    section, data = matches[0]
    gp = dm.decode_passthroughgp(model.by_id(data["passthroughgp"]).payload)
    geo = dm.decode_geometry(model.by_id(gp["geometry"]).payload)
    top = dm.decode_topology(model.by_id(gp["topology"]).payload)
    bind = dm.decode_skinbones(model.by_id(data["skinbones"]).payload)
    return section, data, geo, top, bind, gp


def load(donor_zip: Path, template: bm.Template, slot_prefix: str,
         unit: str) -> tuple[Head, dm.ModelFile]:
    """Read the donor unit out of its ZIP: the head group and the model it came from.

    `unit` is the donor's unit path inside the ZIP (no `.model`), the same path
    the native Hila override installs, so the donor is the shipped override and
    not a copy of it.
    """
    import xml.etree.ElementTree as ET
    from zipfile import ZipFile

    with ZipFile(Path(donor_zip)) as z:
        prefix = z.namelist()[0].split("/")[0] + "/"
        model = dm.ModelFile.read(z.read(f"{prefix}{unit}.model"))
        config = ET.fromstring(z.read(f"{prefix}{unit.rsplit('/', 1)[0]}/mtr_criminal_ecp_female"
                                      ".material_config"))
        head = read(model, template, slot_prefix, Path(donor_zip).name)
        # The donor's own maps, under the pack's slot names. The face and lashes
        # are DXT5 with full mips already, so no re-encode.
        names = {m.get("name"): m for m in config.findall("material")}
        face, lashes = names["mtr_head"], names["mtr_lashes"]
        out = {}
        for element, slot, suffix in ((face, head.slots[0], "_df"), (face, head.slots[0], "_nm"),
                                      (lashes, head.slots[1], "")):
            stem = element.find("diffuse_texture" if suffix != "_nm" else "bump_normal_texture").get("file")
            data = z.read(prefix + stem + ".texture")
            out[f"{slot}{suffix}.texture"] = data
            head.report.setdefault("textures", {})[f"{slot}{suffix}"] = {
                "source": stem + ".texture", "bytes": len(data),
                "sha256": __import__("hashlib").sha256(data).hexdigest(),
            }
        head.textures.update(out)
    return head, model


def read(donor: dm.ModelFile, template: bm.Template, slot_prefix: str,
         donor_name: str = "(in memory)") -> Head:
    """Re-skin the donor's head drawable onto `template` as one group.

    `slot_prefix` is the LAS item id: the out materials are `<prefix>_head` and
    `<prefix>_lashes`, so two packs built from this donor cannot collide.
    `donor_name` is what the report says the head came from — the ZIP's name when it
    came from one, so two interchangeable donors cannot produce the same report.
    """
    section, data, geo, top, bind, _gp = _drawable(donor, DRAWABLE)
    faces = np.asarray(top["indices"], dtype=np.int64).reshape(-1, 3)
    verts = np.asarray(geo["verts"], dtype=np.float64)
    normals = np.asarray(geo["normals"], dtype=np.float64)
    uv0 = np.asarray(geo["uv0"], dtype=np.float64)

    # -- palette: donor bone -> 2B bone, by rest position only ----------------
    donor_objs, donor_worlds = bm._resolve_worlds(donor)
    target = {name: np.asarray(template.worlds[template.name_id[name]][12:15]) for name in HEAD_BONES}
    lookup: dict[int, int] = {}
    resolved = {}
    for bone in bind["objects"]:
        pos = np.asarray(donor_worlds[bone][12:15])
        name, dist = min(((n, float(np.linalg.norm(p - pos))) for n, p in target.items()),
                         key=lambda t: t[1])
        if dist > MATCH_CM:
            raise ValueError(f"donor bone {bone:#x} at {pos.round(2)} is {dist:.2f} cm from any "
                             f"2B head-chain bone; this donor needs another fit")
        # Two donor bones may not share one 2B bone unless they are the same bone.
        if name in resolved.values():
            raise ValueError(f"two donor bones resolve to 2B {name}")
        lookup[bone] = name
        resolved[bone] = name
    if sorted(resolved.values()) != sorted(HEAD_BONES):
        raise ValueError(f"expected the head on {HEAD_BONES}, got {sorted(resolved.values())}")

    # -- weights: keep the donor's, with the palette re-indexed --------------
    blend_ids = np.asarray(geo["blendindices"])[:, :3]
    blend_w = np.asarray(geo["blendweights"], dtype=np.float64)[:, :3]
    palette = [resolved[b] for b in bind["objects"]]
    # `Group.weights` indexes the group's own palette, so each donor influence
    # becomes that palette's slot. Sorting by weight keeps the strongest first,
    # where the pack's three-weight geometry keeps it.
    weights = []
    for idx_row, w_row in zip(blend_ids, blend_w):
        influences = [(palette[int(i)], float(w)) for i, w in zip(idx_row, w_row) if w > 0]
        total = sum(w for _, w in influences) or 1.0
        keep = sorted(influences, key=lambda iw: (-iw[1], iw[0]))[:3]
        weights.append([(HEAD_BONES.index(name), w / total) for name, w in keep])

    # -- the group ----------------------------------------------------------
    group = bm.Group(name=DRAWABLE, verts=[tuple(v) for v in verts],
                     normals=[tuple(n) for n in normals],
                     uvs=[tuple(t) for t in uv0],
                     faces=[tuple(int(i) for i in f) for f in faces],
                     palette=list(HEAD_BONES))
    mats = [dm.decode_material(donor.by_id(i).payload)["name_hash"]
            for i in dm.decode_material_group(donor.by_id(data["matgroup"]).payload)["material_ids"]]
    if len(mats) != len(SLOTS):
        raise ValueError(f"expected {len(SLOTS)} head materials, got {len(mats)}")
    # Group weights are per-vertex palette indices, not per-atom: `weights`
    # keeps the full palette so an atom boundary cannot shift an influence.
    group.weights = []
    for w_row in weights:
        group.weights.append(w_row)
    group.mat_slots = [f"{slot_prefix}_{m}" for m in _donor_slot_names(donor, mats)]
    for atom, slot in zip(data["atoms"], group.mat_slots):
        start = atom["base_vertex"]
        group.slices.append((slot, start, atom["base_index"], atom["tri_count"], atom["slice_len"]))

    report = {
        "donor": donor_name,
        "drawable": DRAWABLE,
        "verts": int(len(verts)),
        "tris": int(len(faces)),
        "atoms": len(data["atoms"]),
        "bones": {f"{bone:#x}": name for bone, name in resolved.items()},
        "weights": "influences %d..%d per vertex" % (int((blend_w > 0).sum(1).min()),
                                                     int((blend_w > 0).sum(1).max())),
    }
    return Head(group=group, slots=tuple(group.mat_slots), report=report)


#: The donor's material names, keyed by name hash, for the two atoms.
def _donor_slot_names(donor: dm.ModelFile, hashes: list[int]) -> list[str]:
    names = {}
    for name in ("mtr_head", "mtr_lashes"):
        names[dm.hash64(name)] = name.removeprefix("mtr_")
    try:
        return [names[h] for h in hashes]
    except KeyError as error:
        raise ValueError(f"unexpected head material {error.args[0]:#x}") from error
