#!/usr/bin/env python3
"""Run a builder with a checkpoint trace.

    python tools/pd2-las/trace_run.py --out TRACE.log tools/pd2-las/build_models.py [its arguments]

Every function of this repository (anything under tools/) leaves a checksum of
what it was given and of what it returned. Two runs of one builder, on two
machines or under two numeric code paths, can then be compared line by line:
the first line that differs names the function where they parted
(`fresh.py matrix --trace` does the comparing).

A builder started the usual way is not traced and pays nothing for this.

Each checksum comes in two halves. The first covers everything. The second
leaves out float64 values (arrays, Python floats): between CPUs those differ in
their last bits as a matter of course. What is left in the second half has been
rounded or decided: uint8 and float32 arrays, bytes, integers, masks, strings.
A difference there is a difference that can reach a file.

Lines:  C name#n all exact seq caller   the arguments of the n-th call (first 40 calls)
        R name#n all exact seq          what it returned               (first 40 calls)
        S name calls all exact first    every return value of the function, chained
"""
from __future__ import annotations

import hashlib
import os
import runpy
import struct
import sys
from pathlib import Path, PurePath

FIRST = 40              # calls of one function that get a line each
BUDGET = 256 << 20      # bytes of return values checksummed per function


def _pair():
    return hashlib.blake2b(digest_size=8), hashlib.blake2b(digest_size=8)


class Trace:
    def __init__(self, out: str, root: Path):
        self.out = open(out, "w", encoding="utf-8")
        self.root = str(root)
        self.tools = str(root / "tools") + os.sep
        self.names: dict = {}     # code object -> name, or None when the code is not this repository's
        self.stats: dict = {}     # name -> [calls, bytes, all, exact, first]
        self.live: dict = {}      # frame -> which call of its function it is
        self.ours: dict = {}      # type -> whether its instances are walked
        self.seq = 0

    # ------------------------------------------------------------ checksums

    def feed(self, obj, pair, depth: int = 0) -> int:
        """Add `obj` to both checksums, or to the first only where it is float64. Returns the bytes fed."""
        whole, exact = pair
        if obj is None or isinstance(obj, (bool, int)):
            data = repr(obj).encode()
        elif isinstance(obj, float):
            whole.update(struct.pack("<d", obj))
            return 8
        elif isinstance(obj, str):
            data = obj.replace(self.root, "<root>").encode("utf-8", "replace")
        elif isinstance(obj, (bytes, bytearray)):
            data = bytes(obj)
        elif isinstance(obj, PurePath):
            data = str(obj).replace(self.root, "<root>").encode("utf-8", "replace")
        else:
            return self._feed_other(obj, pair, depth)
        whole.update(data)
        exact.update(data)
        return len(data)

    def _feed_other(self, obj, pair, depth: int) -> int:
        whole, exact = pair
        np = sys.modules.get("numpy")       # never imported here: the builder decides when numpy loads
        if np is not None:
            if isinstance(obj, np.generic):
                obj = np.asarray(obj)
            if isinstance(obj, np.ndarray):
                if obj.dtype.hasobject:
                    return 0
                head = f"{obj.dtype.str}{obj.shape}".encode()
                data = np.ascontiguousarray(obj).tobytes()
                whole.update(head)
                whole.update(data)
                if not (obj.dtype.kind in "fc" and obj.dtype.itemsize >= 8):
                    exact.update(head)
                    exact.update(data)
                return len(data)
        if hasattr(obj, "mode") and hasattr(obj, "size") and hasattr(obj, "tobytes"):     # a Pillow image
            try:
                data = obj.tobytes()
            except Exception:
                return 0
            head = f"{obj.mode}{obj.size}".encode()
            for half in pair:
                half.update(head)
                half.update(data)
            return len(data)
        if depth >= 5:
            return 0
        if isinstance(obj, (list, tuple)):
            if len(obj) > 16 and np is not None:
                try:
                    array = np.asarray(obj)
                except Exception:
                    array = None
                if array is not None and array.dtype.kind in "biuf":
                    return self._feed_other(array, pair, depth)
            return sum(self.feed(item, pair, depth + 1) for item in obj)
        if isinstance(obj, dict):
            return sum(self.feed(key, pair, depth + 1) + self.feed(value, pair, depth + 1)
                       for key, value in obj.items())
        if isinstance(obj, (set, frozenset)):
            return self.feed(sorted(repr(item) for item in obj), pair, depth + 1)
        kind = type(obj)
        walk = self.ours.get(kind)
        if walk is None:
            module = sys.modules.get(getattr(kind, "__module__", "") or "")
            walk = self.ours[kind] = str(getattr(module, "__file__", "") or "").startswith(self.tools)
        if not walk or not hasattr(obj, "__dict__"):
            return 0
        return sum(self.feed(key, pair, depth + 1) + self.feed(vars(obj)[key], pair, depth + 1)
                   for key in sorted(vars(obj)))

    # --------------------------------------------------------------- events

    def name(self, code):
        try:
            return self.names[code]
        except KeyError:
            file = code.co_filename
            name = None
            if file.startswith(self.tools) and not code.co_name.startswith("<") and not file.endswith("trace_run.py"):
                name = f"{Path(file).stem}.{getattr(code, 'co_qualname', code.co_name)}"
            self.names[code] = name
            return name

    def on_call(self, frame, event, arg):
        if event != "call":
            return None
        name = self.name(frame.f_code)
        if name is None:
            return None
        stat = self.stats.get(name)
        if stat is None:
            stat = self.stats[name] = [0, 0, *_pair(), self.seq + 1]
        stat[0] += 1
        index = stat[0]
        self.live[frame] = index
        frame.f_trace_lines = False
        if index <= FIRST:
            code = frame.f_code
            count = code.co_argcount + code.co_kwonlyargcount + bool(code.co_flags & 0x04) + bool(code.co_flags & 0x08)
            pair = _pair()
            values = frame.f_locals
            for variable in code.co_varnames[:count]:
                if variable in values:
                    self.feed(values[variable], pair)
            caller = frame.f_back
            where = f"{Path(caller.f_code.co_filename).stem}:{caller.f_lineno}" if caller is not None else "-"
            self.seq += 1
            self.out.write(f"C {name}#{index} {pair[0].hexdigest()} {pair[1].hexdigest()} {self.seq} {where}\n")
        return self.on_return

    def on_return(self, frame, event, arg):
        if event != "return":
            return self.on_return
        index = self.live.pop(frame, None)
        if index is None:
            return None
        name = self.names[frame.f_code]
        stat = self.stats[name]
        if index <= FIRST or stat[1] < BUDGET:
            pair = _pair()
            stat[1] += self.feed(arg, pair)
            stat[2].update(pair[0].digest())
            stat[3].update(pair[1].digest())
            if index <= FIRST:
                self.seq += 1
                self.out.write(f"R {name}#{index} {pair[0].hexdigest()} {pair[1].hexdigest()} {self.seq}\n")
        return None

    def finish(self) -> None:
        for name, (calls, size, whole, exact, first) in sorted(self.stats.items(), key=lambda item: item[1][4]):
            self.out.write(f"S {name} {calls} {whole.hexdigest()} {exact.hexdigest()} {first} {size}\n")
        self.out.close()


def main() -> None:
    argv = sys.argv[1:]
    if len(argv) < 3 or argv[0] != "--out":
        raise SystemExit(__doc__)
    out, script = argv[1], str(Path(argv[2]).resolve())
    trace = Trace(out, Path.cwd().resolve())
    sys.argv = [script] + argv[3:]
    sys.path[0] = str(Path(script).parent)
    sys.settrace(trace.on_call)
    try:
        runpy.run_path(script, run_name="__main__")
    finally:
        sys.settrace(None)
        trace.finish()


if __name__ == "__main__":
    main()
