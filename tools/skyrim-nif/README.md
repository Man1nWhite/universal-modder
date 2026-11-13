# skyrim-nif — read a Skyrim SE outfit, and see what a port would cost

Dependency-free (numpy + Pillow) readers for Skyrim Special Edition `.nif`
meshes, plus the inventory and preview tooling that measures what a port would
cost. The outfit this was written against was cancelled and its sources removed;
see [`docs/skyrim-nif/STATUS.md`](../../docs/skyrim-nif/STATUS.md).

Nothing here *ports* anything yet: it decodes the source, proves it is readable,
and measures the facts a port decision needs (geometry, skinning, materials,
texture coverage, rig fit against a target skeleton).

The reader is **byte-exact against nifly** (the C++ library behind Outfit Studio)
on every mesh in `4.zip` — 91/91 checks, vertex and UV deltas `0.0`. See
[`docs/skyrim-nif/TOOLING.md`](../../docs/skyrim-nif/TOOLING.md) for why we run
nifly through a small ctypes bridge instead of PyNifly/PyFFI/SkyMeshGLTF, and
[`docs/skyrim-nif/CROSSCHECK.md`](../../docs/skyrim-nif/CROSSCHECK.md) for the
table itself.

## Use

```bash
# once, for a venv with pillow/numpy
make -sC tools/pd2-las env           # or: python3 -m venv .venv && .venv/bin/pip install pillow numpy

# full inventory: JSON + Markdown + tracked previews
.venv/bin/python tools/skyrim-nif/inventory.py \
    --json build/skyrim-nif/source_inventory.json \
    --markdown build/skyrim-nif/REPORT.md \
    --previews docs/previews

# cross-check the reader against nifly (optional; builds a ~4 MB .so in ~90 s)
bash tools/skyrim-nif/build_nifly.sh
.venv/bin/python tools/skyrim-nif/crosscheck.py \
    --markdown docs/skyrim-nif/CROSSCHECK.md

# one file, ad hoc
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "tools/skyrim-nif")
import nif
f = nif.parse(open("meshes.nif", "rb").read(), "meshes.nif")
print(f.shade(), [(s.name, s.num_vertices, s.num_triangles) for s in f.shapes])
PY
```

## What the reader handles

* NIF 20.2.0.7 (Skyrim SE / user 12 / stream 100). LE files are rejected on
  purpose rather than half-parsed.
* The header block table, so blocks we do not model (`NiSkinData`, collision,
  extra data) are skipped by declared size instead of breaking the parse.
* `NiNode`/`BSFadeNode` hierarchy with `MatTransform` (translation, 3×3 rotation
  matrix, scale) and world-matrix composition.
* `BSTriShape` and — the part that matters for SSE — geometry that lives in
  `NiSkinPartition` instead of the shape (`dataSize == 0`). Vertex flags are read
  from bits 44-59 of the descriptor, half-float UVs and weights, packed byte
  normals, triangles as `uint16` triples.
* Skinning: `BSDismemberSkinInstance` → bone refs resolved to node names, plus the
  dismember `partID` per partition. Per-vertex weights are kept, so
  `shape.bone_weights()` gives "which bone drives how much of this mesh".
* Legacy geometry: `NiTriShape` + `NiTriShapeData` (separate data block). The
  `_g` ground/collision NIFs are built this way, not with `BSTriShape`.
* Materials: `BSLightingShaderProperty` (SSE layout: the shader type lives in
  NiObjectNET *before* the name, the two fixed flag words follow the name) →
  `BSShaderTextureSet` (9 paths), `NiAlphaProperty` flags/threshold.

Known gaps, all deliberate: `NiSkinData` bodies are skipped (the partition copy is
authoritative and identical), tangent space is read but discarded, and the
`bhk*` collision blocks inside the `_g` NIFs are skipped by declared size — we
want their meshes' bounds, not their physics.

## Verified against

All 12 meshes in `4.zip` parse with a single warning class (the skipped
`NiSkinData` blocks). Independent sanity checks that would catch a mis-parse:

| check | expected | got |
| --- | --- | --- |
| vertex weights per vertex | sum to 1.0 | 1.000 mean on every shape |
| triangle indices | < vertex count | in range |
| skinned body height | ~163 cm | `3BA` shape 16 → 163 cm |
| garment placement | skirt around the hips | `0_Skirt` 86.6 → 117.7 cm |
| UV range | inside 0…1 | 0.01…0.99 on the 2048² atlases |
| four-view render | an actual outfit | a four-view render of the source meshes |
| **nifly, shape by shape** | identical shapes, verts, tris, bones, textures | **91/91 checks, deltas `0.0`** |

Units: one NIF unit = 1.428 cm; an adult NPC is ~128 units tall.

## Files

| file | role |
| --- | --- |
| `nif.py` | the reader (`NifFile`, `Node`, `Shape`, `parse()`) |
| `preview.py` | `.dds` contact sheets + z-buffered four-view mesh renders |
| `inventory.py` | the report: archives, meshes, textures, colourways, rights |
| `skeleton_map.json` | XPMSE/3BA → PAYDAY 2 LAS bone map (15 mapped joints, 22 helper folds, 10 dropped 3BA bones) |
| `nifly_wrap.cpp` | C ABI over `ousnius/nifly` (open, shapes, geometry, skin, materials, nodes) |
| `nifly_bridge.py` | ctypes loader + `NiflyFile`; honours `NIFLY_WRAP`, defaults to `build/libniflywrap.so` |
| `build_nifly.sh` | clones nifly into `build/nifly-src` and compiles the wrapper (~90 s, g++ only, no cmake) |
| `crosscheck.py` | feeds every NIF in `4.zip` to both readers and reports disagreements |
