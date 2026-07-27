# Documentation: the prose gate and the generated architecture diagrams.
#
# Separate from checks.mk because only half of this is a gate. `docs-lint`
# fails a build; the diagrams are things you look at when deciding whether the
# structure is the one you meant, which is a different job from asserting that
# today's structure matches yesterday's rules.

.PHONY: docs-lint docs-diagrams be-graph fe-graph

# ================================================
# Prose linting
# ================================================

docs-lint:
	@echo "Linting docs with Vale..."
	vale sync
	vale docs README.md

# ================================================
# Architecture diagrams
# ================================================
#
# The pictures the import rules in checks.mk describe. Both halves of the
# codebase gate their import graph, and a gate only ever reports that a rule
# held — it cannot tell you whether the shape it held over is the one you
# meant. These render that shape, each from the same graph its own checker
# walks, so a diagram cannot drift from the rules it illustrates.
#
# Output is gitignored: these are things you look at, not artifacts to review
# in a diff. They live under dist/diagrams rather than dist/images, which
# already means loadable container tarballs (see images.mk).

DIAGRAM_DIR ?= dist/diagrams

# Declared empty so `make --warn-undefined-variables` stays quiet for anyone
# who runs these without passing extra flags.
ARGS ?=
FE_ARGS ?=

docs-diagrams: be-graph fe-graph

# Backend, via grimp — the engine import-linter itself is built on — reading
# the root_packages and layers contracts straight out of pyproject.toml. PKG
# picks a root package, ARGS forwards flags such as --all or --hide-leaves.
PKG ?= repo2ree_core
be-graph:
	@mkdir -p $(DIAGRAM_DIR)
	python scripts/arch_graph.py $(PKG) $(ARGS) -f svg -o $(DIAGRAM_DIR)/$(PKG).svg

# Frontend, via dependency-cruiser's own dot reporter — the same cruise
# fe-checks runs, rendered instead of asserted, so rule violations show up
# coloured in the picture.
#
# The collapse pattern is the substance of the target. dependency-cruiser's
# built-in `archi` reporter folds to one level under src/, which here yields
# just `core` and `shell` — true, and too coarse to see anything. Folding one
# level deeper inside shell/ produces the boundary the rules actually police:
# core, and shell's infra / data / ui / app / state. Override FE_COLLAPSE to
# zoom (or pass an empty value for the full module graph); FE_ARGS forwards
# flags such as --focus.
#
# The cruise writes DOT to a file rather than piping straight into `dot`: in a
# pipeline the shell reports only the last command's status, so a cruise that
# died would still leave make green and the output holding an empty SVG.
FE_COLLAPSE ?= ^src/(core|shell/[^/]+)/
fe-graph:
	@mkdir -p $(DIAGRAM_DIR)
	cd frontend && npx depcruise src \
		--include-only '^src' \
		--output-type dot \
		$(if $(FE_COLLAPSE),--collapse '$(FE_COLLAPSE)',) \
		$(FE_ARGS) \
		--output-to ../$(DIAGRAM_DIR)/frontend.dot
	dot -Tsvg -o $(DIAGRAM_DIR)/frontend.svg $(DIAGRAM_DIR)/frontend.dot
	@rm -f $(DIAGRAM_DIR)/frontend.dot
	@echo "wrote $(DIAGRAM_DIR)/frontend.svg"
