#!/usr/bin/env python3
"""Is a fresh build of the Miranda packs the tracked packs? Member by member.

    make -sC tools/pd2-las fresh

builds both packs again into build/fresh/, which leaves the tracked zips alone,
and then runs this file on the result:

    python tools/pd2-las/fresh_check.py [--fresh build/fresh] [--tracked dist]

Comparing the two zips is the wrong question, because a `.model` is allowed to
differ in two ways. The builder gets its numbers from linear algebra; numpy
hands that to OpenBLAS, and OpenBLAS picks its routines by the CPU it runs on.
Measured on 2026-11-11 by holding OpenBLAS to the routines of other CPUs
(`OPENBLAS_CORETYPE`), the third-person model of each pack comes out 136 to 174
bytes different of about two million, and no other member moves:

* the last bits of a float (one U direction in 9,874 vertices);
* the V direction of a vertex whose triangles all have no area in UV: 44
  vertices of the hair, and the same 44 in the shadow caster. The UV map gives
  such a vertex no handedness, so `build_models` takes the sign of a number
  that is zero but for rounding, and the rounding decides: 16 to 21 of the 44
  came out reversed.

So the rule is:

* a member that is not a model has to be the same bytes;
* a model has to have the same sections of the same sizes; everything in it
  that is not a float has to be the same; its floats have to agree to
  `FLOAT_TOLERANCE`, except that the V direction of such a vertex may be
  reversed;
* `BUILD_INFO.json` records the sha256 of every member, so it may differ in the
  entry of a model that differs in those ways, and nowhere else.

On the kind of CPU the tracked packs were built on nothing differs at all, and
the report says which of the two it found. The exit status is 1 when a member
differs by more than this allows.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import diesel_model as dm  # noqa: E402

#: the tracked packs that `make fresh` builds again
PACKS = ("Miranda_LAS.zip", "Miranda_Busty_LAS.zip")

#: Two floats of a model are the same number when they differ by no more than
#: this, relative to the larger of 1 and the value. Single precision carries
#: seven digits and the measured differences are in the seventh; a vertex that
#: moved by a tenth of a millimetre is a thousand times outside it.
FLOAT_TOLERANCE = 1e-5

#: the sections of a model that hold floats, and how to read them
_DECODERS = {
    dm.OBJECT3D: dm.decode_object3d,
    dm.MODEL_DATA: dm.decode_model_data,
    dm.SKINBONES: dm.decode_skinbones,
    dm.GEOMETRY: dm.decode_geometry,
}


def members(path: Path) -> dict:
    """Member name, without the pack's own folder, -> its bytes."""
    with zipfile.ZipFile(path) as z:
        return {info.filename.split("/", 1)[-1]: z.read(info) for info in z.infolist() if not info.is_dir()}


def _same(a, b) -> bool:
    """Two decoded values: floats within the tolerance, everything else equal."""
    if isinstance(a, float) and isinstance(b, float):
        return a == b or abs(a - b) <= FLOAT_TOLERANCE * max(1.0, abs(a))
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[key], b[key]) for key in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _without_uv_area(sections: list, geometry_id: int, uv: list) -> set:
    """The vertices of a geometry whose triangles all have no area in UV.

    The UV map gives such a vertex no direction (`dm.compute_uv_directions` skips
    the same triangles), so the sign of its V direction is nobody's decision.
    """
    by_id = {section.id: section for section in sections}
    with_area = set()
    for section in sections:
        if section.type != dm.PASSTHROUGH_GP:
            continue
        gp = dm.decode_passthroughgp(section.payload)
        if gp["geometry"] != geometry_id:
            continue
        indices = dm.decode_topology(by_id[gp["topology"]].payload)["indices"]
        for a, b, c in zip(indices[0::3], indices[1::3], indices[2::3]):
            det = (uv[b][0] - uv[a][0]) * (uv[c][1] - uv[a][1]) - (uv[c][0] - uv[a][0]) * (uv[b][1] - uv[a][1])
            if abs(det) > dm.UV_DET_EPS:
                with_area.update((a, b, c))
    return set(range(len(uv))) - with_area


def model_difference(tracked: bytes, fresh: bytes) -> tuple[str, int]:
    """(what makes two models differ by more than the docstring allows, V directions reversed).

    The text is empty when nothing does.
    """
    try:
        old, new = dm.ModelFile.read(tracked).sections, dm.ModelFile.read(fresh).sections
    except Exception as error:                       # a model that does not parse is not a rounding difference
        return f"does not read as a model: {error}", 0
    if [(s.type, s.id, len(s.payload)) for s in old] != [(s.type, s.id, len(s.payload)) for s in new]:
        return "its sections are not the same list", 0
    reversed_v = 0
    for a, b in zip(old, new):
        if a.payload == b.payload:
            continue
        name = f"{dm.TAG_NAMES.get(a.type, hex(a.type))} section {a.id}"
        decode = _DECODERS.get(a.type)
        if decode is None:
            return f"{name} holds no floats and differs", 0
        was, now = decode(a.payload), decode(b.payload)
        if a.type != dm.GEOMETRY:
            if not _same(was, now):
                return f"{name} differs by more than rounding", 0
            continue
        if was.keys() != now.keys():
            return f"{name} has other channels", 0
        free = None
        for key in was:
            if key != "uvdir_v" or len(was[key]) != len(now[key]):
                if not _same(was[key], now[key]):
                    return f"{name}, {key}, differs by more than rounding", 0
                continue
            for vertex, (x, y) in enumerate(zip(was[key], now[key])):
                if _same(x, y):
                    continue
                if free is None:
                    free = _without_uv_area(old, a.id, was["uv0"])
                if vertex not in free or not _same(x, tuple(-value for value in y)):
                    return f"{name}, V direction of vertex {vertex}, differs by more than rounding", 0
                reversed_v += 1
    return "", reversed_v


def compare(tracked: Path, fresh: Path) -> dict:
    """{"members": count, "same": count, "rounding": [text], "different": [text]} for one pack."""
    old, new = members(tracked), members(fresh)
    out = {"members": len(old), "same": 0, "rounding": [], "different": []}
    for name in sorted(set(old) - set(new)):
        out["different"].append(f"{name}: not in the fresh build")
    for name in sorted(set(new) - set(old)):
        out["different"].append(f"{name}: not in the tracked pack")
    rounded = set()
    for name in sorted(set(old) & set(new)):
        if name == "BUILD_INFO.json":
            continue
        a, b = old[name], new[name]
        if a == b:
            out["same"] += 1
            continue
        moved = sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
        why, reversed_v = model_difference(a, b) if name.endswith(".model") else ("has to be the same bytes", 0)
        if why:
            out["different"].append(f"{name}: {moved:,} bytes differ of {len(a):,}; {why}")
        else:
            rounded.add(name)
            out["rounding"].append(
                f"{name}: {moved:,} bytes differ of {len(a):,}: the last bits of floats"
                + (f", and {reversed_v} V directions reversed where the UV map gives none" if reversed_v else ""))
    if "BUILD_INFO.json" in old and "BUILD_INFO.json" in new:
        a, b = json.loads(old["BUILD_INFO.json"]), json.loads(new["BUILD_INFO.json"])
        if a == b:
            out["same"] += 1
        else:
            for info in (a, b):                      # the hashes of the models that differ by rounding
                info["payload_sha256"] = {key: value for key, value in info.get("payload_sha256", {}).items()
                                          if key not in rounded}
            if a == b:
                out["rounding"].append("BUILD_INFO.json: the sha256 it records for the above")
            else:
                keys = sorted(key for key in set(a) | set(b) if a.get(key) != b.get(key))
                out["different"].append(f"BUILD_INFO.json: differs in {', '.join(keys)}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fresh", type=Path, default=REPO / "build" / "fresh", help="where the fresh builds are")
    ap.add_argument("--tracked", type=Path, default=REPO / "dist", help="where the tracked packs are")
    args = ap.parse_args(argv)
    status = 0
    for pack in PACKS:
        if not (args.fresh / pack).is_file():
            print(f"{pack}: no fresh build in {args.fresh}; run `make -sC tools/pd2-las fresh`")
            status = 1
            continue
        result = compare(args.tracked / pack, args.fresh / pack)
        if result["same"] == result["members"] and not result["different"]:
            print(f"{pack}: all {result['members']} members are the same bytes as the tracked pack")
        else:
            print(f"{pack}: {result['same']} of {result['members']} members are the same bytes as the tracked pack")
        for line in result["rounding"]:
            print(f"  as allowed      {line}")
        for line in result["different"]:
            print(f"  DIFFERENT       {line}")
        status |= bool(result["different"])
    return status


if __name__ == "__main__":
    raise SystemExit(main())
