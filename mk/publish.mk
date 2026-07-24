# Gates and the push → validate → promote publish flow.
#
# Every push goes to all REGISTRIES under one tag; `edge` is only ever moved
# by promoting a rev that was pushed and validated first:
#   make push-rev       # immutable :<rev>, clean tree only
#   make validate-rev   # full e2e suite against the pushed set
#   make promote-edge   # registry-side retag <rev> -> edge

.PHONY: commit-gate push-gate \
	push-tag push-rev push-archives validate-rev promote-edge

# validate-rev/promote-edge operate on an already-pushed rev: REV must not
# carry -dirty (tree dirty and REV not overridden), because a dirty rev names
# nothing on the registry.
define require_named_rev
	@case "$(REV)" in (*-dirty) echo "tree is dirty — name the pushed rev" \
		"explicitly: make $@ REV=<rev>"; exit 1;; esac
endef

# The commit gate: fast and container-free by design — static checks plus
# every test tier that runs without docker/nix/browsers, so it's cheap enough
# to run before each commit. The heavyweight counterpart is push-gate.
commit-gate:
	$(MAKE) scripts-checks fe-checks be-checks
	$(MAKE) fe-tests be-unit-tests core-integration-tests

# The push gate: everything that must be green before publishing images, in
# one command. Refuses a dirty tree first (require-clean-tree) — images build
# from the working tree (stage-nix-sources even intent-adds untracked files),
# so only a committed state gives the pushed images a commit they correspond
# to. Slow by design: it runs the e2e suite twice, source-run and
# image-backed. The review suite is its own playwright project, so it is named
# here too — source-run only, since an image-backed review adds stack coverage
# the authoring pass already gives. When it passes, the :local images it just
# built are exactly what push-rev will publish.
push-gate: require-clean-tree
	$(MAKE) scripts-checks fe-checks be-checks
	$(MAKE) e2e-bundles
	$(MAKE) fe-tests be-tests
	$(MAKE) e2e-tests
	$(MAKE) e2e-review
	$(MAKE) e2e-tests-stack
	@echo ">> push gate green — publish with: make push-rev"

# Plumbing: tag + push the already-built :local images to every registry
# under IMAGE_TAG. Narrow with REGISTRIES="docker.io/somens" if needed.
push-tag:
	@set -e; for reg in $(REGISTRIES); do for img in $(IMAGES); do \
		docker tag $$img:local $$reg/$$img:$(IMAGE_TAG); \
		docker push $$reg/$$img:$(IMAGE_TAG); \
	done; done

# Immutable publish: build from a committed tree, push under the git rev.
# Never moves `edge`, so it is safe to run at any time.
push-rev: require-clean-tree
	$(MAKE) images
	$(MAKE) push-tag IMAGE_TAG=$(GIT_REV)
	@echo ">> pushed :$(GIT_REV) — next: make validate-rev && make promote-edge"

# Host-side one-shot: load the archives built in the devcontainer, then push
# under the rev stamped by image-archives. Lets the devcontainer build
# credential-free (`make image-archives`) while the host (the only place with
# registry creds) loads and pushes in a single step. Deliberately ignores
# IMAGE_TAG: this is the archive-path twin of push-rev, so it only ever
# publishes an immutable :<rev> — `edge` moves via promote-edge alone.
push-archives: load-image-archives
	@[ -s $(IMAGE_ARCHIVE_DIR)/REV ] \
		|| { echo "no $(IMAGE_ARCHIVE_DIR)/REV stamp — build with 'make image-archives'"; exit 1; }
	$(MAKE) push-tag IMAGE_TAG="$$(cat $(IMAGE_ARCHIVE_DIR)/REV)"
	@echo ">> pushed :$$(cat $(IMAGE_ARCHIVE_DIR)/REV) — next: make validate-rev REV=$$(cat $(IMAGE_ARCHIVE_DIR)/REV) && make promote-edge REV=$$(cat $(IMAGE_ARCHIVE_DIR)/REV)"

# Validate the pushed rev with the full e2e suite before promoting it.
# Like promote-edge, REV defaults to the current HEAD's rev — so the whole
# publish flow runs tag-free from the commit being published.
validate-rev:
	$(require_named_rev)
	$(MAKE) e2e-tests-stack-published IMAGE_TAG=$(REV)

# Promote a validated rev to edge by retagging on the registry — no rebuild,
# no local images involved, so the promoted digests are exactly the validated
# ones. REV defaults to the current HEAD's rev.
promote-edge:
	$(require_named_rev)
	@set -e; for reg in $(REGISTRIES); do for img in $(IMAGES); do \
		echo ">> $$reg/$$img: $(REV) -> edge"; \
		docker buildx imagetools create -t $$reg/$$img:edge $$reg/$$img:$(REV); \
	done; done
