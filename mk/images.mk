# Image builds: the normal build-and-load path and the opt-in archive path.

.PHONY: image-archive-dir stage-nix-sources \
	frontend-image backend-image agent-image images frontend-npm-hash \
	frontend-image-archive backend-image-archive agent-image-archive \
	image-archives load-image-archives

image-archive-dir:
	@mkdir -p $(IMAGE_ARCHIVE_DIR)

# Nix only sees files git tracks, so intent-add the untracked python sources
# before any nix image/bundle build that packages them.
stage-nix-sources:
	@git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor agent/src 2>/dev/null || true

# ---- Normal path: build and load straight into the local Docker. ----
# These do NOT write tarballs; use the *-image-archive targets for that.

frontend-image:
	@echo "Building frontend image..."
	nix build .#frontend-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-frontend:local"

# Backend is a Dockerfile build (uv sync at image-build time), not a nix image,
# so `docker build` already loads it into the local Docker. The :local tag marks
# never-pushed workbench builds (the compose local-override path uses it);
# published channels are minted at push time.
backend-image:
	@echo "Building backend image..."
	docker build -f docker/demo/backend.Dockerfile -t repo2ree-backend:local .
	@echo "Done: repo2ree-backend:local"

# The agent image is the self-carrying deployable third parties run: agent
# process + embedded executor/tools bundles (see nix/agent-image.nix).
agent-image: stage-nix-sources
	@echo "Building agent image..."
	nix build .#agent-image
	@echo "Loading into docker..."
	docker load < result
	@echo "Done: repo2ree-agent:local"

images: frontend-image backend-image agent-image

# Regenerate the pinned npm-deps hash from frontend/package-lock.json. Run this
# manually after any lockfile change (it is intentionally NOT a build prereq, so
# building an image never re-prefetches or rewrites this tracked file). It uses
# prefetch-npm-deps (the same tool buildNpmPackage uses), so it can't disagree
# with the build.
frontend-npm-hash:
	@echo "Computing npm deps hash from frontend/package-lock.json..."
	nix run nixpkgs#prefetch-npm-deps -- frontend/package-lock.json > nix/frontend-npm-deps.hash
	@echo "Wrote nix/frontend-npm-deps.hash: $$(cat nix/frontend-npm-deps.hash)"

# ---- Archive path (opt-in): write loadable tarballs under IMAGE_ARCHIVE_DIR. ----
# For building inside the dev container and loading/pushing from the host Docker
# client: `make image-archives`, copy dist/images to the host, then
# `make push-archives` there. Kept off the normal images/push-* path so a
# plain build/push writes no tarballs.

frontend-image-archive: | image-archive-dir
	@echo "Building frontend image archive..."
	nix build .#frontend-image
	cp -fL result $(IMAGE_ARCHIVE_DIR)/repo2ree-frontend-local.tar
	@echo "Wrote $(IMAGE_ARCHIVE_DIR)/repo2ree-frontend-local.tar"

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
# off the devcontainer, so they must correspond to a commit. The rev is stamped
# into the archive dir so the host side pushes under exactly this commit's
# tag — no way to grab a stale IMAGE_TAG by accident.
image-archives: require-clean-tree frontend-image-archive backend-image-archive agent-image-archive
	@git describe --always > $(IMAGE_ARCHIVE_DIR)/REV
	@echo ">> stamped $(IMAGE_ARCHIVE_DIR)/REV: $$(cat $(IMAGE_ARCHIVE_DIR)/REV)"

load-image-archives:
	@set -e; for img in $(IMAGES); do \
		docker load -i $(IMAGE_ARCHIVE_DIR)/$$img-local.tar; \
	done
