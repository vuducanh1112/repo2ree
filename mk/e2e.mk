# End-to-end tests: bundles, source-run and image-backed stacks, playwright.
#
# Stack orchestration (backend + agent + playwright, readiness polling,
# teardown, the coverage variant) lives in scripts/e2e-stack.sh.

.PHONY: e2e-bundles \
	e2e-tests e2e-tests-images e2e-tests-stack e2e-tests-stack-published \
	e2e-review e2e-review-images e2e-review-stack e2e-review-stack-published \
	e2e-demo e2e-demo-images e2e-demo-stack e2e-demo-stack-published \
	e2e-demo-code-ocean coverage-e2e coverage-demo \
	e2e-api e2e-api-images e2e-api-stack e2e-api-stack-published \
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
	scripts/e2e-stack.sh

# Workbench agents the stack connects. The multi-agent specs need >= 2 and
# skip themselves on smaller stacks; raise it for stress runs
# (E2E_AGENTS=10 make e2e-tests). Demos stay single-agent — they show one lab.
E2E_AGENTS ?= 2

e2e-tests: e2e-bundles
	$(E2E_STACK) --project e2e --agents $(E2E_AGENTS)

# The reviewer-side suite, on a stack of its own. Kept out of `e2e-tests` (which
# covers authoring) so a reviewer-facing change is one command to validate, and
# so neither suite pays for the other — every spec provisions a real workbench.
# Single-agent: reviews reproduce in their own namespace, never on a second lab.
e2e-review: e2e-bundles
	$(E2E_STACK) --project review --agents 1

e2e-demo: e2e-bundles
	$(E2E_STACK) --project demo

# Pure-API agent walkthrough: the same live backend+agent stack, driven over
# HTTP by a curl/jq client instead of a browser. Asserts the full authoring
# lifecycle (create -> upload -> seal -> download -> delete), so it is a real CI
# check as well as a demonstrable transcript — and always records the session as
# an asciinema .cast (the pure-API counterpart of the narrated browser `demo`
# video). Recording here is cheap and unintrusive (unlike playwright video, which
# is why the browser e2e/demo split exists), so there is one target, not two.
# Render the cast to SVG/GIF with `agg $(API_DEMO_CAST) api-agent-walkthrough.gif`.
# A recording is a poor standalone document, so the run also derives a chaptered
# markdown transcript from the .cast — the same artifact in written form.
API_DEMO_CAST ?= $(CURDIR)/test-artifacts/api-agent-walkthrough.cast
API_DEMO_TRANSCRIPT ?= $(API_DEMO_CAST:.cast=.md)
e2e-api: e2e-bundles
	$(E2E_STACK) --script $(CURDIR)/api/tests/e2e/api_agent_walkthrough.py --record $(API_DEMO_CAST)
	python3 $(CURDIR)/api/tests/e2e/render_cast_transcript.py $(API_DEMO_CAST) $(API_DEMO_TRANSCRIPT)

e2e-demo-code-ocean: e2e-bundles
	$(E2E_STACK) --project code-ocean

# Full-stack coverage: browser (GUI) + server and agents (backend) in one
# run. Reports land in test-artifacts/coverage/<tier>/ (backend) and
# gui/test-artifacts/coverage/ (browser V8). Needs docker + the workbench
# image + browsers, like the suites themselves.
#
# Two tiers, because the two stacks reach different code: `e2e` is the
# regression suite, `demo` the narrated walkthrough. Each writes its own data
# directory; `make coverage-combined` unions them with the pytest tiers. See
# the tier map at the top of mk/tests.mk.
coverage-e2e: e2e-bundles
	$(E2E_STACK) --project e2e --agents $(E2E_AGENTS) --coverage e2e

coverage-demo: e2e-bundles
	$(E2E_STACK) --project demo --coverage demo

# Image-backed demo stack: the compose control plane on :local tags plus the
# agent container compose deliberately doesn't manage. Expects `make images`
# to have run; lifecycle lives in scripts/image-stack.sh.
stack-up:
	STACK_AGENTS=$(E2E_AGENTS) scripts/image-stack.sh up

# Stop the stack, keeping its volumes: a demo stack picks up where it left off,
# and the agent keeps its identity.
stack-down:
	scripts/image-stack.sh down

# Stop the stack and drop everything it stored: the compose volumes plus any
# workbench containers/volumes the agent left behind. What the one-command test
# flows below use — their REEs die with the backend volume, so keeping either
# only leaks disk.
stack-clean:
	scripts/image-stack.sh down --volumes

# Just the workbench leftovers (containers, per-REE volumes, and the anonymous
# volumes the bench image declares), for cleaning up after a source-run stack or
# an interrupted run. `STORE=1` additionally drops every bundle store volume —
# the live one included, so the next provision re-copies the closure.
workbench-clean:
	scripts/workbench-cleanup.sh $(if $(STORE),--store,)

# Evict the bundle store cache: ~450MB per volume, one orphaned every time the
# executor or tools bundle is rebuilt, so it grows without bound on a dev
# machine. Drops those no container references and no build has recreated in
# STORE_GC_DAYS, keeping this checkout's live bundle so runs still start warm.
# Deliberately not part of any e2e teardown — evicting a cache the next run
# needs is exactly what a test target should not do behind your back.
STORE_GC_DAYS ?= 14
store-gc:
	scripts/workbench-cleanup.sh --store-gc $(STORE_GC_DAYS)

# Run a playwright project against the already-running image-backed stack:
# the Caddy-served GUI (its /api reverse proxy included) instead of a
# vite dev server, and whatever backend + agent images are behind it.
# Nothing is started or stopped here — `make stack-up` first (or start
# compose + agent by hand, see README).
define playwright_against_stack  # $(1) = playwright --project name
	@scripts/image-stack.sh check
	cd gui && E2E_BASE_URL=$$(../scripts/image-stack.sh gui-url) \
		npm exec -- playwright test -c playwright.config.ts --project=$(1)
endef

e2e-tests-images:
	$(call playwright_against_stack,e2e)

e2e-review-images:
	$(call playwright_against_stack,review)

e2e-demo-images:
	$(call playwright_against_stack,demo)

# The API walkthrough against the already-running image-backed stack — the
# pure-API analog of e2e-tests-images. A validation run, not a demo run, so it
# doesn't record; the .cast/transcript demo artifacts come from `e2e-api`.
e2e-api-images:
	@scripts/image-stack.sh check
	API_BASE_URL=$$(scripts/image-stack.sh api-url) \
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

e2e-tests-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-tests-images)

e2e-tests-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-tests-images)

e2e-review-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-review-images)

e2e-review-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-review-images)

e2e-demo-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-demo-images)

e2e-demo-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-demo-images)

e2e-api-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-api-images)

e2e-api-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-api-images)
