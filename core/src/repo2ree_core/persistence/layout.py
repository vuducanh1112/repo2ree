"""Pure description of the on-disk layout of a single REE.

This module is part of the functional core: it contains the data type and
path arithmetic, but performs no filesystem I/O. The imperative shell —
:class:`repo2ree_core.persistence.directory.ReeDirectory` and the read views beside it — uses
``ReeLayout`` to know where to read and write.

Layout under ``<storage_root>/<ree_id>/`` (host) or ``/ree/`` (workbench):

    .ree.json             persisted REE record
    manifest.json         sealed REE spec manifest
    sealed.zip            immutable sealed archive (written by seal_ree)
    snapshot.tar.gz       frozen upstream archive
    upload-staging/       staging area for in-flight source uploads
    upstream/             extracted snapshot, treated as read-only
    overlay/              user-added and tool-generated recipe files
    artifacts/            produced evidence (sbom.json, reproducibility-report.json,
                          and a runtime restored from a loaded bundle)
    workspace/            materialized view (upstream + overlay) used at build time
    runs/                 per-action logs and immutable receipt history
    receipts/author/      latest successful author receipt per operation
    reviews/<review-id>/  isolated reviewer tree: its own upstream/, overlay/,
                          workspace/, receipts, and comparisons

``upstream/`` and ``overlay/`` are the sources of truth; ``workspace/`` is
derived and may be rebuilt at any time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Canonical lexical path checks live in the dependency-free leaf module so the
# domain and experiment layers can share them without an import cycle. Import
# them from there, never from here: one spelling per primitive.
from repo2ree_core.path_safety import validate_path_segment, validate_relative_path

# ================================================
# Constants
# ================================================


_RECORD_FILENAME = ".ree.json"
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
# The SBOM is REE-owned evidence, not an authored file: only ``generate_sbom``
# writes it, and it names one fixed place. Published on the intent (and so in
# the manifest) as this REE-root-relative path, which is also where the bundle
# carries it — so an REE loaded from a bundle declares exactly what it declared
# before packaging.
SBOM_FILENAME = "sbom.json"
SBOM_ARTIFACT_PATH = f"{ARTIFACTS_DIRNAME}/{SBOM_FILENAME}"
# The evaluate step's report, the other piece of REE-owned produced evidence
# with one fixed home. Unlike the SBOM it is never published on the intent (no
# step consumes it as a declared input), so it needs no root-relative spelling —
# but it is read by the step overlay and the cross-check, which is exactly why
# its name belongs here rather than in each of them.
REPRODUCIBILITY_REPORT_FILENAME = "reproducibility-report.json"
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
REVIEWS_DIRNAME = "reviews"

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
    def record(self) -> Path:
        return self.root / _RECORD_FILENAME

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
    def sbom(self) -> Path:
        """This REE's software bill of materials, scanned off its runtime.

        Sits in ``artifacts/`` rather than in ``workspace/``: the workspace is a
        materialized view of source + recipe that any run may rewrite, while
        this document is produced evidence the seal and every reviewer read.
        Mirrors :attr:`ReviewLayout.sbom` on the reviewer's side.
        """
        return self.artifacts / SBOM_FILENAME

    @property
    def reproducibility_report(self) -> Path:
        """This REE's evaluate report, written by ``evaluate_dependency_score``.

        Beside the SBOM in ``artifacts/`` and for the same reason: produced
        evidence, not an authored file. Its presence is also the evaluate step's
        completion signal — the step records no receipt — which is why the step
        overlay asks the layout for it rather than spelling the name itself.
        """
        return self.artifacts / REPRODUCIBILITY_REPORT_FILENAME

    @property
    def results(self) -> Path:
        return self.root / RESULTS_DIRNAME

    def results_dir(self, name: str) -> Path:
        """Produced-results store for a single experiment, keyed by its name.

        Experiment names are already constrained to a safe single path segment
        (``EXPERIMENT_NAME_PATTERN``); the resolver rejects anything else.
        """
        return _resolve_under(self.results, name)

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
    def reviews(self) -> Path:
        return self.root / REVIEWS_DIRNAME

    def review(self, review_id: str) -> ReviewLayout:
        return ReviewLayout(root=_resolve_under(self.reviews, validate_path_segment(review_id, kind="review_id")))

    @property
    def author_receipts(self) -> Path:
        """Selected author evidence: latest successful receipt per step."""
        return self.receipts / AUTHOR_RECEIPTS_DIRNAME

    def author_operation_receipt(self, operation: str) -> Path:
        """Selected receipt for a singleton operation."""
        return _resolve_under(self.author_receipts, f"{operation}.json")

    def author_experiment_receipt(self, experiment_slug: str) -> Path:
        """Selected receipt for one experiment, keyed by its canonical slug."""
        return _resolve_under(self.author_receipts, PurePosixPath("experiments") / f"{experiment_slug}.json")

    def run_log(self, run_id: str) -> Path:
        """Path to the NDJSON log file for a single action run."""
        return self.runs / f"{validate_run_id(run_id)}.ndjson"

    def run_receipt(self, run_id: str) -> Path:
        """Path to the receipt (input/output digests) for a single action run."""
        return self.runs / f"{validate_run_id(run_id)}.receipt.json"

    def run_cancel_marker(self, run_id: str) -> Path:
        """Path whose existence means the action run should stop cooperatively."""
        return self.runs / f"{validate_run_id(run_id)}.cancel"

    def upstream_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.upstream, rel)

    def overlay_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.overlay, rel)

    def artifact_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.artifacts, rel)

    def workspace_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.workspace, rel)

    def ree_file(self, rel: str | PurePosixPath) -> Path:
        """A path relative to the REE root itself, e.g. ``artifacts/runtime.tar.gz``.

        The spelling a bundle's manifest uses once packaging has lifted the
        runtime out of the workspace (see ``ReeDirectory.author_artifact``).
        """
        return _resolve_under(self.root, rel)

    def upload_staging_file(self, token: str) -> Path:
        validate_upload_token(token)
        return self.upload_staging / f"{token}.bin"


@dataclass(frozen=True)
class ReviewLayout:
    """Writable evidence namespace for one independent review attempt.

    Deliberately a *parallel* REE tree, not a view onto the author's: it carries
    its own ``upstream/``, ``overlay/``, and ``workspace/`` under the same
    dirnames, so the shared acquire and materialize scripts — which derive their
    paths from their own location — run here unchanged and mean the same thing.
    The author's tree is only ever read.
    """

    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / "review.json"

    @property
    def acquire_script(self) -> Path:
        return self.root / ACQUIRE_SCRIPT_FILENAME

    @property
    def materialize_script(self) -> Path:
        return self.root / MATERIALIZE_SCRIPT_FILENAME

    @property
    def snapshot_archive(self) -> Path:
        """The author's frozen snapshot, copied in for a bundled-basis acquisition.

        Present only on attempts that reproduced from the bundle rather than
        from the origin: ``acquire_source.sh`` extracts whatever snapshot sits
        beside it, which is how the same script serves both bases.
        """
        return self.root / SNAPSHOT_FILENAME

    @property
    def upstream(self) -> Path:
        return self.root / UPSTREAM_DIRNAME

    @property
    def overlay(self) -> Path:
        """The author's recipe files, copied in so the merge never mutates them."""
        return self.root / OVERLAY_DIRNAME

    @property
    def workspace(self) -> Path:
        return self.root / WORKSPACE_DIRNAME

    @property
    def sbom(self) -> Path:
        """The reviewer's own scan of the runtime they built.

        Sits at the attempt root rather than inside ``workspace/``: the workspace
        is disposable (and pruned after a build), while this document is the
        evidence the build verdict rests on.
        """
        return self.root / "sbom.json"

    @property
    def runs(self) -> Path:
        return self.root / RUNS_DIRNAME

    @property
    def receipts(self) -> Path:
        return self.root / RECEIPTS_DIRNAME

    @property
    def comparisons(self) -> Path:
        return self.root / "comparisons"

    def run_log(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.ndjson"

    def run_receipt(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.receipt.json"

    def operation_receipt(self, operation: str) -> Path:
        return _resolve_under(self.receipts, f"{operation}.json")

    def comparison(self, step: str) -> Path:
        return _resolve_under(self.comparisons, f"{step}.json")

    def experiment_receipt(self, experiment_slug: str) -> Path:
        """Selected receipt for one reproduced experiment, keyed by its slug.

        The experiments step is the one step with more than one subject, so its
        evidence needs a directory where the others need a file. Mirrors the
        author side's ``receipts/author/experiments/`` for the same reason.
        """
        return _resolve_under(self.receipts, PurePosixPath("experiments") / f"{experiment_slug}.json")

    def experiment_comparison(self, experiment_slug: str) -> Path:
        """This attempt's verdict for one experiment, keyed by its slug."""
        return _resolve_under(self.comparisons, PurePosixPath("experiments") / f"{experiment_slug}.json")


# ================================================
# Validation and Normalization
# ================================================

# Both layouts key directories and files by the same three identifiers and join
# paths the same way, so the primitives are module-level functions rather than
# methods on either class: a layout that reached into the other's privates to
# borrow one would make the two look like a hierarchy they are not.


def validate_run_id(run_id: str) -> str:
    return validate_path_segment(run_id, kind="run_id")


def validate_upload_token(token: str) -> None:
    validate_path_segment(token, kind="upload token")


def _resolve_under(base: Path, rel: str | PurePosixPath) -> Path:
    validate_relative_path(rel)
    return base / Path(str(rel))
