#!/usr/bin/env python3
"""Adversarial self-test: does the compliance checker actually catch violations?

A checker that passes everything is worthless. This mutates the built pack
in the ways the guide's rules forbid and asserts that the matching check
fails. Run it directly, or through the test suite.

    python tools/pd2-port/check_guide_compliance.py --self-test
"""
from __future__ import annotations

import importlib.util
import io
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


checker = _load("check_guide_compliance", "check_guide_compliance.py")
build = _load("build_las_pack", "build_las_pack.py")
dds = _load("dds_las", "dds.py")

PACK = ROOT / "dist" / "lawson_las.zip"
TPP_CFG = "Lawson_LAS/units/lawson/skins/lawson/lawson.material_config"
FPS_CFG = "Lawson_LAS/units/lawson/skins/lawson/fps_lawson.material_config"
TPP_MODEL = "Lawson_LAS/units/lawson/skins/lawson/lawson.model"
FPS_MODEL = "Lawson_LAS/units/lawson/skins/lawson/fps_lawson.model"
NM_TEXTURE = "Lawson_LAS/units/lawson/skins/lawson/body1_nm.texture"


def read_pack() -> dict[str, bytes]:
    with zipfile.ZipFile(PACK) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def audit_pack(files: dict[str, bytes]):
    """Run the checker against an in-memory pack (no zip on disk)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        zip_path = root / "pack.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
        return checker.audit(zip_path)


def failed_ids(report) -> set[str]:
    return {c["id"] for c in report.checks if c["status"] == "FAIL"}


# --------------------------------------------------------------- mutations
def m_invented_template(files):
    """M4: an invented render-template keyword combination."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = cfg.replace(
        "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS",
        "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SHINY:SKINNED_3WEIGHTS"
    ).encode()
    return files


def m_no_unique(files):
    """M5: a contour material without unique="true"."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = cfg.replace(' unique="true"', "", 1).encode()
    return files


def m_no_contour_var(files):
    """M5: contour without the contour_opacity variable."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = re.sub(r'\s*<variable value="0" type="scalar" name="contour_opacity"/>',
                             "", cfg).encode()
    return files


def m_no_depth_scaling(files):
    """M6: an FPS material_config without DEPTH_SCALING."""
    cfg = files[FPS_CFG].decode()
    files[FPS_CFG] = cfg.replace("DEPTH_SCALING:", "").encode()
    return files


def m_mip0_only_texture(files):
    """T1: a texture with only mip 0 (the old mip-0-only bug)."""
    data = files[NM_TEXTURE]
    size = int.from_bytes(data[12:16], "little")
    mip0 = data[dds.DDS_HEADER_SIZE:]
    truncated = bytearray(data[:dds.DDS_HEADER_SIZE]) + mip0
    struct_pack = truncated[4:8]
    truncated[4:8] = (len(truncated) - 4).to_bytes(4, "little")
    truncated[28:32] = (0).to_bytes(4, "little")          # dwMipMapCount = 0
    truncated[80:84] = (0x00081007).to_bytes(4, "little")  # vanilla-ish flags
    truncated[108:112] = (0x00001000).to_bytes(4, "little")
    files[NM_TEXTURE] = bytes(truncated)
    return files


def m_unpacked_normal(files):
    """T2: a normal map in the plain RGB layout (X in red, not alpha)."""
    data = files[NM_TEXTURE]
    size = int.from_bytes(data[12:16], "little")
    from PIL import Image
    import numpy as np
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    arr = np.asarray(img).copy()
    arr[..., 0] = 128      # red = flat X
    arr[..., 2] = 255      # blue = Z
    arr[..., 3] = 255
    mips = dds.mip_payloads_from_image(Image.fromarray(arr, "RGBA"))
    files[NM_TEXTURE] = dds.pack_dds(mips, size)
    return files


def m_missing_addfile(files):
    """P2: an AddFiles entry that points at nothing."""
    main = files["Lawson_LAS/main.xml"].decode()
    main = main.replace('        <df_nm path="units/lawson/skins/lawson/face"/>\n', "")
    files["Lawson_LAS/main.xml"] = main.encode()
    return files


def m_no_hooks(files):
    """P1: a manifest without the Hooks section."""
    main = files["Lawson_LAS/main.xml"].decode()
    main = re.sub(r"\s*<Hooks directory=\"hooks\">.*?</Hooks>", "", main, flags=re.S)
    files["Lawson_LAS/main.xml"] = main.encode()
    return files


def m_hook_flag(files):
    """P3: the LAS registration without fps_replace_body."""
    hook = files["Lawson_LAS/hooks/lawson.lua"].decode()
    files["Lawson_LAS/hooks/lawson.lua"] = hook.replace(
        "\tfps_replace_body = true", "\tfps_replace_body = false").encode()
    return files


def m_missing_loc_key(files):
    """P4: a localization without the description key."""
    loc = files["Lawson_LAS/localization/english.txt"].decode()
    files["Lawson_LAS/localization/english.txt"] = re.sub(
        r'.*bm_askn_lawson_desc.*\n', "", loc).encode()
    return files


def m_renamed_material(files):
    """M3: a config material name that no longer matches the model."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = cfg.replace('name="mtr_body1"', 'name="mtr_bodyOne"').encode()
    return files


def m_old_version(files):
    """M1: a materials header with the wrong version."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = cfg.replace('<materials version="3"', '<materials version="2"').encode()
    return files


def m_texture_extension(files):
    """M7: a texture path with the file extension in it."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = cfg.replace('file="units/lawson/skins/lawson/body1_df"',
                                  'file="units/lawson/skins/lawson/body1_df.texture"').encode()
    return files


def m_skinning_keyword(files):
    """K1: a material that claims one weight while its geometry uses three."""
    cfg = files[TPP_CFG].decode()
    files[TPP_CFG] = cfg.replace(
        "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS",
        "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_1WEIGHT").encode()
    return files


def m_missing_unit_mat(files):
    """P2: the FPS unit is not registered."""
    main = files["Lawson_LAS/main.xml"].decode()
    main = main.replace('        <unit_mat path="units/lawson/skins/lawson/fps_lawson"/>\n', "")
    files["Lawson_LAS/main.xml"] = main.encode()
    return files


MUTATIONS = [
    (m_invented_template, "M4", "invented render template"),
    (m_no_unique, "M5", "contour without unique=true"),
    (m_no_contour_var, "M5", "contour without contour_opacity"),
    (m_no_depth_scaling, "M6", "FPS without DEPTH_SCALING"),
    (m_mip0_only_texture, "T1", "texture with mip 0 only"),
    (m_unpacked_normal, "T2", "normal map not in the PD2 layout"),
    (m_missing_addfile, "P2", "AddFiles entry that resolves to nothing"),
    (m_no_hooks, "P1", "manifest without Hooks"),
    (m_hook_flag, "P3", "hook without fps_replace_body"),
    (m_missing_loc_key, "P4", "localization without the description key"),
    (m_renamed_material, "M3", "material name that does not match the model"),
    (m_old_version, "M1", "materials header with the wrong version"),
    (m_texture_extension, "M7", "texture path with a file extension"),
    (m_skinning_keyword, "K1", "skinning keyword below the geometry's influences"),
    (m_missing_unit_mat, "P2", "FPS unit not registered"),
]


def self_test(verbose: bool = True) -> int:
    base = read_pack()
    clean = failed_ids(audit_pack(base))
    if clean:
        print(f"FAIL the unmodified pack already fails: {sorted(clean)}")
        return 1
    if verbose:
        print(f"baseline: the unmodified pack passes every check "
              f"({len(audit_pack(base).checks)} checks)\n")
    bad = 0
    for mutate, expect, label in MUTATIONS:
        files = mutate(dict(base))
        ids = failed_ids(audit_pack(files))
        ok = expect in ids
        if not ok:
            bad += 1
        print(f"{'ok  ' if ok else 'MISS'}  {expect:<3} {label:<52} "
              f"failed: {sorted(ids) or '-'}")
    print(f"\n{len(MUTATIONS) - bad}/{len(MUTATIONS)} mutations detected")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(self_test())
