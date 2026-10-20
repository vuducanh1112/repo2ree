IMAGE_CANDIDATE_TOOL := "scripts/publish/image_candidate.py"
IMAGE_VALIDATION_REGISTRY := env("IMAGE_VALIDATION_REGISTRY", DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
IMAGE_CANDIDATE_REV := env("IMAGE_CANDIDATE_REV", "")

# Images are published as one protocol-compatible set. A candidate is pushed
# under a clean Git revision, resolved to exact digests in every registry, and
# exercised through those digests before its receipt may promote edge. Direct
# pushes intentionally reject edge so validation cannot be bypassed.

# The certificate records the exact tree only after every prerequisite passes;
# the pre-commit hook performs the cheap content comparison later.
# Run the fast checks, documentation build, and unit tests, then certify the tree.
[group('Release gates')]
commit-gate: check build-docs test-unit
    python scripts/publish/commit_gate_stamp.py write
    @echo ">> commit gate green — certificate written for the current tree"

# Require the current clean content to have passed the commit gate.
[private]
_require-current-commit-gate:
    python scripts/publish/commit_gate_stamp.py verify

# A test is accepted when it passed (or is a strict xfail) and its behaviour passed, or left
# exactly the rules conformance/expected-verdicts.toml excuses for it open.
# Run the per-test e2e tiers on HEAD, judge every test's behaviour, and certify HEAD's tree.
[group('Release gates')]
behaviour-gate: _require-clean-tree
    #!/usr/bin/env bash
    set -euo pipefail
    runs=()
    for tier in test-e2e-system test-e2e-gui-instant; do
        log=$(mktemp)
        just "$tier" 2>&1 | tee "$log" || true
        run=$(sed -n 's/^>> per-test run: //p' "$log" | tail -n 1)
        rm -f "$log"
        [[ -n "$run" ]] || { echo ">> $tier left no per-test run" >&2; exit 1; }
        runs+=("$run")
    done
    python scripts/publish/behaviour_gate.py certify "${runs[@]}"

# Require a behaviour receipt for HEAD's clean tree.
[private]
_require-current-behaviour-receipt:
    python scripts/publish/behaviour_gate.py verify

# Run the complete pre-publish gate and certify the local image set.
[group('Release gates')]
publish-gate: _require-clean-tree _require-current-commit-gate _require-current-behaviour-receipt test-backend-integration test-gui-accessibility test-gui-screenshots test-e2e-gui test-e2e-review build-images
    #!/usr/bin/env bash
    set -euo pipefail
    python scripts/test-stack/run_image_suite.py --suite e2e-gui --compute-locations {{ quote(DEFAULT_STACK_LOCATIONS) }} --images local
    python scripts/test-stack/run_image_suite.py --suite e2e-gui-review --compute-locations 1 --images local
    revision=$(git describe --always)
    python scripts/publish/publish_gate_receipt.py write {{ quote(DEFAULT_PUBLISH_GATE_RECEIPT) }} "$revision"
    echo ">> publish gate green — certified local image set for $revision"
    echo ">> publish with: just publish-candidate"

# Push the exact local image set certified by publish-gate under its Git revision.
[group('Publishing')]
publish-candidate revision="": _require-clean-tree
    python {{ quote(IMAGE_CANDIDATE_TOOL) }} push --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --registries {{ quote(REGISTRIES) }} --gate-receipt {{ quote(DEFAULT_PUBLISH_GATE_RECEIPT) }} --require-current

# Load and push a stamped image archive set.
[group('Publishing')]
publish-image-archives archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: (load-image-archives archive_dir)
    python {{ quote(IMAGE_CANDIDATE_TOOL) }} push-archive --archive-dir {{ quote(archive_dir) }} --registries {{ quote(REGISTRIES) }}

# Resolve, test, and record one exact registry image candidate.
[group('Publishing')]
validate-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR: _require-clean-tree
    python {{ quote(IMAGE_CANDIDATE_TOOL) }} validate --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }} --validation-registry {{ quote(IMAGE_VALIDATION_REGISTRY) }} --registries {{ quote(REGISTRIES) }}

# Verify that candidate tags still name the recorded digest set.
[group('Publishing')]
verify-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    python {{ quote(IMAGE_CANDIDATE_TOOL) }} verify --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }}

# Promote a validated candidate's exact digest set to edge.
[group('Publishing')]
promote-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    python {{ quote(IMAGE_CANDIDATE_TOOL) }} promote --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }}
