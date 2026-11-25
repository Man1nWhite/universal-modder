# Test fixtures — third-party mod code

## `las_loader_4.1.9.lua`

Verbatim copy of **Legendary Armour Skins 4.1.9**'s outfit loader
(`hooks/outfits/loader.lua`), fetched 2026-11-03 from the public mirror
`Vladik268/P2` on GitHub (`mod/Legendary Armour Skins/hooks/outfits/loader.lua`,
branch `main`). SHA-256:
`21afb703889e172e51244ff675c27a510eacbae00bdd81996c9761eae92965ad`.

It is executed unmodified by `tests/test_glove_behavior_lua.py` inside a
LuaJIT 2.1 runtime (PD2's Lua dialect) so the glove-adapter compat hook is
checked against the real registration behavior — notably the fresh-table reads
`output.default_glove_id = output.default_glove_id or false` and
`output.glove_adapter = output.glove_adapter or false`, which caused the
in-game "no hands" bug.

### `PlayerStyleGloveHooks.lua`

Verbatim copy of BeardLib's `Hooks/Items/PlayerStyleGloveHooks.lua` at
`simon-wh/PAYDAY-2-BeardLib` commit
`95eb1c0c84e3f07d36f28a5e69197ec3b5c59046`. SHA-256:
`ca6bbb78a330c89981c0f9fafd58da67e03d4e95a56b6bd63152b66065f62b65`.
It is loaded and executed directly by `tests/test_glove_behavior_lua.py` for the glove
resolution and initialization branches. The upstream BeardLib repository is
MIT-licensed; its `LICENSE.md` is reproduced below.

### `playerstyletweakdata.lua`

Two function excerpts (the player-style and material-variation lookup functions)
from the decompiled game file
`pd2-lua/lib/tweak_data/blackmarket/playerstyletweakdata.lua` at
`AzureeDev/payday-2-luajit` commit
`6305c67cc603cb1e8965d680fea1226da1966eef`. SHA-256 of this excerpt file:
`acbe14680a1b957f910da6b2813ea4955b4e0f15eedf945b9073413860d415bb`. The source file upstream SHA-256 is
`c0c45c1ead37a22af5454149bda1001ca2dc8405ba9cf642a910a52bd24c2e2b`.
It is the source for the player-style character-override-first lookup exercised
by the same test fixture contract.

The source was fetched from `AzureeDev/payday-2-luajit` at commit
`6305c67cc603cb1e8965d680fea1226da1966eef`; only these two functions are
retained, with original logic and source line positions 2987 and 3011.

BeardLib license (`simon-wh/PAYDAY-2-BeardLib/LICENSE.md`):

```
The MIT License (MIT)

Copyright (c) 2015 Simon Whyte

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Tests pin these hashes and execute the vendored BeardLib hooks directly.
Do not edit these files; re-fetch them when updating the supported loader or
behavior under test. `.gitattributes` disables line-ending conversion here.
