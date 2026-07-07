# End-to-end tests: bundles, source-run and image-backed stacks, playwright.
#
# Stack orchestration (backend + agent + playwright, readiness polling,
# teardown, the coverage variant) lives in scripts/e2e-stack.sh.

.PHONY: e2e-bundles \
	e2e-tests e2e-tests-images e2e-tests-stack e2e-tests-stack-published \
	e2e-demo e2e-demo-images e2e-demo-stack e2e-demo-stack-published \
	e2e-demo-code-ocean e2e-coverage \
	stack-up stack-down

# The e2e agent always gets the executor/tools bundles: lean env images (the
# dind default, custom benches) need the injection, and images that ship their
# own /nix (the full workbench) skip it — so this is safe for every tier.
E2E_EXEC_BUNDLE = $(CURDIR)/test-artifacts/exec-bundle
E2E_TOOLS_BUNDLE = $(CURDIR)/test-artifacts/tools-bundle

e2e-bundles: stage-nix-sources
	nix build .#exec-bundle -o $(E2E_EXEC_BUNDLE)
	nix build .#tools-bundle -o $(E2E_TOOLS_BUNDLE)

E2E_STACK = E2E_WORKBENCH_IMAGE='$(E2E_WORKBENCH_IMAGE)' \
	E2E_WORKBENCH_DOCKER_MODE=$(E2E_WORKBENCH_DOCKER_MODE) \
	E2E_EXEC_BUNDLE=$(E2E_EXEC_BUNDLE) \
	E2E_TOOLS_BUNDLE=$(E2E_TOOLS_BUNDLE) \
	scripts/e2e-stack.sh

e2e-tests: e2e-bundles
	$(E2E_STACK) --project e2e

e2e-demo: e2e-bundles
	$(E2E_STACK) --project demo

e2e-demo-code-ocean: e2e-bundles
	$(E2E_STACK) --project code-ocean

# Full-stack e2e coverage: browser (frontend) + server (backend) in one run.
# Reports land in test-artifacts/coverage/e2e/ (backend) and
# frontend/test-artifacts/coverage/ (browser V8). Needs docker + the workbench
# image + browsers, like the e2e suite itself.
e2e-coverage: e2e-bundles
	$(E2E_STACK) --project e2e --coverage

# Image-backed demo stack: the compose control plane on :local tags plus the
# agent container compose deliberately doesn't manage. Expects `make images`
# to have run; lifecycle lives in scripts/image-stack.sh.
stack-up:
	scripts/image-stack.sh up

stack-down:
	scripts/image-stack.sh down

# Run a playwright project against the already-running image-backed stack:
# the Caddy-served frontend (its /api reverse proxy included) instead of a
# vite dev server, and whatever backend + agent images are behind it.
# Nothing is started or stopped here — `make stack-up` first (or start
# compose + agent by hand, see README).
define playwright_against_stack  # $(1) = playwright --project name
	@scripts/image-stack.sh check
	cd frontend && E2E_BASE_URL=$$(../scripts/image-stack.sh frontend-url) \
		npm exec -- playwright test -c playwright.config.ts --project=$(1)
endef

e2e-tests-images:
	$(call playwright_against_stack,e2e)

e2e-demo-images:
	$(call playwright_against_stack,demo)

# One-command flows: build the :local images (or pull the pushed ones),
# stack-up, run against the stack, and tear it down again (also on failure).
define run_then_stack_down  # $(1) = target to run against the running stack
	@status=0; $(MAKE) $(1) || status=$$?; \
	$(MAKE) stack-down; exit $$status
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

e2e-demo-stack:
	$(MAKE) images
	$(MAKE) stack-up
	$(call run_then_stack_down,e2e-demo-images)

e2e-demo-stack-published:
	$(PUBLISHED_STACK) $(MAKE) stack-up
	$(call run_then_stack_down,e2e-demo-images)
