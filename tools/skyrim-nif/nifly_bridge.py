"""ctypes bridge to ousnius/nifly (via `nifly_wrap.cpp`) — the cross-check oracle.

nifly is the C++ NIF library that Outfit Studio and PyNifly use. `nifly_wrap.cpp`
exposes a small C ABI over it; this module loads the resulting shared library and
turns a NIF into plain Python data, so the pure-Python reader in `nif.py` can be
validated against the reference implementation instead of taken on faith.

Building (Linux, ~90 s, no cmake needed):

    bash tools/skyrim-nif/build_nifly.sh          # clones nifly into build/, compiles
    .venv/bin/python tools/skyrim-nif/crosscheck.py

The library path can be overridden with `NIFLY_WRAP=/path/to/libniflywrap.so`.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import POINTER, c_char, c_char_p, c_float, c_int, c_uint, c_void_p
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_LIB = HERE / "build" / "libniflywrap.so"
LIB_ENV = "NIFLY_WRAP"

TEXTURE_STRIDE = 512
NUM_TEXTURES = 9


class NiflyUnavailable(RuntimeError):
    pass


def library_path() -> Path:
    env = os.environ.get(LIB_ENV)
    if env:
        return Path(env)
    return DEFAULT_LIB


def load(path: Path | None = None) -> ctypes.CDLL:
    path = Path(path) if path else library_path()
    if not path.exists():
        raise NiflyUnavailable(
            f"{path} not found — run `bash tools/skyrim-nif/build_nifly.sh` first "
            f"(or point {LIB_ENV} at a built libniflywrap.so)"
        )
    lib = ctypes.CDLL(str(path))

    lib.nifw_open.restype = c_void_p
    lib.nifw_open.argtypes = [c_char_p]
    lib.nifw_close.restype = None
    lib.nifw_close.argtypes = [c_void_p]
    lib.nifw_error.restype = c_char_p
    lib.nifw_error.argtypes = [c_void_p]
    for name in ("nifw_shape_count", "nifw_node_count"):
        getattr(lib, name).restype = c_int
        getattr(lib, name).argtypes = [c_void_p]
    lib.nifw_shape_name.restype = c_char_p
    lib.nifw_shape_name.argtypes = [c_void_p, c_int]
    for name in ("nifw_shape_num_vertices", "nifw_shape_num_triangles",
                 "nifw_shape_num_bones", "nifw_shape_shader_type",
                 "nifw_shape_has_uvs"):
        getattr(lib, name).restype = c_int
        getattr(lib, name).argtypes = [c_void_p, c_int]
    for name in ("nifw_shape_vertices", "nifw_shape_normals"):
        getattr(lib, name).restype = c_int
        getattr(lib, name).argtypes = [c_void_p, c_int, POINTER(c_float)]
    lib.nifw_shape_uvs.restype = c_int
    lib.nifw_shape_uvs.argtypes = [c_void_p, c_int, POINTER(c_float)]
    lib.nifw_shape_triangles.restype = c_int
    lib.nifw_shape_triangles.argtypes = [c_void_p, c_int, POINTER(c_uint)]
    lib.nifw_shape_bone_name.restype = c_char_p
    lib.nifw_shape_bone_name.argtypes = [c_void_p, c_int, c_int]
    lib.nifw_shape_textures.restype = c_int
    lib.nifw_shape_textures.argtypes = [c_void_p, c_int, POINTER(c_char), c_int, c_int]
    lib.nifw_shape_num_weights.restype = c_int
    lib.nifw_shape_num_weights.argtypes = [c_void_p, c_int, c_int]
    lib.nifw_shape_weights.restype = c_int
    lib.nifw_shape_weights.argtypes = [c_void_p, c_int, c_int, POINTER(c_uint),
                                       POINTER(c_float)]
    lib.nifw_node_name.restype = c_char_p
    lib.nifw_node_name.argtypes = [c_void_p, c_int]
    lib.nifw_node_transform.restype = c_int
    lib.nifw_node_transform.argtypes = [c_void_p, c_int, POINTER(c_float)]
    lib.nifw_warnings.restype = c_int
    lib.nifw_warnings.argtypes = [c_void_p, POINTER(c_char), c_int, c_int]
    return lib


_cache: ctypes.CDLL | None = None


def _lib() -> ctypes.CDLL:
    global _cache
    if _cache is None:
        _cache = load()
    return _cache


class NiflyFile:
    """One NIF, decoded by nifly. Close it (or use it as a context manager)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lib = _lib()
        self._handle = self.lib.nifw_open(str(self.path).encode())
        if not self._handle:
            raise NiflyUnavailable(f"nifly could not open {self.path}")
        error = self.lib.nifw_error(self._handle).decode() or ""
        if error:
            self.close()
            raise ValueError(f"nifly failed to load {self.path}: {error}")
        buf = ctypes.create_string_buffer(256)
        self.lib.nifw_warnings(self._handle, buf, 256, 1)
        self.status = buf.value.decode()

    # -- lifetime ---------------------------------------------------------
    def close(self) -> None:
        if self._handle:
            self.lib.nifw_close(self._handle)
            self._handle = None

    def __enter__(self) -> "NiflyFile":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):
        self.close()

    # -- data -------------------------------------------------------------
    @property
    def shape_count(self) -> int:
        return self.lib.nifw_shape_count(self._handle)

    @property
    def node_count(self) -> int:
        return self.lib.nifw_node_count(self._handle)

    def shape_name(self, i: int) -> str:
        return self.lib.nifw_shape_name(self._handle, i).decode()

    def node_names(self) -> list[str]:
        return [self.lib.nifw_node_name(self._handle, i).decode()
                for i in range(self.node_count)]

    def node_transforms(self) -> dict[str, tuple[float, ...]]:
        out = {}
        for i in range(self.node_count):
            buf = (c_float * 10)()
            if self.lib.nifw_node_transform(self._handle, i, buf):
                out[self.lib.nifw_node_name(self._handle, i).decode()] = tuple(buf)
        return out

    def shape(self, i: int) -> dict:
        nv = self.lib.nifw_shape_num_vertices(self._handle, i)
        nt = self.lib.nifw_shape_num_triangles(self._handle, i)
        name = self.shape_name(i)
        verts = np.zeros((max(nv, 0), 3), np.float32)
        norms = np.zeros((max(nv, 0), 3), np.float32)
        uvs = np.zeros((max(nv, 0), 2), np.float32)
        if nv:
            self.lib.nifw_shape_vertices(self._handle, i, verts.ctypes.data_as(POINTER(c_float)))
            self.lib.nifw_shape_normals(self._handle, i, norms.ctypes.data_as(POINTER(c_float)))
            if self.lib.nifw_shape_has_uvs(self._handle, i):
                self.lib.nifw_shape_uvs(self._handle, i, uvs.ctypes.data_as(POINTER(c_float)))
        tris = np.zeros((max(nt, 0), 3), np.uint32)
        if nt:
            self.lib.nifw_shape_triangles(self._handle, i, tris.ctypes.data_as(POINTER(c_uint)))

        n_bones = self.lib.nifw_shape_num_bones(self._handle, i)
        bones = [self.lib.nifw_shape_bone_name(self._handle, i, b).decode()
                 for b in range(n_bones)]
        textures: list[str] = []
        raw = ctypes.create_string_buffer(TEXTURE_STRIDE * NUM_TEXTURES)
        count = self.lib.nifw_shape_textures(self._handle, i, raw, len(raw), TEXTURE_STRIDE)
        for k in range(count):
            textures.append(raw.raw[k * TEXTURE_STRIDE:(k + 1) * TEXTURE_STRIDE].split(b"\0")[0].decode())

        weights = []
        bone_totals = {}
        for b in range(n_bones):
            n = self.lib.nifw_shape_num_weights(self._handle, i, b)
            if not n:
                continue
            vidx = (c_uint * n)()
            wval = (c_float * n)()
            self.lib.nifw_shape_weights(self._handle, i, b, vidx, wval)
            pairs = list(zip(list(vidx), list(wval)))
            weights.append((bones[b], pairs))
            bone_totals[bones[b]] = float(sum(w for _v, w in pairs))

        return {
            "name": name,
            "vertices": verts,
            "normals": norms,
            "uvs": uvs,
            "triangles": tris,
            "bones": bones,
            "bone_totals": bone_totals,
            "textures": textures,
            "shader_type": self.lib.nifw_shape_shader_type(self._handle, i),
        }

    def shapes(self) -> list[dict]:
        return [self.shape(i) for i in range(self.shape_count)]

    def summary(self) -> dict:
        return {
            "status": self.status,
            "nodes": self.node_count,
            "shapes": [
                {"name": self.shape_name(i),
                 "vertices": self.lib.nifw_shape_num_vertices(self._handle, i),
                 "triangles": self.lib.nifw_shape_num_triangles(self._handle, i),
                 "bones": self.lib.nifw_shape_num_bones(self._handle, i)}
                for i in range(self.shape_count)
            ],
        }
