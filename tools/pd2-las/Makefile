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

.DEFAULT_GOAL := help
.PHONY: help status env build busty christie slim all inventory audit fresh test

help:       ## list the targets
	@sed -n 's/^\([a-z]*\):.*## /\1\t/p' $(MAKEFILE_LIST)

status:     ## one JSON object: inputs, env, templates, tracked packs (needs no venv)
	@cd "$(ROOT)" && python3 $(HERE)/status.py

env:        ## once per fresh clone or wiped sandbox: pinned .venv + the 2B templates -> build/pd2-las/2b/
	cd "$(ROOT)" && bash $(HERE)/recover_env.sh

build:      ## Miranda_LAS -> dist/ and build/pd2-las/
	cd "$(ROOT)" && $(PY) $(HERE)/build_models.py

busty:      ## Miranda_Busty_LAS -> dist/ and build/pd2-las/
	cd "$(ROOT)" && $(PY) $(HERE)/build_busty_variant.py

christie:   ## Christie_LAS -> dist/
	cd "$(ROOT)" && $(PY) $(HERE)/build_christie_las.py

slim:       ## Christie_LAS_Slim -> dist/
	cd "$(ROOT)" && $(PY) $(HERE)/build_christie_las.py --variant slim

all: build busty christie slim  ## the four packs

inventory:  ## what the source archive contains -> tools/pd2-las/source_inventory.json, the tracked record (and stdout)
	cd "$(ROOT)" && $(PY) $(HERE)/build_las.py --stage inventory --out $(HERE)

audit:      ## the mip levels of the face and eye textures against the pictures they stand for (Markdown on stdout)
	cd "$(ROOT)" && $(PY) $(HERE)/mip_audit.py

fresh:      ## every tracked pack built again in a copy of the tree and compared with its tracked sha256, no tolerance
	cd "$(ROOT)" && $(PY) $(HERE)/fresh.py check

test:       ## the whole suite, offline
	cd "$(ROOT)" && $(PY) -m pytest -q tests
