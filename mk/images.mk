# Image builds: the normal build-and-load path and the opt-in archive path.

.PHONY: image-archive-dir stage-nix-sources \
	gui-image backend-image agent-image images gui-npm-hash \
	gui-image-archive backend-image-archive agent-image-archive \
	image-archives load-image-archives

image-archive-dir:
	@mkdir -p $(IMAGE_ARCHIVE_DIR)

# Nix only sees files git tracks, so intent-add the untracked python sources
# before any nix image/bundle build that packages them.
stage-nix-sources:
	@git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor agent/src 2>/dev/null || true

# ---- Normal path: build and load straight into the local Docker. ----
# These do NOT write tarballs; use the *-image-archive targets for that.

gui-image:
	@echo "Building GUI image..."
	nix build .#gui-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-gui:local"

# Backend is a Dockerfile build (uv sync at image-build time), not a nix image,
# so `docker build` already loads it into the local Docker. The :local tag marks
# never-pushed workbench builds (the compose local-override path uses it);
# published channels are minted at push time.
# --provenance=false: the default SLSA attestation embeds a per-build
# invocation id + timestamps into the image index, so without it the image
# digest changes on every build even when all layers are cache hits.
backend-image:
	@echo "Building backend image..."
	docker build --provenance=false -f docker/demo/backend.Dockerfile -t repo2ree-backend:local .
	@echo "Done: repo2ree-backend:local"

# The agent image is the self-carrying deployable third parties run: agent
# process + embedded executor/tools bundles (see nix/agent-image.nix).
agent-image: stage-nix-sources
	@echo "Building agent image..."
	nix build .#agent-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-agent:local"

images: gui-image backend-image agent-image

# Regenerate the pinned npm-deps hash from gui/package-lock.json. Run this
# manually after any lockfile change (it is intentionally NOT a build prereq, so
# building an image never re-prefetches or rewrites this tracked file). It uses
# prefetch-npm-deps (the same tool buildNpmPackage uses), so it can't disagree
# with the build.
gui-npm-hash:
	@echo "Computing npm deps hash from gui/package-lock.json..."
	nix run nixpkgs#prefetch-npm-deps -- gui/package-lock.json > nix/gui-npm-deps.hash
	@echo "Wrote nix/gui-npm-deps.hash: $$(cat nix/gui-npm-deps.hash)"

# ---- Archive path (opt-in): write loadable tarballs under IMAGE_ARCHIVE_DIR. ----
# For building inside the dev container and loading/pushing from the host Docker
# client: `make image-archives`, copy dist/images to the host, then
# `make push-image-archives` there. Kept off the normal images/push-* path so a
# plain build/push writes no tarballs.

gui-image-archive: | image-archive-dir
	@echo "Building GUI image archive..."
	nix build .#gui-image
	cp -fL result $(IMAGE_ARCHIVE_DIR)/repo2ree-gui-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-gui-local.tar"

# Backend reuses the already-built/loaded image, so there's no second build.
backend-image-archive: backend-image | image-archive-dir
	docker save repo2ree-backend:local -o $(IMAGE_ARCHIVE_DIR)/repo2ree-backend-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-backend-local.tar"

agent-image-archive: stage-nix-sources | image-archive-dir
	@echo "Building agent image archive..."
	nix build .#agent-image
	cp -fL result $(IMAGE_ARCHIVE_DIR)/repo2ree-agent-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-agent-local.tar"

# Refuses a dirty tree (require-clean-tree): the archives are the publish path
# off the devcontainer, so they must correspond to a commit. The candidate
# revision is stamped into the archive dir so the host pushes exactly that set.
image-archives: require-clean-tree gui-image-archive backend-image-archive agent-image-archive
	@git describe --always > $(IMAGE_ARCHIVE_DIR)/IMAGE_CANDIDATE_REV
	@echo ">> stamped candidate: $$(cat $(IMAGE_ARCHIVE_DIR)/IMAGE_CANDIDATE_REV)"

load-image-archives:
	@set -e; for img in $(IMAGES); do \
		docker load -i $(IMAGE_ARCHIVE_DIR)/$$img-local.tar; \
	done
