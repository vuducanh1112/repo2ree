IMAGE_CANDIDATE_TOOL := "scripts/publish/image-candidate.sh"
PUBLISH_GATE_RECEIPT_TOOL := "scripts/publish/publish-gate-receipt.sh"
IMAGE_VALIDATION_REGISTRY := env("IMAGE_VALIDATION_REGISTRY", DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
IMAGE_CANDIDATE_REV := env("IMAGE_CANDIDATE_REV", "")

# Images are published as one protocol-compatible set. A candidate is pushed
# under a clean Git revision, resolved to exact digests in every registry, and
# exercised through those digests before its receipt may promote edge. Direct
# pushes intentionally reject edge so validation cannot be bypassed.

[private]
_require-current-image-candidate revision:
    #!/usr/bin/env bash
    set -euo pipefail
    git_rev="$(git describe --always --dirty)"
    candidate={{ quote(revision) }}
    configured_candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$configured_candidate}"
    candidate="${candidate:-$git_rev}"
    [[ "$candidate" == "$git_rev" ]] || { echo "IMAGE_CANDIDATE_REV must name the clean tree being built ($git_rev)"; exit 1; }

# The certificate records the exact tree only after every prerequisite passes;
# the pre-commit hook performs the cheap content comparison later.
# Run the fast, container-free pre-commit gate and certify the tree.
[group('Release gates')]
commit-gate: docs-checks scripts-checks gui-checks be-checks gui-tests be-unit-tests core-integration-tests
    scripts/publish/commit-gate-stamp.sh write
    @echo ">> commit gate green — certificate written for the current tree"

# Require the current clean content to have passed the commit gate.
[private]
_require-current-commit-gate:
    scripts/publish/commit-gate-stamp.sh verify

# Run the checks not covered by commit-gate, then build and exercise the exact
# local image set that push-image-candidate will publish. Both image-backed roles
# run here; a receipt is written only after every source and image test passes.
[group('Release gates')]
publish-gate: _require-clean-tree _require-current-commit-gate e2e-bundles api-integration-tests supervisor-integration-tests gui-accessibility-tests gui-screenshot-tests e2e-gui e2e-gui-review images
    #!/usr/bin/env bash
    set -euo pipefail
    just stack-test e2e-gui {{ quote(DEFAULT_STACK_COMPUTE_LOCATIONS) }} local
    just stack-test e2e-gui-review 1 local
    revision=$(git describe --always)
    {{ quote(PUBLISH_GATE_RECEIPT_TOOL) }} write {{ quote(DEFAULT_PUBLISH_GATE_RECEIPT) }} "$revision"
    echo ">> publish gate green — certified local image set for $revision"
    echo ">> publish with: just push-image-candidate"

# Push the exact local image set certified by publish-gate under its Git revision.
[group('Publishing')]
push-image-candidate revision="": _require-clean-tree (_require-current-image-candidate revision)
    #!/usr/bin/env bash
    set -euo pipefail
    git_rev="$(git describe --always --dirty)"
    candidate={{ quote(revision) }}
    configured_candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$configured_candidate}"
    candidate="${candidate:-$git_rev}"
    receipt={{ quote(DEFAULT_PUBLISH_GATE_RECEIPT) }}
    {{ quote(PUBLISH_GATE_RECEIPT_TOOL) }} verify "$receipt" "$candidate"
    REGISTRIES={{ quote(REGISTRIES) }} scripts/publish/push-image-set.sh "$candidate" "$receipt"
    echo ">> pushed image candidate :$candidate"
    echo ">> next: just validate-image-candidate $candidate && just promote-image-candidate-to-edge $candidate"

# Load and push a stamped image archive set.
[group('Publishing')]
push-image-archives archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: (load-image-archives archive_dir)
    #!/usr/bin/env bash
    set -euo pipefail
    stamp={{ quote(archive_dir + "/IMAGE_CANDIDATE_REV") }}
    test -s "$stamp" || { echo "no IMAGE_CANDIDATE_REV stamp — build with 'just image-archives'"; exit 1; }
    candidate="$(cat "$stamp")"
    REGISTRIES={{ quote(REGISTRIES) }} scripts/publish/push-image-set.sh "$candidate"
    echo ">> pushed image candidate :$candidate"
    echo ">> next: just validate-image-candidate $candidate"

# Resolve, test, and record one exact registry image candidate.
[group('Publishing')]
validate-image-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR: _require-clean-tree
    #!/usr/bin/env bash
    set -euo pipefail
    candidate={{ quote(revision) }}
    configured_candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$configured_candidate}"
    candidate="${candidate:-$(git describe --always --dirty)}"
    case "$candidate" in *-dirty) echo "tree is dirty — name the image candidate explicitly: just validate-image-candidate <rev>"; exit 1;; esac
    receipt={{ quote(state_dir + "/") }}"$candidate.validated"
    pending="$receipt.pending"
    trap 'rm -f "$pending"' EXIT
    candidate_tool={{ quote(IMAGE_CANDIDATE_TOOL) }}
    validation_registry={{ quote(IMAGE_VALIDATION_REGISTRY) }}
    registries_text={{ quote(REGISTRIES) }}
    read -r -a registries <<< "$registries_text"
    "$candidate_tool" resolve "$candidate" "$pending" "${registries[@]}"
    eval "$("$candidate_tool" environment "$pending" "$validation_registry")"
    export STACK_GUI_IMAGE STACK_BACKEND_IMAGE STACK_PROVIDER_IMAGE
    scripts/test-stack/run-image-suite.sh --suite e2e-gui --compute-locations 2 --images published --repository "$validation_registry" --tag "$candidate"
    scripts/test-stack/run-image-suite.sh --suite e2e-gui-review --compute-locations 1 --images published --repository "$validation_registry" --tag "$candidate"
    mv "$pending" "$receipt"
    trap - EXIT
    echo ">> image candidate $candidate validated — receipt written"

# Verify that candidate tags still name the recorded digest set.
[group('Publishing')]
verify-image-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    #!/usr/bin/env bash
    set -euo pipefail
    candidate={{ quote(revision) }}
    configured_candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$configured_candidate}"
    candidate="${candidate:-$(git describe --always --dirty)}"
    case "$candidate" in *-dirty) echo "tree is dirty — name the image candidate explicitly: just verify-image-candidate <rev>"; exit 1;; esac
    {{ quote(IMAGE_CANDIDATE_TOOL) }} verify "$candidate" {{ quote(state_dir + "/") }}"$candidate.validated"

# Promote a validated candidate's exact digest set to edge.
[group('Publishing')]
promote-image-candidate-to-edge revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    #!/usr/bin/env bash
    set -euo pipefail
    candidate={{ quote(revision) }}
    configured_candidate={{ quote(IMAGE_CANDIDATE_REV) }}
    candidate="${candidate:-$configured_candidate}"
    candidate="${candidate:-$(git describe --always --dirty)}"
    case "$candidate" in *-dirty) echo "tree is dirty — name the image candidate explicitly: just promote-image-candidate-to-edge <rev>"; exit 1;; esac
    {{ quote(IMAGE_CANDIDATE_TOOL) }} promote "$candidate" {{ quote(state_dir + "/") }}"$candidate.validated"
    echo ">> promoted validated image candidate $candidate to edge"
