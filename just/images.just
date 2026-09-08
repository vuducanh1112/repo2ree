# Normal image recipes build and load :local images. Archive recipes are an
# explicit credential-free handoff: build tarballs in the development
# container, then load and publish them on a host with registry credentials.
# The archive set is stamped with its clean Git revision so the host cannot
# accidentally publish it under a different candidate name.

# Create archive output directory.
[private]
_create-image-archive-dir archive_dir:
    @mkdir -p {{ quote(archive_dir) }}

# Make untracked Python sources visible to Nix source filtering.
# Nix only includes Git-visible sources, so intent-to-add lets local builds see
# new Python files without staging their contents or changing the index state.
[private]
_stage-nix-sources:
    @git add -N protocol/src core/src/repo2ree_core/ executor/src/repo2ree_executor provider/src workbench/src nix/provider-image.nix nix/workbench-service.nix nix/clean-py-src.nix docker-support/src 2>/dev/null || true

# Build and load the GUI image.
[group('Images')]
build-gui-image:
    @echo "Building GUI image..."
    nix build .#gui-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-gui:local"

# Build and load the backend image.
[group('Images')]
build-backend-image:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Building backend image..."
    revision=$(scripts/build-revision.sh)
    docker build --provenance=false --build-arg REPO2REE_BUILD_REVISION="$revision" -f docker/demo/backend.Dockerfile -t repo2ree-backend:local .
    echo "Done: repo2ree-backend:local"

# Build and load the self-contained Docker provider image.
[group('Images')]
build-provider-image: _stage-nix-sources
    @echo "Building Docker provider image..."
    nix build .#provider-image
    @echo "Loading into docker..."
    docker load < result
    @echo "Done: repo2ree-provider-docker:local"

# Build and load all deployable images.
[group('Images')]
build-images: build-gui-image build-backend-image build-provider-image

# Regenerate the pinned GUI npm dependency hash.
[group('Images')]
update-gui-npm-hash:
    @echo "Computing npm deps hash from gui/package-lock.json..."
    nix run nixpkgs#prefetch-npm-deps -- gui/package-lock.json > nix/gui-npm-deps.hash
    @echo "Wrote nix/gui-npm-deps.hash: $(cat nix/gui-npm-deps.hash)"

# Build a loadable GUI image archive.
[group('Image archives')]
archive-gui-image archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: (_create-image-archive-dir archive_dir)
    @echo "Building GUI image archive..."
    nix build .#gui-image
    cp -fL result {{ quote(archive_dir + "/repo2ree-gui-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(archive_dir + "/repo2ree-gui-local.tar") }}

# Save the loaded backend image as an archive.
[group('Image archives')]
archive-backend-image archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: build-backend-image (_create-image-archive-dir archive_dir)
    docker save repo2ree-backend:local -o {{ quote(archive_dir + "/repo2ree-backend-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(archive_dir + "/repo2ree-backend-local.tar") }}

# Build a loadable provider image archive.
[group('Image archives')]
archive-provider-image archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: _stage-nix-sources (_create-image-archive-dir archive_dir)
    @echo "Building provider image archive..."
    nix build .#provider-image
    cp -fL result {{ quote(archive_dir + "/repo2ree-provider-docker-local.tar") }}
    @printf 'Wrote %s\n' {{ quote(archive_dir + "/repo2ree-provider-docker-local.tar") }}

# Build and stamp the complete clean-tree image archive set.
[group('Image archives')]
archive-images archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: _require-clean-tree (archive-gui-image archive_dir) (archive-backend-image archive_dir) (archive-provider-image archive_dir)
    @git describe --always > {{ quote(archive_dir + "/IMAGE_CANDIDATE_REV") }}
    @echo ">> stamped candidate: $(cat {{ quote(archive_dir + "/IMAGE_CANDIDATE_REV") }})"

# Load every image from an archive set.
[group('Image archives')]
load-image-archives archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR:
    #!/usr/bin/env bash
    set -euo pipefail
    for image in repo2ree-gui repo2ree-backend repo2ree-provider-docker; do
      docker load -i {{ quote(archive_dir) }}/"$image"-local.tar
    done
