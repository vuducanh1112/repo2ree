IMAGE_CANDIDATE_TOOL := "scripts.publish.image_candidate"
IMAGE_VALIDATION_REGISTRY := env("IMAGE_VALIDATION_REGISTRY", DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
IMAGE_CANDIDATE_REV := env("IMAGE_CANDIDATE_REV", "")

# Images are published as one protocol-compatible set. A candidate is pushed
# under a clean Git revision, resolved to exact digests in every registry, and
# exercised through those digests before its receipt may promote edge. Direct
# pushes intentionally reject edge so validation cannot be bypassed.

# Push the exact local image set certified by publish-gate under its Git revision.
[group('Publishing')]
publish-candidate revision="": _require-clean-tree
    python -m {{ IMAGE_CANDIDATE_TOOL }} push --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --registries {{ quote(REGISTRIES) }} --gate-receipt {{ quote(DEFAULT_PUBLISH_GATE_RECEIPT) }} --require-current

# Load and push a stamped image archive set.
[group('Publishing')]
publish-image-archives archive_dir=DEFAULT_IMAGE_ARCHIVE_DIR: (load-image-archives archive_dir)
    python -m {{ IMAGE_CANDIDATE_TOOL }} push-archive --archive-dir {{ quote(archive_dir) }} --registries {{ quote(REGISTRIES) }}

# Resolve, test, and record one exact registry image candidate.
[group('Publishing')]
validate-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR: _require-clean-tree
    python -m {{ IMAGE_CANDIDATE_TOOL }} validate --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }} --validation-registry {{ quote(IMAGE_VALIDATION_REGISTRY) }} --registries {{ quote(REGISTRIES) }}

# Verify that candidate tags still name the recorded digest set.
[group('Publishing')]
verify-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    python -m {{ IMAGE_CANDIDATE_TOOL }} verify --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }}

# Promote a validated candidate's exact digest set to edge.
[group('Publishing')]
promote-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    python -m {{ IMAGE_CANDIDATE_TOOL }} promote --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }}
