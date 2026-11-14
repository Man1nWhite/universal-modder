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
.PHONY: help status env build busty lawson heads all inventory audit fresh test green

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

status:     ## one JSON object: environment, all 14 tracked packs, the next command (needs no venv)
	@cd "$(ROOT)" && python3 $(HERE)/status.py

env:        ## once per fresh clone or restarted sandbox: missing tracked files, pinned .venv, 2B templates; then status
	@cd "$(ROOT)" && bash $(HERE)/recover_env.sh

build:      ## Miranda_LAS -> dist/ and build/pd2-las/
	$(call BUILD,$(HERE)/build_models.py)

busty:      ## Miranda_Busty_LAS -> dist/ and build/pd2-las/
	$(call BUILD,$(HERE)/build_busty_variant.py)

lawson:     ## lawson_las -> dist/
	$(call BUILD,tools/pd2-port/build_las_pack.py)

heads:      ## the nine head packs (Miranda_*_over_*, Geralt_over_Rust) -> dist/; they read dist/Miranda_LAS.zip
	$(call BUILD,tools/build_joy_head_mods.py)

all: build busty lawson heads  ## every pack that can be rebuilt in this checkout (the two Christie packs' builder is deleted; their tracked zips cannot be rebuilt)

inventory:  ## what the source archive contains -> tools/pd2-las/source_inventory.json, the tracked record (and stdout)
	cd "$(ROOT)" && $(PY) $(HERE)/build_las.py --stage inventory --out $(HERE)

audit:      ## the mip levels of the face and eye textures against the pictures they stand for (Markdown on stdout)
	cd "$(ROOT)" && $(PY) $(HERE)/mip_audit.py

fresh:      ## every rebuildable pack built again in a copy of the tree and compared with its tracked sha256, no tolerance
	cd "$(ROOT)" && $(PY) $(HERE)/fresh.py check

test:       ## the whole suite, offline
	cd "$(ROOT)" && $(PY) -m pytest -q tests

green:      ## everything the test workflow checks (lint, suite, um, knowledge base, publish check, all 16 zips), one line each
	@cd "$(ROOT)" && $(PY) tools/pd2-port/check_all.py --full
