#!/usr/bin/env python3
"""Recover PD2 bone names for the rig contract's hash-only bones.

The LAS rig contract (``reference/las_rig.json``) was extracted from the 2B
reference model, whose finger bones carry only a name *hash* (the Model Tool
writes names when the PAYDAY-2-Hashlist is installed). The hash is the
lookup3 variant in ``dmodel.hash64``, so the names can be recovered offline:
hash the PD2 naming convention's candidates and keep the ones that match a
bone's stored hash. The stored hash is never modified - only the human
readable ``name`` field is filled in.

Usage:
    python tools/pd2-port/resolve_rig_names.py            # report
    python tools/pd2-port/resolve_rig_names.py --apply    # patch the contract
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dmodel import hash_str  # noqa: E402

RIG_JSON = HERE / "reference" / "las_rig.json"

# PD2's hand bones: five fingers, three bones each, per hand.
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")


def candidates() -> list[str]:
    out = []
    for side in ("Left", "Right"):
        for finger in FINGERS:
            for n in (1, 2, 3):
                out.append(f"{side}Hand{finger}{n}")
    return out


def resolve(rig: dict) -> dict[int, str]:
    """bone id -> name, for every hash-only bone a candidate matches."""
    by_hash = {hash_str(c): c for c in candidates()}
    found: dict[int, str] = {}
    for b in rig["bones"]:
        h = int(b["name_hash"], 16)
        if b.get("name"):
            continue
        name = by_hash.get(h)
        if name:
            found[b["id"]] = name
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the recovered names into the rig contract")
    args = ap.parse_args()
    rig = json.loads(RIG_JSON.read_text())
    found = resolve(rig)
    for bone_id, name in sorted(found.items()):
        print(f"  id {bone_id:>3}  {name}")
    print(f"{len(found)} of {sum(1 for b in rig['bones'] if not b.get('name'))} "
          f"hash-only bones named")
    if not args.apply:
        print("(dry run - pass --apply to write)")
        return
    for b in rig["bones"]:
        if b["id"] in found:
            b["name"] = found[b["id"]]
    # the contract is stored without a trailing newline: keep the diff to the
    # names that actually changed
    RIG_JSON.write_text(json.dumps(rig, indent=1))
    print(f"wrote {RIG_JSON}")


if __name__ == "__main__":
    main()
