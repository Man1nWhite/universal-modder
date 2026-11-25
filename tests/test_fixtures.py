"""Third-party Lua fixtures are byte-pinned inputs to the glove behavior harness."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"
README = (FIX / "README.md").read_text(encoding="utf-8")


FIXTURES = {
    "las_loader_4.1.9.lua": "21afb703889e172e51244ff675c27a510eacbae00bdd81996c9761eae92965ad",
    "PlayerStyleGloveHooks.lua": "ca6bbb78a330c89981c0f9fafd58da67e03d4e95a56b6bd63152b66065f62b65",
    "playerstyletweakdata.lua": "acbe14680a1b957f910da6b2813ea4955b4e0f15eedf945b9073413860d415bb",
}


def test_fixture_hashes_match_the_readme_and_raw_bytes():
    for name, expected in FIXTURES.items():
        hashes = re.findall(r"SHA-256(?: of this excerpt file)?:\s*`([0-9a-f]{64})`", README)
        match_hashes = hashes[list(FIXTURES).index(name)] if len(hashes) == len(FIXTURES) else None
        assert match_hashes == expected, f"README hash for {name} is stale"
        raw = (FIX / name).read_bytes()
        if name == "las_loader_4.1.9.lua":
            assert b"\r\n" not in raw, "line endings were converted; fixtures must remain byte-exact"
        assert hashlib.sha256(raw).hexdigest() == expected, f"fixture bytes changed: {name}"


def test_beardlib_fixture_contains_the_glove_decisions_executed_by_harness():
    source = (FIX / "PlayerStyleGloveHooks.lua").read_text(encoding="utf-8")
    assert "if glove_id == false then" in source
    assert "return false" in source
    assert "player_style_td.glove_adapter = false" in source


def test_game_fixture_retains_only_the_character_override_lookup_functions():
    source = (FIX / "playerstyletweakdata.lua").read_bytes().decode("utf-8")
    assert source.count("function ") == 2
    for function in ("get_player_style_value", "get_suit_variation_value"):
        assert f"function BlackMarketTweakData:{function}" in source
