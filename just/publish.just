IMAGE_CANDIDATE_STATE_DIR := env("IMAGE_CANDIDATE_STATE_DIR", ".validation-certificates/image-candidates")
IMAGE_CANDIDATE_TOOL := "scripts/publish/image-candidate.sh"
IMAGE_VALIDATION_REGISTRY := env("IMAGE_VALIDATION_REGISTRY", DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)

# Images are published as one protocol-compatible set. A candidate is pushed
# under a clean Git revision, resolved to exact digests in every registry, and
# exercised through those digests before its receipt may promote edge. Direct
# pushes intentionally reject edge so validation cannot be bypassed.

[private]
_require-current-image-candidate IMAGE_CANDIDATE_REV:
    #!/usr/bin/env bash
    set -euo pipefail
    git_rev="$(git describe --always --dirty)"
    candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$git_rev}"
    [[ "$candidate" == "$git_rev" ]] || { echo "IMAGE_CANDIDATE_REV must name the clean tree being built ($git_rev)"; exit 1; }

# Run the fast, container-free pre-commit gate and certify the tree.
# The certificate records the exact tree only after every prerequisite passes;
# the pre-commit hook performs the cheap content comparison later.
[group('Release gates')]
commit-gate: docs-checks scripts-checks gui-checks be-checks gui-tests be-unit-tests core-integration-tests
    scripts/publish/commit-gate-stamp.sh write
    @echo ">> commit gate green — certificate written for the current tree"

# Run every check required before publishing the local image set.
# This intentionally exercises both measured source runs and the uninstrumented
# local-image topology before any candidate is pushed.
[group('Release gates')]
push-gate: require-clean-tree scripts-checks gui-checks be-checks e2e-bundles gui-tests be-tests gui-accessibility-tests gui-screenshot-tests e2e-gui e2e-gui-review e2e-gui-stack-local
    @echo ">> push gate green — publish with: just push-image-candidate"

# Tag and push the loaded local image set to every registry.
[group('Publishing')]
push-image-set-tag IMAGE_TAG=IMAGE_TAG REGISTRIES=REGISTRIES:
    #!/usr/bin/env bash
    set -euo pipefail
    image_tag={{ quote(IMAGE_TAG) }}
    registries_text={{ quote(REGISTRIES) }}
    read -r -a registries <<< "$registries_text"
    case "$image_tag" in ''|edge) echo "push-image-set-tag requires a non-edge candidate tag; edge moves only through validated promotion"; exit 1;; esac
    for registry in "${registries[@]}"; do
      for image in repo2ree-gui repo2ree-backend repo2ree-agent; do
        docker tag "$image:local" "$registry/$image:$image_tag"
        docker push "$registry/$image:$image_tag"
      done
    done

# Build a clean-tree image candidate and push it under its Git revision.
[group('Publishing')]
push-image-candidate IMAGE_CANDIDATE_REV=env("IMAGE_CANDIDATE_REV", "") REGISTRIES=REGISTRIES: require-clean-tree (_require-current-image-candidate IMAGE_CANDIDATE_REV) images
    #!/usr/bin/env bash
    set -euo pipefail
    git_rev="$(git describe --always --dirty)"
    candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$git_rev}"
    registries_text={{ quote(REGISTRIES) }}
    read -r -a registries <<< "$registries_text"
    for registry in "${registries[@]}"; do
      for image in repo2ree-gui repo2ree-backend repo2ree-agent; do
        docker tag "$image:local" "$registry/$image:$candidate"
        docker push "$registry/$image:$candidate"
      done
    done
    echo ">> pushed image candidate :$candidate"
    echo ">> next: just validate-image-candidate $candidate && just promote-image-candidate-to-edge $candidate"

# Load and push a stamped image archive set.
[group('Publishing')]
push-image-archives IMAGE_ARCHIVE_DIR=IMAGE_ARCHIVE_DIR REGISTRIES=REGISTRIES: (load-image-archives IMAGE_ARCHIVE_DIR)
    #!/usr/bin/env bash
    set -euo pipefail
    stamp={{ quote(IMAGE_ARCHIVE_DIR + "/IMAGE_CANDIDATE_REV") }}
    test -s "$stamp" || { echo "no IMAGE_CANDIDATE_REV stamp — build with 'just image-archives'"; exit 1; }
    candidate="$(cat "$stamp")"
    registries_text={{ quote(REGISTRIES) }}
    read -r -a registries <<< "$registries_text"
    for registry in "${registries[@]}"; do
      for image in repo2ree-gui repo2ree-backend repo2ree-agent; do
        docker tag "$image:local" "$registry/$image:$candidate"
        docker push "$registry/$image:$candidate"
      done
    done
    echo ">> pushed image candidate :$candidate"
    echo ">> next: just validate-image-candidate $candidate"

# Resolve, test, and record one exact registry image candidate.
[group('Publishing')]
validate-image-candidate IMAGE_CANDIDATE_REV=env("IMAGE_CANDIDATE_REV", "") REGISTRIES=REGISTRIES IMAGE_VALIDATION_REGISTRY=IMAGE_VALIDATION_REGISTRY: require-clean-tree
    #!/usr/bin/env bash
    set -euo pipefail
    candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$(git describe --always --dirty)}"
    case "$candidate" in *-dirty) echo "tree is dirty — name the image candidate explicitly: just validate-image-candidate <rev>"; exit 1;; esac
    receipt={{ quote(IMAGE_CANDIDATE_STATE_DIR + "/") }}"$candidate.validated"
    pending="$receipt.pending"
    trap 'rm -f "$pending"' EXIT
    candidate_tool={{ quote(IMAGE_CANDIDATE_TOOL) }}
    validation_registry={{ quote(IMAGE_VALIDATION_REGISTRY) }}
    registries_text={{ quote(REGISTRIES) }}
    read -r -a registries <<< "$registries_text"
    "$candidate_tool" resolve "$candidate" "$pending" "${registries[@]}"
    eval "$("$candidate_tool" environment "$pending" "$validation_registry")"
    export STACK_GUI_IMAGE STACK_BACKEND_IMAGE STACK_AGENT_IMAGE
    just --justfile {{ quote(ROOT + "/justfile") }} e2e-gui-stack-published 2 "$validation_registry" "$candidate"
    just --justfile {{ quote(ROOT + "/justfile") }} e2e-gui-review-stack-published "$validation_registry" "$candidate"
    mv "$pending" "$receipt"
    trap - EXIT
    echo ">> image candidate $candidate validated — receipt written"

# Verify that candidate tags still name the recorded digest set.
[group('Publishing')]
verify-image-candidate IMAGE_CANDIDATE_REV=env("IMAGE_CANDIDATE_REV", ""):
    #!/usr/bin/env bash
    set -euo pipefail
    candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$(git describe --always --dirty)}"
    case "$candidate" in *-dirty) echo "tree is dirty — name the image candidate explicitly: just verify-image-candidate <rev>"; exit 1;; esac
    {{ quote(IMAGE_CANDIDATE_TOOL) }} verify "$candidate" {{ quote(IMAGE_CANDIDATE_STATE_DIR + "/") }}"$candidate.validated"

# Promote a validated candidate's exact digest set to edge.
[group('Publishing')]
promote-image-candidate-to-edge IMAGE_CANDIDATE_REV=env("IMAGE_CANDIDATE_REV", ""):
    #!/usr/bin/env bash
    set -euo pipefail
    candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$(git describe --always --dirty)}"
    case "$candidate" in *-dirty) echo "tree is dirty — name the image candidate explicitly: just promote-image-candidate-to-edge <rev>"; exit 1;; esac
    {{ quote(IMAGE_CANDIDATE_TOOL) }} promote "$candidate" {{ quote(IMAGE_CANDIDATE_STATE_DIR + "/") }}"$candidate.validated"
    echo ">> promoted validated image candidate $candidate to edge"
