# Generated views of the import graphs guarded by checks.mk. A gate reports
# whether a rule held; these diagrams show whether the resulting structure is
# the one we meant. Each renderer walks the same graph as its corresponding
# architecture checker.

.PHONY: architecture-diagrams be-graph be-graphs be-graph-all gui-graph gui-graph-core

# Output is gitignored: these are local analysis artifacts, not files to review
# in a diff. `dist/images` already means loadable container archives, so graphs
# keep their distinct `dist/diagrams` namespace.
#
# One subdirectory per kind of question, because the root had grown to hold two
# unrelated families: import graphs answer "what depends on what in the code",
# and the domain views next door answer "what is an REE". A reader opening
# `dist/diagrams` should see that split before they see thirteen files.
DIAGRAM_DIR ?= dist/diagrams
ARCH_DIR ?= $(DIAGRAM_DIR)/architecture

# Declared empty so `make --warn-undefined-variables` stays quiet for anyone
# who runs these without passing extra flags.
ARGS ?=
GUI_ARGS ?=

architecture-diagrams: be-graphs be-graph-all gui-graph gui-graph-core

# Backend, via grimp — the engine import-linter itself is built on — reading
# the root_packages and layers contracts straight out of pyproject.toml.
#
# The package list is not written here. `make be-graph` used to draw core and
# nothing else, which quietly made "the backend diagram" mean "the diagram of
# the package someone thought to pass": a package with no picture is exactly the
# one whose shape nobody is checking. Asking the script for root_packages keeps
# the set of diagrams equal to the set of packages the contracts govern, so
# adding a seventh package to the workspace adds its diagram too.
#
# Recursively expanded (`=`, not `:=`) so the script runs when `be-graphs`
# expands it and not when make parses this file. With `:=` it ran on *every*
# make invocation — `make push-image-archives` on a host outside the devshell has no
# `python`, so every target printed "make: python: No such file or directory"
# before doing anything, and this list came out empty. Referenced once, in
# be-graphs below; a second reference would re-run the script, so read it into a
# shell variable rather than expanding it twice.
BE_PACKAGES = $(shell python scripts/arch_graph.py --list-packages)

# One diagram per root package: the inside of that package, with its own layers
# contract setting the vertical axis. PKG/ARGS still single out one package
# (`make be-graph PKG=repo2ree_api ARGS=--hide-leaves`) for when you are working
# on it and want one file to reload.
PKG ?= repo2ree_core
be-graph:
	@mkdir -p $(ARCH_DIR)
	python scripts/arch_graph.py $(PKG) $(ARGS) -f svg -o $(ARCH_DIR)/$(PKG).svg

# Refuses to draw nothing. An empty word list is legal shell — `for pkg in ; do
# … done` loops zero times and exits 0 — so a derivation that came back empty
# would report success having produced no diagrams, which is the silent outcome
# the derived list exists to prevent. Reads it into a shell variable, so the
# script runs once rather than per reference.
be-graphs:
	@mkdir -p $(ARCH_DIR)
	@set -e; packages="$(BE_PACKAGES)"; \
	[ -n "$$packages" ] || { echo "no root packages resolved from pyproject.toml" \
		"[tool.importlinter] — check 'python scripts/arch_graph.py --list-packages'" >&2; exit 1; }; \
	for pkg in $$packages; do \
		python scripts/arch_graph.py $$pkg $(ARGS) -f svg -o $(ARCH_DIR)/$$pkg.svg; \
	done

# The two views across all six packages, which answer different questions.
#
# workspace.svg folds each package to one node. This is the only picture where
# "Workspace layers", "Protocol imports no workspace package" and "Agent and
# supervisor speak only protocol" are things you can see rather than rules you
# have to trust: the packages are stacked in the contract's order, so all three
# hold exactly when no arrow points up the page. Edge labels carry the import
# count, which is where it becomes obvious that core -> protocol (89) is a
# different kind of dependency from api -> supervisor (1).
#
# workspace-modules.svg is the same graph without the folding — every top-level
# module of every package, and the cross-package edges the per-package diagrams
# necessarily cut. Honest and unavoidably wide; it is for tracing one specific
# edge back to the modules underneath it, not for reading the shape.
be-graph-all:
	@mkdir -p $(ARCH_DIR)
	python scripts/arch_graph.py --collapse $(ARGS) -f svg -o $(ARCH_DIR)/workspace.svg
	python scripts/arch_graph.py --all $(ARGS) -f svg -o $(ARCH_DIR)/workspace-modules.svg

# GUI, via dependency-cruiser's own dot reporter — the same cruise
# gui-checks runs, rendered instead of asserted, so rule violations show up
# coloured in the picture.
#
# The collapse pattern is the substance of the target. dependency-cruiser's
# built-in `archi` reporter folds to one level under src/, which here yields
# just `core` and `shell` — true, and too coarse to see anything. Folding one
# level deeper inside shell/ produces the boundary the rules actually police:
# core, and shell's infra / data / ui / app / state. Override GUI_COLLAPSE to
# zoom (or pass an empty value for the full module graph); GUI_ARGS forwards
# flags such as --focus.
#
# The cruise writes DOT to a file rather than piping straight into `dot`: in a
# pipeline the shell reports only the last command's status, so a cruise that
# died would still leave make green and the output holding an empty SVG.
GUI_COLLAPSE ?= ^src/(core|shell/[^/]+)/
gui-graph:
	@mkdir -p $(ARCH_DIR)
	cd gui && npx depcruise src \
		--include-only '^src' \
		--output-type dot \
		$(if $(GUI_COLLAPSE),--collapse '$(GUI_COLLAPSE)',) \
		$(GUI_ARGS) \
		--output-to ../$(ARCH_DIR)/gui.dot
	dot -Tsvg -o $(ARCH_DIR)/gui.svg $(ARCH_DIR)/gui.dot
	@rm -f $(ARCH_DIR)/gui.dot
	@echo "wrote $(ARCH_DIR)/gui.svg"

# Expand the functional core by one namespace while retaining the collapsed
# shell around it. Cruising all of src is deliberate: a core-only cruise would
# mislabel modules reached only from the shell as orphans, and it would hide
# which shell layer consumes each core namespace.
GUI_CORE_COLLAPSE ?= ^src/(core/[^/]+|shell/[^/]+)/
gui-graph-core:
	@mkdir -p $(ARCH_DIR)
	cd gui && npx depcruise src \
		--include-only '^src' \
		--output-type dot \
		--collapse '$(GUI_CORE_COLLAPSE)' \
		$(GUI_ARGS) \
		--output-to ../$(ARCH_DIR)/gui-core.dot
	dot -Tsvg -o $(ARCH_DIR)/gui-core.svg $(ARCH_DIR)/gui-core.dot
	@rm -f $(ARCH_DIR)/gui-core.dot
	@echo "wrote $(ARCH_DIR)/gui-core.svg"
