IMAGE_CANDIDATE_TOOL := "scripts.publish.image_candidate"
IMAGE_VALIDATION_REGISTRY := env("IMAGE_VALIDATION_REGISTRY", DOCKERHUB_REGISTRY + "/" + DOCKERHUB_NAMESPACE)
IMAGE_CANDIDATE_REV := env("IMAGE_CANDIDATE_REV", "")

# Images are published as one protocol-compatible set for every platform in
# PUBLISH_PLATFORMS, from one host: the one holding registry credentials. A
# candidate is pushed under a clean Git revision as one index per image over
# each platform's certified images, resolved to exact digests in every
# registry, and exercised through those digests on a machine of each platform
# before its receipts may promote edge. Direct pushes reject edge, so
# validation cannot be bypassed. Another platform's images reach this host as
# archives (`just archive-images` on its machine, `just machine fetch-archives`
# here).

# Push this host's certified images and every fetched platform's archives under the Git revision, as one index per image.
[group('Publishing')]
publish-candidate revision="": _require-clean-tree
    python -m {{ IMAGE_CANDIDATE_TOOL }} push --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --registries {{ quote(REGISTRIES) }} --receipts .receipts --archives {{ quote(DEFAULT_IMAGE_ARCHIVE_DIR) }} --platforms {{ quote(PUBLISH_PLATFORMS) }} --require-current

# Resolve, test, and record one exact registry image candidate on this machine's platform; run it on a machine of each.
[group('Publishing')]
validate-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR: _require-clean-tree
    python -m {{ IMAGE_CANDIDATE_TOOL }} validate --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }} --validation-registry {{ quote(IMAGE_VALIDATION_REGISTRY) }} --registries {{ quote(REGISTRIES) }}

# Verify that every platform in the candidate was validated and its tags still name the validated digests.
[group('Publishing')]
verify-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    python -m {{ IMAGE_CANDIDATE_TOOL }} verify --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }}

# Promote a candidate validated on every platform it carries to edge: edge becomes its index.
[group('Publishing')]
promote-candidate revision="" state_dir=DEFAULT_IMAGE_CANDIDATE_STATE_DIR:
    python -m {{ IMAGE_CANDIDATE_TOOL }} promote --revision {{ quote(revision) }} --configured-revision {{ quote(IMAGE_CANDIDATE_REV) }} --state-dir {{ quote(state_dir) }}
