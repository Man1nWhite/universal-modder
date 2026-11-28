# pd2-las commands. From the repo root:  make -sC tools/pd2-las <target>
#
# Every target is one command with no arguments to remember: the scripts carry
# the defaults (the 2B templates directory, the output paths). `make -n <target>`
# prints the command, to run by hand from the repo root where there is no make.
#
# Keep the -s. GNU make wraps the output of a bare `make -C` in "Entering
# directory" / "Leaving directory" lines, on stdout, and nothing inside a
# makefile can turn that off before make 4.4; with -s it does not print them,
# so `make -sC tools/pd2-las status` is one JSON object and nothing else.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
# The venv interpreter: `.venv/bin/python` on POSIX, `.venv/Scripts/python.exe` on Windows
# (git-bash / MSYS make). `env` builds the POSIX venv with recover_env.sh; a Windows venv
# made by hand (see the README) is found the same way.
PY   := $(firstword $(wildcard .venv/bin/python .venv/Scripts/python.exe) .venv/bin/python)
# `status` and `help` run before a venv exists, so they take whatever Python is there.
SYS_PY := $(or $(wildcard .venv/bin/python),$(wildcard .venv/Scripts/python.exe),python3)
HERE := tools/pd2-las
LOGS := build/pd2-las

.DEFAULT_GOAL := help
.PHONY: help status env build honokodae bunny heads voices_stream voices_tables voices_char_rust voices_sheets voices_master glb all inventory audit fresh test green

# A build target prints the state of the packs it wrote and nothing else: `tracked`
# says the rebuild reproduced the committed bytes. What the builder printed is in
# build/pd2-las/<target>.log; when the builder fails, its last lines are shown.
define BUILD
@cd "$(ROOT)" && mkdir -p $(LOGS) && { $(PY) $(1) > $(LOGS)/$@.log 2>&1 \
	|| { tail -n 25 $(LOGS)/$@.log; echo "FAILED: $(1) (the whole log: $(LOGS)/$@.log)"; exit 1; }; } \
	&& $(SYS_PY) $(HERE)/status.py $@
endef

help:       ## list the targets
	@sed -n 's/^\([a-z_]*\):.*## /\1\t/p' $(MAKEFILE_LIST)

status:     ## one JSON object: environment, all tracked packs, the next command (needs no venv)
	@cd "$(ROOT)" && $(SYS_PY) $(HERE)/status.py

env:        ## once per fresh clone or restarted sandbox: missing tracked files, pinned .venv, 2B templates; then status
	@cd "$(ROOT)" && bash $(HERE)/recover_env.sh

build:      ## Miranda_L4D2_LAS -> dist/Miranda_L4D2/
	$(call BUILD,$(HERE)/build_models.py)

honokodae:  ## OfficeSuite (DOAXVV 'Secret Report' from .dae; ships the FPS arms unit) -> dist/Miranda/
	$(call BUILD,$(HERE)/build_honoko2_dae.py)

bunny:      ## OfficeSuite_over_Bunny: native mod_overrides replacement of Hop to It (bunny), body + FPS arms -> dist/Miranda/
	$(call BUILD,$(HERE)/build_bunny_body_mod.py)

heads:      ## the over Hila heads, Geralt_over_Rust, Arivus_over_Hoxton -> dist/Miranda/, dist/Geralt/, dist/Arivus/; they read dist/Miranda_L4D2/Miranda_L4D2_LAS.zip
	$(call BUILD,tools/build_joy_head_mods.py)


voices_stream:  ## Miranda_Lawson_VO_over_Hila_Stream: the same clips as one Wwise ADPCM .stream per Hila voice-line id, no BeardLib -> dist/Miranda/
	$(call BUILD,tools/build_hila_stream_mod.py)

voices_tables:  ## the Rust and Old Hoxton stream tables (slot -> bank -> id) -> voice_lines_vox/targets/
	@cd "$(ROOT)" && $(PY) tools/build_stream_tables.py

# voices_geralt / voices_arivus (and the Geralt_VO_over_Rust_Stream / Arivus_VO_over_Hoxton_Stream
# packs) are gone: retired and deleted from dist/ 2026-11-28 (D89); never heard in game.
# The builder remains for the char_rust route below.
# Not a BUILD target: the re-keyed pack is not tracked in dist/ until the id map exists (D74),
# so `fresh` and `status` do not own it - the builder prints its own state.
voices_char_rust:  ## Geralt's takes onto Rust's own char_rust bank (refuses until voice_lines_vox/geralt/char_rust_ids.csv names every id)
	@cd "$(ROOT)" && $(PY) tools/build_character_stream_mod.py --pack geralt-rust --bank char_rust

# Not a BUILD target either: an import is an input, not a pack, so `fresh`/`status` do not own it.
voices_sheets:  ## import a community voice-line sheet (id | who | what | notes) -> voice_lines_vox/sheets/ ; SHEET=references/sheets/<file>.csv WANT=Rust
	@cd "$(ROOT)" && test -n "$(SHEET)" || { echo "usage: make -sC tools/pd2-las voices_sheets SHEET=references/sheets/<file>.csv [WANT=Rust]"; exit 1; }
	@cd "$(ROOT)" && $(PY) tools/import_voiceline_sheet.py --sheet "$(SHEET)" $(if $(TAB),--tab "$(TAB)") $(if $(WANT),--who "$(WANT)") $(if $(LEADS),--keys)

# Not a BUILD target: the workbook is a tracked artifact, not a pack; `fresh`/`status` do not own it.
voices_master:  ## the VO source-of-truth workbook + per-tab CSVs -> voice_lines_vox/vo_master.xlsx, voice_lines_vox/vo_master/
	@cd "$(ROOT)" && $(PY) tools/build_vo_master.py

glb:            ## Arivus_Head_over_Old_Hoxton_GLB: the Arivus head .glb + its .dds, from the tracked Arivus_over_Hoxton.zip -> dist/Arivus/
	$(call BUILD,$(HERE)/build_arivus_glb_pack.py)

# These consumers share base build files or read the base ZIP. Order them when
# both goals are requested, but don't rebuild an existing base for `make heads`.
ifneq ($(filter all build,$(MAKECMDGOALS)),)
heads: build
endif

ifneq ($(filter all honokodae,$(MAKECMDGOALS)),)
bunny: honokodae
endif

ifneq ($(filter all heads,$(MAKECMDGOALS)),)
glb: heads
endif

all: build honokodae bunny heads voices_stream glb  ## every tracked pack

inventory:  ## what the source archive contains -> tools/pd2-las/source_inventory.json, the tracked record (and stdout)
	cd "$(ROOT)" && $(PY) $(HERE)/build_las.py --stage inventory --out $(HERE)

audit:      ## the mip levels of the face and eye textures against the pictures they stand for (Markdown on stdout)
	cd "$(ROOT)" && $(PY) $(HERE)/mip_audit.py

fresh:      ## every tracked pack built again in a copy of the tree and compared with its tracked sha256, no tolerance
	cd "$(ROOT)" && $(PY) $(HERE)/fresh.py check

test:       ## the whole suite, offline
	cd "$(ROOT)" && $(PY) -m pytest -q tests

green:      ## everything the test workflow checks (lint, suite, um, knowledge base, publish check, all distribution ZIPs), one line each
	@cd "$(ROOT)" && $(PY) tools/pd2-port/check_all.py --full
