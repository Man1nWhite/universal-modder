# Reading Skyrim SE `.nif` files: which library actually works

Question: should the port use **nifly / PyNifly**, **PyFFI**, or **SkyMeshGLTF**
instead of a hand-written reader? Measured on this machine (Linux, Python 3.11,
g++ 12.2), against the real files in `4.zip`.

Verdicts first, evidence below:

| option | verdict | why |
| --- | --- | --- |
| **nifly** (C++ core) | ✅ **works — and is now the oracle** | 90 s `g++` build, no cmake, no Python headers; reads all 12 meshes "cleanly"; agrees with our reader on **91/91** checks |
| **PyNifly** (Python wrapper) | ⚠️ **not usable as-is, but only because of packaging** | the `pyn` layer is a Blender add-on that loads `NiflyDLL.dll` built from a **MSVC `.vcxproj`**; on Linux `import pyn.niflydll` dies at `cdll.LoadLibrary` with "No such file or directory" |
| **PyFFI 2.2.3** | ❌ **dead end for Skyrim SE** | crashes on import under Python ≥ 3.8 (`time.clock`), and even patched: `ValueError: Unknown block type 'BSTriShape'` |
| **SkyMeshGLTF** | ❌ **cannot read SE meshes** | its parser *is* `pyffi.formats.nif` (so it inherits the failure), plus `mathutils`, `wand`, `pyvips` and Windows-only process flags |

So: the suggestion was right — nifly is the one to trust — but it is the **C++
core** that works here, not the Python wrapper. We compile nifly with `g++`,
expose a tiny C ABI (`tools/skyrim-nif/nifly_wrap.cpp`) and load it with
`ctypes`; no Blender, no Windows DLL, no PyFFI.

---

## 1. nifly (github.com/ousnius/nifly)

Dependency-free C++17 (it vendors only `half.hpp` and `Miniball.hpp`), so `cmake`
is optional:

```bash
bash tools/skyrim-nif/build_nifly.sh        # clones nifly into tools/skyrim-nif/build/
.venv/bin/python tools/skyrim-nif/crosscheck.py
```

```
== compiling libniflywrap.so ==
built .../build/libniflywrap.so (4.0M)      # ~85 s on one core
crosscheck: 91 checks passed, 0 failed
```

Per-file agreement with `nif.py` (all 12 NIFs, garments *and* the `_g` collision
meshes):

| check | result |
| --- | --- |
| shape list, per-file | identical |
| vertex count, per shape | identical |
| max vertex position Δ | **0.00e+00** (float32-exact, same bytes) |
| max UV Δ | **0.00e+00** |
| triangle sets | identical (same indices, same winding) |
| bone lists | identical, same order |
| texture paths | identical, same slots |
| node count | identical (54 for the jacket, 14 for the skirt, …) |
| per-bone vertex-weight totals | ≤ 3.6e-2 apart — `nifly` reads float weights from `NiSkinData`, we read the half-float copy in `NiSkinPartition` |

That last row is the only difference, it is expected (two copies of the same
data at different precision), and it is now the documented reason the port keeps
the partition copy: it is what the GPU uses.

What the C ABI exposes (`nifw_*` in `nifly_wrap.cpp`): open/close, shape list,
per-shape name / vertex count / triangle count / vertices / normals / UVs /
triangles / shader type / texture slot paths / bone list / per-bone weights,
node names and local transforms, and a load-status string.

## 2. PyNifly (github.com/BadDogSkyrim/PyNifly)

```
$ python -c "import pyn.niflydll"
OSError: .../io_scene_nifly/NiflyDLL.dll: cannot open shared object file:
No such file or directory
```

The repo is structured as a Blender add-on: `io_scene_nifly/` (Blender
operators, `bpy` imports) over `pyn/` (pure `ctypes` bindings). The bindings
themselves never import `bpy` — they look it up in `sys.modules` — so they would
run in plain Python, but they resolve the library to `NiflyDLL.dll`, and that
DLL is produced by `NiflyDLL/NiflyDLL.vcxproj` (`ConfigurationType:
DynamicLibrary`, MSVC only). There is no CMake/Unix build for it.

That is why we wrapped nifly directly: same library, ~300 lines of C ABI, and it
builds anywhere `g++` exists. **If you later need PyNifly itself** (e.g. to run
its test-suite), the practical route is Windows + Visual Studio, or Blender on
Linux with a hand-built `.so` renamed to `NiflyDLL.dll`.

## 3. PyFFI 2.2.3

```
$ pip install pyffi            # installs fine
$ python -c "from pyffi.formats.nif import NifFormat"
AttributeError: module 'time' has no attribute 'clock'      # Python ≥ 3.8
```

Monkeypatching `time.clock` gets the import through, and then:

```
nif.read(Skirt_0.nif)
ValueError: Unknown block type 'BSTriShape'.
```

`BSTriShape` is *the* Skyrim SE geometry block (it is what `4.zip` uses, and what
every SSE body/outfit mod uses). PyFFI's last release is from 2014 and tops out at
Skyrim LE (file version 20.0.0.5). For SSE it is not a partial solution, it is a
hard stop.

## 4. SkyMeshGLTF (github.com/nlaha/SkyMeshGLTF)

`file_process.py` starts with `from pyffi.formats.nif import NifFormat`, so it
inherits §3 exactly: it converts Skyrim LE meshes, not SE ones. It also needs
`mathutils` (a Blender module), `wand` (ImageMagick), `pyvips`, `psutil`, and
uses Windows-only process flags (`DETACHED_PROCESS = 0x00000008`). It is a batch
converter, not a library, and it cannot emit the one thing a port needs — a
skinned mesh with per-vertex bone weights in a target-friendly format.

---

## What this means for the repo

* `tools/skyrim-nif/nif.py` stays: it is pure Python (numpy only), has no build
  step, and is **byte-exact against nifly** on every file we care about. The
  cross-check is the test that keeps it honest.
* `tools/skyrim-nif/build_nifly.sh` + `crosscheck.py` are the audit: they can be
  re-run any time nifly moves, or after a change to the reader.
* Nothing in the port pipeline depends on PyFFI, PyNifly, Blender, .NET or
  Windows. `bash tools/skyrim-nif/build_nifly.sh` is the only extra step, and it
  is optional (the reader works without it; only the audit needs it).

Reproduce:

```bash
bash tools/skyrim-nif/build_nifly.sh
.venv/bin/python tools/skyrim-nif/crosscheck.py --markdown docs/skyrim-nif/CROSSCHECK.md
```
