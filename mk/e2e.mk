# End-to-end tests: bundles, source-run and image-backed stacks, playwright.
#
# Every suite here brings up a real stack — backend, agent, and a workbench
# container. The browser suites that need only a vite dev server are GUI suites
# and live in mk/gui-tests.mk.
#
# Stack orchestration (backend + agent + playwright, readiness polling,
# teardown, the coverage variant) lives in scripts/test-stack/e2e-stack.sh.

.PHONY: e2e-bundles \
	e2e-gui e2e-gui-on-stack e2e-gui-stack-local e2e-gui-stack-published \
	e2e-gui-review e2e-gui-review-on-stack e2e-gui-review-stack-local e2e-gui-review-stack-published \
	demo-gui demo-gui-on-stack demo-gui-stack-local demo-gui-stack-published \
	demo-api demo-api-on-stack demo-api-stack-local demo-api-stack-published \
	demo-gui-code-ocean \
	stack-up stack-down stack-clean workbench-clean store-gc

# The e2e agent always gets the executor/tools bundles: lean env images (the
# dind default, custom benches) need the injection, and images that ship their
# own /nix (the full workbench) skip it — so this is safe for every tier.
#
# Under dist/, with the repo's other built output, rather than test-artifacts/:
# these are `nix build -o` symlinks, which means they are *GC roots* holding
# their store closures alive, and they are an input to the suites rather than
# something a suite produced. test-artifacts/ is the disposable half of the
# tree — emptying it should never cost a rebuild, let alone let the next
# `make store-gc` collect what the stack is about to inject.
E2E_BUNDLE_DIR = $(CURDIR)/dist/bundles
E2E_EXEC_BUNDLE = $(E2E_BUNDLE_DIR)/exec
E2E_TOOLS_BUNDLE = $(E2E_BUNDLE_DIR)/tools

# mkdir first: `nix build -o` writes the symlink but will not create its parent.
e2e-bundles: stage-nix-sources
	@mkdir -p $(E2E_BUNDLE_DIR)
	nix build .#exec-bundle -o $(E2E_EXEC_BUNDLE)
	nix build .#tools-bundle -o $(E2E_TOOLS_BUNDLE)

E2E_STACK = E2E_WORKBENCH_IMAGE='$(E2E_WORKBENCH_IMAGE)' \
	E2E_WORKBENCH_DOCKER_MODE=$(E2E_WORKBENCH_DOCKER_MODE) \
	E2E_EXEC_BUNDLE=$(E2E_EXEC_BUNDLE) \
	E2E_TOOLS_BUNDLE=$(E2E_TOOLS_BUNDLE) \
	scripts/test-stack/e2e-stack.sh

# Workbench agents the stack connects. The multi-agent specs need >= 2 and
# skip themselves on smaller stacks; raise it for stress runs
# (E2E_AGENTS=10 make e2e-gui). Demos stay single-agent — they show one lab.
E2E_AGENTS ?= 2

# Suites are named <purpose>-<interface>: `e2e-` is a regression suite, `demo-` a
# demonstration; `-gui` is browser-driven through playwright, `-api` drives the
# same stack over HTTP with no browser. The name is also the playwright project
# and the coverage tier — one word for one thing, so a report cannot be labelled
# with a suite that did not produce it (see scripts/test-stack/e2e-stack.sh).
#
# Every source-run suite here is measured; there is no unmeasured variant and no
# --coverage flag. What they measure is the *backend* —
# test-artifacts/coverage/python/<suite>/. The browser is not measured by these
# runs (see scripts/test-stack/e2e-stack.sh); UI coverage comes from component tests in the
# `node` tier.
#
# The image-backed variants below (-on-stack, -stack-local, -stack-published) are
# unmeasured and always will be: those processes run inside containers where the
# host's coverage cannot see them. That is the division of labour, not a gap —
# the measured source-run path produces the numbers, and the image path proves
# the un-instrumented topology works.

e2e-gui: e2e-bundles
	$(E2E_STACK) --project e2e-gui --agents $(E2E_AGENTS)

# The reviewer-side suite, on a stack of its own. Kept out of `e2e-gui` (which
# covers authoring) so a reviewer-facing change is one command to validate, and
# so neither suite pays for the other — every spec provisions a real workbench.
# Single-agent: reviews reproduce in their own namespace, never on a second lab.
e2e-gui-review: e2e-bundles
	$(E2E_STACK) --project e2e-gui-review --agents 1

demo-gui: e2e-bundles
	$(E2E_STACK) --project demo-gui

# Pure-API agent walkthrough: the same live backend+agent stack, driven over
# HTTP by a curl/jq client instead of a browser. It walks the full authoring
# lifecycle (create -> upload -> seal -> download -> delete) and records the
# session as an asciinema .cast — the pure-API counterpart of the narrated
# browser demo's video. A demonstration, not a gate: no gate runs it, and the
# walkthrough's assertions exist so a broken demo fails loudly rather than
# recording a lie.
#
# Recording here is cheap and unintrusive (unlike playwright video, which is why
# the browser e2e/demo split exists), so there is one target, not two.
# Render the cast to SVG/GIF with `agg $(API_DEMO_CAST) api-agent-walkthrough.gif`.
# A recording is a poor standalone document, so the run also derives a chaptered
# markdown transcript from the .cast — the same artifact in written form.
API_DEMO_CAST ?= $(CURDIR)/test-artifacts/casts/api-agent-walkthrough.cast
API_DEMO_TRANSCRIPT ?= $(API_DEMO_CAST:.cast=.md)
demo-api: e2e-bundles
	@mkdir -p $(dir $(API_DEMO_CAST))
	$(E2E_STACK) --script $(CURDIR)/api/tests/e2e/api_agent_walkthrough.py \
		--tier demo-api --record $(API_DEMO_CAST)
	python3 $(CURDIR)/api/tests/e2e/render_cast_transcript.py $(API_DEMO_CAST) $(API_DEMO_TRANSCRIPT)

demo-gui-code-ocean: e2e-bundles
	$(E2E_STACK) --project demo-gui-code-ocean

# Image-backed demo stack: the compose control plane on :local tags plus the
# agent container compose deliberately doesn't manage. Expects `make images`
# to have run; lifecycle lives in scripts/test-stack/image-stack.sh.
stack-up:
	STACK_AGENTS=$(E2E_AGENTS) scripts/test-stack/image-stack.sh up

# Stop the stack, keeping its volumes: a demo stack picks up where it left off,
# and the agent keeps its identity.
stack-down:
	scripts/test-stack/image-stack.sh down

# Stop the stack and drop everything it stored: the compose volumes plus any
# workbench containers/volumes the agent left behind. What the one-command test
# flows below use — their REEs die with the backend volume, so keeping either
# only leaks disk.
stack-clean:
	scripts/test-stack/image-stack.sh down --volumes

# Just the workbench leftovers (containers, per-REE volumes, and the anonymous
# volumes the bench image declares), for cleaning up after a source-run stack or
# an interrupted run. `STORE=1` additionally drops every bundle store volume —
# the live one included, so the next provision re-copies the closure.
workbench-clean:
	scripts/test-stack/workbench-cleanup.sh $(if $(STORE),--store,)

# Evict the bundle store cache: ~450MB per volume, one orphaned every time the
# executor or tools bundle is rebuilt, so it grows without bound on a dev
# machine. Drops those no container references and no build has recreated in
# STORE_GC_DAYS, keeping this checkout's live bundle so runs still start warm.
# Deliberately not part of any e2e teardown — evicting a cache the next run
# needs is exactly what a test target should not do behind your back.
STORE_GC_DAYS ?= 14
store-gc:
	scripts/test-stack/workbench-cleanup.sh --store-gc $(STORE_GC_DAYS)

# Run a playwright project against the already-running image-backed stack:
# the Caddy-served GUI (its /api reverse proxy included) instead of a
# vite dev server, and whatever backend + agent images are behind it.
# Nothing is started or stopped here — `make stack-up` first (or start
# compose + agent by hand, see README).
define playwright_against_stack  # $(1) = playwright --project name
	@scripts/test-stack/image-stack.sh check
	cd gui && E2E_BASE_URL=$$(../scripts/test-stack/image-stack.sh gui-url) \
		npm exec -- playwright test -c playwright.config.ts --project=$(1)
endef

e2e-gui-on-stack:
	$(call playwright_against_stack,e2e-gui)

e2e-gui-review-on-stack:
	$(call playwright_against_stack,e2e-gui-review)

demo-gui-on-stack:
	$(call playwright_against_stack,demo-gui)

# The API walkthrough against the already-running image-backed stack — the
# pure-API analog of e2e-gui-on-stack. A validation run, not a demo run, so it
# doesn't record; the .cast/transcript demo artifacts come from `demo-api`.
demo-api-on-stack:
	@scripts/test-stack/image-stack.sh check
	API_BASE_URL=$$(scripts/test-stack/image-stack.sh api-url) \
		api/tests/e2e/api_agent_walkthrough.py

# One-command flows: build the :local images (or pull the pushed ones),
# stack-up, run against the stack, and tear it down again (also on failure).
# These own the whole stack lifecycle, so they clean up after themselves —
# volumes and leftover workbenches included.
define run_then_stack_down  # $(1) = target to run against the running stack
	@status=0; $(MAKE) $(1) || status=$$?; \
	$(MAKE) stack-clean; exit $$status
endef

# The pushed images default to the Docker Hub set at IMAGE_TAG; use
# IMAGE_TAG=<rev> to validate a freshly pushed rev before promoting it.
PUBLISHED_STACK = STACK_IMAGE_REPO=$(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE) \
	STACK_IMAGE_TAG=$(IMAGE_TAG)

# Three ways to reach an image-backed stack, named for who provides it:
# `-on-stack` attaches to one you already brought up, `-stack-local` builds the
# :local images itself, and `-stack-published` pulls the pushed ones. Only
# `-stack-local` builds anything.
#
# The two lifecycle wrappers are the same three lines for every suite, and they
# are written out per suite on purpose rather than generated from a suite list:
# a target you cannot grep for costs more, every time you look for it, than the
# duplication saves. The shared parts are already factored into the two defines
# above, which is where the repetition actually belongs.

e2e-gui-stack-local:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-gui-on-stack)

e2e-gui-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-gui-on-stack)

e2e-gui-review-stack-local:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-gui-review-on-stack)

e2e-gui-review-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-gui-review-on-stack)

demo-gui-stack-local:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,demo-gui-on-stack)

demo-gui-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,demo-gui-on-stack)

demo-api-stack-local:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,demo-api-on-stack)

demo-api-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,demo-api-on-stack)
