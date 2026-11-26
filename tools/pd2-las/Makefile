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
PY   := .venv/bin/python
HERE := tools/pd2-las
LOGS := build/pd2-las

.DEFAULT_GOAL := help
.PHONY: help status env fetch build busty lawson honokodae honokodae_head christie cloverchristie heads hila voices_stream voices_geralt voices_arivus voices_tables voices_char_rust voices_sheets glb all inventory audit fresh test green

# A build target prints the state of the packs it wrote and nothing else: `tracked`
# says the rebuild reproduced the committed bytes. What the builder printed is in
# build/pd2-las/<target>.log; when the builder fails, its last lines are shown.
define BUILD
@cd "$(ROOT)" && mkdir -p $(LOGS) && { $(PY) $(1) > $(LOGS)/$@.log 2>&1 \
	|| { tail -n 25 $(LOGS)/$@.log; echo "FAILED: $(1) (the whole log: $(LOGS)/$@.log)"; exit 1; }; } \
	&& python3 $(HERE)/status.py $@
endef

help:       ## list the targets
	@sed -n 's/^\([a-z]*\):.*## /\1\t/p' $(MAKEFILE_LIST)

status:     ## one JSON object: environment, all tracked packs, the next command (needs no venv)
	@cd "$(ROOT)" && python3 $(HERE)/status.py

env:        ## once per fresh clone or restarted sandbox: missing tracked files, pinned .venv, 2B templates; then status
	@cd "$(ROOT)" && bash $(HERE)/recover_env.sh

fetch:      ## the published packs and source archives, into place, every sha256 checked (no venv, needs network)
	@cd "$(ROOT)" && python3 tools/release_assets.py fetch

build:      ## Miranda_L4D2_LAS -> dist/Miranda_L4D2/
	$(call BUILD,$(HERE)/build_models.py)

busty:      ## Miranda_L4D2_Busty_LAS -> dist/Miranda_L4D2/
	$(call BUILD,$(HERE)/build_busty_variant.py)

lawson:     ## Miranda_Romance_LAS -> dist/Miranda_Romance/
	$(call BUILD,tools/pd2-port/build_las_pack.py)

honokodae:  ## OfficeSuite (DOAXVV 'Secret Report' from .dae; ships the FPS arms unit) -> dist/Honoka/
	$(call BUILD,$(HERE)/build_honoko2_dae.py)

honokodae_head:  ## OfficeSuite_Head: OfficeSuite + the Miranda Romance head as one whole-character LAS -> dist/Honoka/
	$(call BUILD,$(HERE)/build_honoko2_dae.py --only officesuite_head)

christie:   ## headless and handless Christie LAS, TPP and FPS -> dist/Christie/
	$(call BUILD,$(HERE)/build_christie_source.py)

cloverchristie:  ## Christie GLB body-only LAS (experimental, TPP only) -> dist/Christie/
	$(call BUILD,$(HERE)/build_clover_christie.py)

heads:      ## the head packs (Miranda_*_over_*, Geralt_over_Rust, Arivus_over_Hoxton) -> dist/; they read dist/Miranda_L4D2/Miranda_L4D2_LAS.zip
	$(call BUILD,tools/build_joy_head_mods.py)

hila:       ## OfficeSuite + Miranda Romance over Hila (native body and head, no LAS) -> dist/Honoka/
	$(call BUILD,tools/build_hila_body_mod.py)


voices_stream:  ## Miranda_Lawson_VO_over_Hila_Stream: the same clips as one Wwise ADPCM .stream per Hila voice-line id, no BeardLib -> dist/Hila/
	$(call BUILD,tools/build_hila_stream_mod.py)

voices_geralt:  ## Geralt_VO_over_Rust_Stream: Geralt barks for the 29 slots the set covers, same id-keyed route -> dist/Geralt/
	$(call BUILD,tools/build_character_stream_mod.py --pack geralt-rust)

voices_arivus:  ## Arivus_VO_over_Hoxton_Stream: Arivus barks (+ the borrowed 'Hoxton.' callout) for the slots the set covers -> dist/Arivus/
	$(call BUILD,tools/build_character_stream_mod.py --pack arivus-old-hoxton)

voices_tables:  ## the Rust and Old Hoxton stream tables (slot -> bank -> id) -> voice_lines_vox/targets/
	@cd "$(ROOT)" && $(PY) tools/build_stream_tables.py

# Not a BUILD target: the re-keyed pack is not tracked in dist/ until the id map exists (D74),
# so `fresh` and `status` do not own it - the builder prints its own state.
voices_char_rust:  ## Geralt's takes onto Rust's own char_rust bank (refuses until voice_lines_vox/geralt/char_rust_ids.csv names every id)
	@cd "$(ROOT)" && $(PY) tools/build_character_stream_mod.py --pack geralt-rust --bank char_rust

# Not a BUILD target either: an import is an input, not a pack, so `fresh`/`status` do not own it.
voices_sheets:  ## import a community voice-line sheet (id | who | what | notes) -> voice_lines_vox/sheets/ ; SHEET=references/<file>.csv WANT=Rust
	@cd "$(ROOT)" && test -n "$(SHEET)" || { echo "usage: make -sC tools/pd2-las voices_sheets SHEET=references/regular_vox.csv [WANT=Rust]"; exit 1; }
	@cd "$(ROOT)" && $(PY) tools/import_voiceline_sheet.py --sheet "$(SHEET)" $(if $(TAB),--tab "$(TAB)") $(if $(WANT),--who "$(WANT)") $(if $(LEADS),--keys)

glb:            ## Arivus_Head_over_Old_Hoxton_GLB: the Arivus head .glb + its .dds, from the tracked Arivus_over_Hoxton.zip -> dist/Arivus/
	$(call BUILD,$(HERE)/build_arivus_glb_pack.py)

# These consumers share base build files or read the base ZIP. Order them when
# both goals are requested, but don't rebuild an existing base for `make heads`.
ifneq ($(filter all build,$(MAKECMDGOALS)),)
busty heads: build
endif

# The direct Hila pack consumes the two assembled donors, not 2B templates.
ifneq ($(filter all honokodae,$(MAKECMDGOALS)),)
hila: honokodae
endif
ifeq ($(filter honokodae_head,$(MAKECMDGOALS)),honokodae_head)
honokodae_head: hila
endif
ifneq ($(filter all heads,$(MAKECMDGOALS)),)
hila: heads
endif

all: build busty lawson honokodae honokodae_head christie cloverchristie heads hila voices_stream voices_geralt voices_arivus glb  ## every tracked pack

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
