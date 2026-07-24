"""Pure description of the on-disk layout of a single REE.

This module is part of the functional core: it contains the data type and
path arithmetic, but performs no filesystem I/O. The imperative shell in
``repo2ree_api.storage`` uses ``ReeLayout`` to know where to read and write.

Layout under ``<storage_root>/<ree_id>/`` (host) or ``/ree/`` (workbench):

    .workspace.json       session metadata
    manifest.json         sealed REE spec sidecar
    sealed.zip            immutable sealed archive (written by seal_ree)
    snapshot.tar.gz       frozen upstream archive
    upload-staging/       staging area for in-flight source uploads
    upstream/             extracted snapshot, treated as read-only
    overlay/              user-added and tool-generated recipe files
    artifacts/            build outputs (runtime, sbom, ...)
    workspace/            materialized view (upstream + overlay) used at build time
    runs/                 per-action logs and immutable receipt history
    receipts/author/      latest successful author receipt per operation

``upstream/`` and ``overlay/`` are the sources of truth; ``workspace/`` is
derived and may be rebuilt at any time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Canonical lexical path checks live in the dependency-free leaf module so the
# domain and experiment layers can share them without an import cycle. Re-export
# here for the storage-layer call sites that have always imported them from
# ``layout``.
from repo2ree_core.path_safety import normalize_workspace_path, validate_relative_path

__all__ = ["normalize_workspace_path", "validate_relative_path"]

# ================================================
# Constants
# ================================================


_METADATA_FILENAME = ".workspace.json"
_MATERIALIZE_MARKER_FILENAME = ".workspace.materialized.json"
_DIGEST_CACHE_FILENAME = ".workspace.digest-cache.json"
_MANIFEST_FILENAME = "manifest.json"
_SEALED_ARCHIVE_FILENAME = "sealed.zip"
_UPLOAD_STAGING_DIRNAME = "upload-staging"

# Public names: shared with the bundle layout (run.sh calls the same scripts).
# REE-owned infra that runs *before* / to build the workspace, so they sit at the
# root alongside manifest/snapshot rather than in the overlay.
ACQUIRE_SCRIPT_FILENAME = "acquire_source.sh"
MATERIALIZE_SCRIPT_FILENAME = "materialize_workspace.sh"

# Public names: shared with the bundle layout so the published REE mirrors
# the on-disk tree. Import these (rather than redefining) to avoid drift.
UPSTREAM_DIRNAME = "upstream"
SNAPSHOT_FILENAME = "snapshot.tar.gz"
OVERLAY_DIRNAME = "overlay"
ARTIFACTS_DIRNAME = "artifacts"
# Produced-results store: per-experiment captured outputs, keyed by name. A
# sibling of ``artifacts/`` (produced, not authored) rather than a subtree of
# it, so the sealed bundle exposes the author baseline at ``ree/results/<name>/``
# for reviewer diffing — deliberately outside ``workspace/`` so a fresh run's
# output at the declared path never collides with the restored baseline.
RESULTS_DIRNAME = "results"
WORKSPACE_DIRNAME = "workspace"
RUNS_DIRNAME = "runs"
RECEIPTS_DIRNAME = "receipts"
AUTHOR_RECEIPTS_DIRNAME = "author"

# Reserved, REE-owned overlay scripts are defined in the leaf
# ``repo2ree_core.reserved_paths`` module so domain, experiment, and storage
# layers can share them without an import cycle.

# Fixed mount point inside every REE workbench container.
WORKBENCH_ROOT = Path("/ree")


# ================================================
# Data Models
# ================================================


@dataclass(frozen=True)
class ReeLayout:
    """The on-disk layout for a single REE, as a value.

    Construct with :meth:`for_ree`; every other attribute is a pure
    derivation from :attr:`root`. No method touches the filesystem.
    """

    root: Path

    @classmethod
    def for_ree(cls, storage_root: Path | str, ree_id: str) -> ReeLayout:
        return cls(root=Path(storage_root) / ree_id)

    @classmethod
    def in_workbench(cls) -> ReeLayout:
        """Layout rooted at the fixed workbench mount point (/ree)."""
        return cls(root=WORKBENCH_ROOT)

    @property
    def metadata(self) -> Path:
        return self.root / _METADATA_FILENAME

    @property
    def manifest(self) -> Path:
        return self.root / _MANIFEST_FILENAME

    @property
    def sealed_archive(self) -> Path:
        return self.root / _SEALED_ARCHIVE_FILENAME

    @property
    def acquire_script(self) -> Path:
        return self.root / ACQUIRE_SCRIPT_FILENAME

    @property
    def materialize_script(self) -> Path:
        return self.root / MATERIALIZE_SCRIPT_FILENAME

    @property
    def snapshot_archive(self) -> Path:
        return self.root / SNAPSHOT_FILENAME

    @property
    def digest_cache(self) -> Path:
        """Stat-keyed cache of the runtime artifact's digest (see ``receipts``)."""
        return self.root / _DIGEST_CACHE_FILENAME

    @property
    def materialize_marker(self) -> Path:
        """What the workspace was last materialized from (see ``receipts``).

        The ``.workspace`` prefix keeps it under the reserved-control-name
        umbrella, so file enumeration and path access already skip it.
        """
        return self.root / _MATERIALIZE_MARKER_FILENAME

    @property
    def upload_staging(self) -> Path:
        return self.root / _UPLOAD_STAGING_DIRNAME

    @property
    def upstream(self) -> Path:
        return self.root / UPSTREAM_DIRNAME

    @property
    def overlay(self) -> Path:
        return self.root / OVERLAY_DIRNAME

    @property
    def artifacts(self) -> Path:
        return self.root / ARTIFACTS_DIRNAME

    @property
    def results(self) -> Path:
        return self.root / RESULTS_DIRNAME

    def results_dir(self, name: str) -> Path:
        """Produced-results store for a single experiment, keyed by its name.

        Experiment names are already constrained to a safe single path segment
        (``EXPERIMENT_NAME_PATTERN``); the resolver rejects anything else.
        """
        return self._resolve_under(self.results, name)

    @property
    def workspace(self) -> Path:
        return self.root / WORKSPACE_DIRNAME

    @property
    def runs(self) -> Path:
        return self.root / RUNS_DIRNAME

    @property
    def receipts(self) -> Path:
        return self.root / RECEIPTS_DIRNAME

    @property
    def author_receipts(self) -> Path:
        """Selected author evidence: latest successful receipt per step."""
        return self.receipts / AUTHOR_RECEIPTS_DIRNAME

    def author_operation_receipt(self, operation: str) -> Path:
        """Selected receipt for a singleton operation."""
        return self._resolve_under(self.author_receipts, f"{operation}.json")

    def author_experiment_receipt(self, experiment_slug: str) -> Path:
        """Selected receipt for one experiment, keyed by its canonical slug."""
        return self._resolve_under(self.author_receipts, PurePosixPath("experiments") / f"{experiment_slug}.json")

    def run_log(self, run_id: str) -> Path:
        """Path to the NDJSON log file for a single action run."""
        return self.runs / f"{self._validate_run_id(run_id)}.ndjson"

    def run_receipt(self, run_id: str) -> Path:
        """Path to the receipt (input/output digests) for a single action run."""
        return self.runs / f"{self._validate_run_id(run_id)}.receipt.json"

    def run_cancel_marker(self, run_id: str) -> Path:
        """Path whose existence means the action run should stop cooperatively."""
        return self.runs / f"{self._validate_run_id(run_id)}.cancel"

    @staticmethod
    def _validate_run_id(run_id: str) -> str:
        if not run_id or "/" in run_id or "\\" in run_id or run_id.startswith("."):
            raise ValueError(f"invalid run_id: {run_id!r}")
        return run_id

    def upstream_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.upstream, rel)

    def overlay_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.overlay, rel)

    def artifact_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.artifacts, rel)

    def workspace_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.workspace, rel)

    def upload_staging_file(self, token: str) -> Path:
        validate_upload_token(token)
        return self.upload_staging / f"{token}.bin"

    @staticmethod
    def _resolve_under(base: Path, rel: str | PurePosixPath) -> Path:
        validate_relative_path(rel)
        return base / Path(str(rel))


# ================================================
# Validation and Normalization
# ================================================


def validate_upload_token(token: str) -> None:
    if not token or "/" in token or "\\" in token or token.startswith("."):
        raise ValueError(f"invalid upload token: {token!r}")
