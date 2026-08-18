# Gates and the image-candidate push → validate → promote flow.
#
# Every push goes to all REGISTRIES under one tag; `edge` is only ever moved
# by promoting a rev that was pushed and validated first:
#   make push-image-candidate
#   make validate-image-candidate
#   make promote-image-candidate-to-edge

.PHONY: commit-gate push-gate \
	push-image-set-tag push-image-candidate push-image-archives \
	validate-image-candidate verify-image-candidate promote-image-candidate-to-edge

# Candidate operations need a registry tag, so an implicit dirty revision is
# never meaningful. Validation itself also requires a clean harness below.
define require_named_image_candidate
	@case "$(IMAGE_CANDIDATE_REV)" in (*-dirty) echo "tree is dirty — name the image" \
		"candidate explicitly: make $@ IMAGE_CANDIDATE_REV=<rev>"; exit 1;; esac
endef

IMAGE_CANDIDATE_STATE_DIR ?= .validation-certificates/image-candidates
IMAGE_CANDIDATE_RECEIPT = $(IMAGE_CANDIDATE_STATE_DIR)/$(IMAGE_CANDIDATE_REV).validated
IMAGE_CANDIDATE_PENDING = $(IMAGE_CANDIDATE_RECEIPT).pending
IMAGE_CANDIDATE_TOOL = scripts/image-candidate.sh
IMAGE_VALIDATION_REGISTRY ?= $(DOCKERHUB_REGISTRY)/$(DOCKERHUB_NAMESPACE)

# The commit gate: fast and container-free by design — static checks plus
# every test tier that runs without docker/nix/browsers, so it's cheap enough
# to run before each commit. The heavyweight counterpart is push-gate.
#
# The last step records the tree this run validated, which is what the
# pre-commit hook checks (scripts/commit-gate-stamp.sh). It runs only after
# everything above passed, because make stops the recipe at the first failure —
# a failed gate leaves the previous certificate in place, and a stale
# certificate never matches new content anyway.
commit-gate:
	$(MAKE) scripts-checks gui-checks be-checks
	$(MAKE) gui-tests be-unit-tests core-integration-tests
	scripts/commit-gate-stamp.sh write
	@echo ">> commit gate green — certificate written for the current tree"

# The push gate: everything that must be green before publishing images, in
# one command. Refuses a dirty tree first (require-clean-tree) — images build
# from the working tree (stage-nix-sources even intent-adds untracked files),
# so only a committed state gives the pushed images a commit they correspond
# to. Slow by design: it runs the e2e suite twice, source-run and
# image-backed. The review suite is its own playwright project, so it is named
# here too — source-run only, since an image-backed review adds stack coverage
# the authoring pass already gives. When it passes, the :local images it just
# built are exactly what push-image-candidate will publish.
push-gate: require-clean-tree
	$(MAKE) scripts-checks gui-checks be-checks
	$(MAKE) e2e-bundles
	$(MAKE) gui-tests be-tests
	$(MAKE) gui-contrast-tests gui-screenshot-tests
	$(MAKE) e2e-gui
	$(MAKE) e2e-gui-review
	$(MAKE) e2e-gui-stack-local
	@echo ">> push gate green — publish with: make push-image-candidate"

# Plumbing: tag + push the already-built :local image set to every registry
# under IMAGE_TAG. Narrow with REGISTRIES="docker.io/somens" if needed.
push-image-set-tag:
	@case "$(IMAGE_TAG)" in (""|edge) echo "push-image-set-tag requires a non-edge" \
		"candidate tag; edge moves only through validated promotion"; exit 1;; esac
	@set -e; for reg in $(REGISTRIES); do for img in $(IMAGES); do \
		docker tag "$$img:local" "$$reg/$$img:$(IMAGE_TAG)"; \
		docker push "$$reg/$$img:$(IMAGE_TAG)"; \
	done; done

# Publish a candidate: build from a committed tree and push the image set under
# that tree's Git revision. Never moves `edge`.
push-image-candidate: require-clean-tree
	@[ "$(IMAGE_CANDIDATE_REV)" = "$(GIT_REV)" ] \
		|| { echo "IMAGE_CANDIDATE_REV must name the clean tree being built ($(GIT_REV))"; exit 1; }
	$(MAKE) images
	$(MAKE) push-image-set-tag IMAGE_TAG=$(IMAGE_CANDIDATE_REV)
	@echo ">> pushed image candidate :$(IMAGE_CANDIDATE_REV)"
	@echo ">> next: make validate-image-candidate && make promote-image-candidate-to-edge"

# Host-side one-shot: load archives built in the devcontainer, then push under
# the candidate revision stamped by image-archives. Lets the devcontainer build
# credential-free (`make image-archives`) while the host (the only place with
# registry creds) loads and pushes in a single step. Deliberately ignores
# IMAGE_TAG: like push-image-candidate, it can never move `edge`.
push-image-archives: load-image-archives
	@[ -s $(IMAGE_ARCHIVE_DIR)/IMAGE_CANDIDATE_REV ] \
		|| { echo "no IMAGE_CANDIDATE_REV stamp — build with 'make image-archives'"; exit 1; }
	$(MAKE) push-image-set-tag IMAGE_TAG="$$(cat $(IMAGE_ARCHIVE_DIR)/IMAGE_CANDIDATE_REV)"
	@echo ">> pushed image candidate :$$(cat $(IMAGE_ARCHIVE_DIR)/IMAGE_CANDIDATE_REV)"
	@echo ">> next: make validate-image-candidate IMAGE_CANDIDATE_REV=$$(cat $(IMAGE_ARCHIVE_DIR)/IMAGE_CANDIDATE_REV)"

# Resolve every registry's revision tag into one pending receipt, require one
# identical digest per component, then run both GUI suites against exact
# @sha256 references. The receipt becomes valid only after both suites pass.
validate-image-candidate: require-clean-tree
	$(require_named_image_candidate)
	@set -e; pending='$(IMAGE_CANDIDATE_PENDING)'; trap 'rm -f "$$pending"' EXIT; \
	$(IMAGE_CANDIDATE_TOOL) resolve '$(IMAGE_CANDIDATE_REV)' \
		"$$pending" $(REGISTRIES); \
	eval "$$($(IMAGE_CANDIDATE_TOOL) environment \
		"$$pending" '$(IMAGE_VALIDATION_REGISTRY)')"; \
	export STACK_GUI_IMAGE STACK_BACKEND_IMAGE STACK_AGENT_IMAGE; \
	$(MAKE) e2e-gui-stack-published; \
	$(MAKE) e2e-gui-review-stack-published; \
	mv "$$pending" '$(IMAGE_CANDIDATE_RECEIPT)'
	@echo ">> image candidate $(IMAGE_CANDIDATE_REV) validated — receipt written"

# Read-only proof that the candidate tags still name the validated digest set.
verify-image-candidate:
	$(require_named_image_candidate)
	$(IMAGE_CANDIDATE_TOOL) verify '$(IMAGE_CANDIDATE_REV)' '$(IMAGE_CANDIDATE_RECEIPT)'

# Move every registry's edge tag from the recorded @sha256 references. The
# tool first verifies the complete receipt and then verifies each written tag.
promote-image-candidate-to-edge:
	$(require_named_image_candidate)
	$(IMAGE_CANDIDATE_TOOL) promote '$(IMAGE_CANDIDATE_REV)' '$(IMAGE_CANDIDATE_RECEIPT)'
	@echo ">> promoted validated image candidate $(IMAGE_CANDIDATE_REV) to edge"
