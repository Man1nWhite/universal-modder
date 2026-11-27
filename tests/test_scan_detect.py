"""`um scan` finds installed games and fingerprints them; the detection logic is the product.

`test_scan_vdf.py` covers the VDF parser; everything above it — the bounded file index, the binary
sniffing, the engine detection — was untested, so a wrong route was the kind of bug an agent hit in
the field. These tests build synthetic game folders in tmp_path.
"""
from __future__ import annotations

import struct

import pytest

from um import scan


def _game(tmp_path, files, dirs=()):
    root = tmp_path / "Game"
    root.mkdir()
    for rel in dirs:
        (root / rel).mkdir(parents=True)
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return root


# --------------------------------------------------------------------------- tables and small helpers


def test_plain_normalises_titles():
    assert scan._plain("Tom Clancy's Rainbow Six® Siege") == "tom clancy s rainbow six siege"
    assert scan._plain("Rusty Lake") == "rusty lake"


def test_online_only_matches_whole_names_only():
    assert scan.online_only("Valorant") == "valorant"
    assert scan.online_only("Tom Clancy's Rainbow Six® Siege X") == "tom clancy s rainbow six siege x"
    assert scan.online_only("Rusty Lake") is None           # contains "rust"; a substring must not trip it
    assert scan.online_only("Minecraft") is None


def test_in_skip_dir_matches_installers_not_games():
    assert scan._in_skip_dir("_CommonRedist/vcredist/x64.exe")
    assert scan._in_skip_dir("__redist/foo.exe")
    assert scan._in_skip_dir("SomeGame/Launcher/setup.exe") is False
    assert scan._in_skip_dir("bin/win64/game.exe") is False


# --------------------------------------------------------------------------- the file index


def test_index_lists_lower_cased_files_and_finds_globs(tmp_path):
    root = _game(tmp_path, {"GAME.exe": b"MZ", "mods/Enabled.esp": b"", "mods/deeper/deep.txt": b"x"})
    ix = scan.Index(root)
    assert "game.exe" in ix.files
    assert ix.has("*.exe") and ix.has("mods/*.esp") and ix.has("mods/deeper/*.txt")
    assert ix.has_dir("mods", "mods/deeper")
    assert ix.path("game.exe").name == "GAME.exe"          # case-insensitive resolution to the real file


def test_index_skips_vcs_and_cache_dirs(tmp_path):
    root = _game(tmp_path, {".git/config": b"x", "shadercache/big.bin": b"x", "game.exe": b"MZ"})
    ix = scan.Index(root)
    assert ix.find("*.bin") == [] and ix.find("config") == [] and ix.has("game.exe")


# --------------------------------------------------------------------------- binary sniffing


def _pe(machine: int, clr_rva: int = 0) -> bytes:
    head = bytearray(4096)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x80)
    head[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", head, 0x84, machine)
    struct.pack_into("<H", head, 0x98, 0x10B)            # PE32 magic -> data directories at +96
    struct.pack_into("<I", head, 0x98 + 96 + 14 * 8, clr_rva)  # CLR runtime header RVA (dd[14])
    return bytes(head)


def test_pe_info_reads_machine_and_managedness(tmp_path):
    native = tmp_path / "native.exe"
    native.write_bytes(_pe(0x8664, 0))
    info = scan.pe_info(native)
    assert info == dict(arch="x64", managed=False)

    managed = tmp_path / "managed.exe"
    managed.write_bytes(_pe(0x14C, 0x00002000))
    info = scan.pe_info(managed)
    assert info == dict(arch="x86", managed=True)


def test_pe_info_rejects_non_pe(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"not a pe at all")
    assert scan.pe_info(f) is None


def test_godot_pck_standalone(tmp_path):
    f = tmp_path / "game.pck"
    f.write_bytes(struct.pack("<4s4I", b"GDPC", 2, 4, 1, 1))
    assert scan.godot_pck(f) == "4.1.1 (pack format 2)"


def test_godot_pck_rejects_junk(tmp_path):
    f = tmp_path / "junk.pck"
    f.write_bytes(b"GDPC" + b"\xff" * 16)                 # insane version numbers: not a PCK
    assert scan.godot_pck(f) is None


# --------------------------------------------------------------------------- detect()


def _detect_keys(root):
    hits, facts = scan.detect(scan.Index(root))
    return [h[0] for h in hits], dict(facts)


def test_unity_mono_is_detected(tmp_path):
    root = _game(tmp_path, {
        "MyGame_Data/globalgamemanagers": b"",
        "MyGame_Data/Managed/Assembly-CSharp.dll": b"MZ",
        "UnityPlayer.dll": b"MZ",
    })
    keys, _ = _detect_keys(root)
    assert keys == ["unity-mono"]


def test_unity_il2cpp_is_detected(tmp_path):
    root = _game(tmp_path, {
        "MyGame_Data/globalgamemanagers": b"",
        "GameAssembly.dll": b"MZ",
        "UnityPlayer.dll": b"MZ",
    })
    keys, _ = _detect_keys(root)
    assert keys == ["unity-il2cpp"]


def test_unreal_is_detected_from_paks(tmp_path):
    root = _game(tmp_path, {"Game/Content/Paks/pakchunk0-Windows.pak": b"PAK"})
    keys, _ = _detect_keys(root)
    assert keys == ["unreal"]


def test_godot_is_detected_from_pck(tmp_path):
    root = _game(tmp_path, {"game.pck": struct.pack("<4s4I", b"GDPC", 2, 4, 2, 1), "game.exe": b"MZ"})
    keys, _ = _detect_keys(root)
    assert keys == ["godot"]


def test_bannerlord_wins_over_generic_dotnet(tmp_path):
    root = _game(tmp_path, {
        "bin/Win64_Shipping_Client/TaleWorlds.MountAndBlade.dll": b"MZ",
        "modules/Native/SubModule.xml": b"<SubModule/>",
    })
    keys, _ = _detect_keys(root)
    assert keys[0] == "bannerlord"


def test_no_signals_falls_back_to_native_at_low_confidence(tmp_path):
    root = _game(tmp_path, {"readme.txt": b"hello"})
    hits, _ = scan.detect(scan.Index(root))
    assert [h[0] for h in hits] == ["native"]
    assert hits[0][1] == 10


# --------------------------------------------------------------------------- resolve_game


def test_resolve_game_by_path_returns_the_folder(tmp_path, monkeypatch):
    root = _game(tmp_path, {"readme.txt": b"x"})
    monkeypatch.setattr(scan, "all_games", lambda: [])
    game = scan.resolve_game(str(root))
    assert game["path"] == str(root)


def test_resolve_game_prefers_the_exact_name(monkeypatch):
    games = [dict(store="steam", appid="1", name="Terraria", path="/games/terraria", workshop=None),
             dict(store="steam", appid="2", name="Terraria Mod", path="/games/terraria-mod", workshop=None)]
    monkeypatch.setattr(scan, "all_games", lambda: games)
    game = scan.resolve_game("Terraria")
    assert game["appid"] == "1"


def test_resolve_game_dies_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(scan, "all_games", lambda: [dict(store="steam", appid="1", name="Terraria", path="/g", workshop=None)])
    with pytest.raises(SystemExit):
        scan.resolve_game("halo infinite")
