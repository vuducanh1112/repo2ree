from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from repo2ree_ree import layout as tree
from repo2ree_ree.paths import validate_path_segment, validate_relative_path

REE_MANIFEST_FILENAME = tree.REE_MANIFEST
_MATERIALIZE_MARKER_FILENAME = tree.MATERIALIZE_MARKER
_UPLOAD_STAGING_DIRNAME = tree.UPLOAD_STAGING
ACQUIRE_SCRIPT_FILENAME = tree.ACQUIRE_SCRIPT
MATERIALIZE_SCRIPT_FILENAME = tree.MATERIALIZE_SCRIPT
UPSTREAM_DIRNAME = tree.UPSTREAM
SNAPSHOT_FILENAME = tree.SNAPSHOT
OVERLAY_DIRNAME = tree.OVERLAY
ARTIFACTS_DIRNAME = tree.ARTIFACTS
SBOM_FILENAME = tree.SBOM
SBOM_ARTIFACT_PATH = f"{ARTIFACTS_DIRNAME}/{SBOM_FILENAME}"
REPRODUCIBILITY_REPORT_FILENAME = tree.REPRODUCIBILITY_REPORT
RESULTS_DIRNAME = tree.RESULTS
WORKSPACE_DIRNAME = tree.WORKSPACE
RUNS_DIRNAME = tree.RUNS
RECEIPTS_DIRNAME = tree.RECEIPTS
REVIEWS_DIRNAME = tree.REVIEWS
REVIEW_RECORD_FILENAME = tree.REVIEW_RECORD
COMPARISONS_DIRNAME = tree.COMPARISONS
SIGNATURES_DIRNAME = tree.SIGNATURES


BUNDLE_ROOT_PREFIX = "ree/"
BUNDLE_REE_MANIFEST_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{REE_MANIFEST_FILENAME}"
BUNDLE_SNAPSHOT_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{SNAPSHOT_FILENAME}"
BUNDLE_OVERLAY_PREFIX = f"{BUNDLE_ROOT_PREFIX}{OVERLAY_DIRNAME}/"
BUNDLE_ARTIFACTS_PREFIX = f"{BUNDLE_ROOT_PREFIX}{ARTIFACTS_DIRNAME}/"
BUNDLE_RESULTS_PREFIX = f"{BUNDLE_ROOT_PREFIX}{RESULTS_DIRNAME}/"
BUNDLE_SIGNATURES_PREFIX = f"{BUNDLE_ROOT_PREFIX}{SIGNATURES_DIRNAME}/"
BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH = tree.REPRODUCER_SCRIPT
BUNDLE_REPRODUCER_README_ENTRY_PATH = tree.REPRODUCER_README
BUNDLE_ACQUIRE_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{ACQUIRE_SCRIPT_FILENAME}"
BUNDLE_MATERIALIZE_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{MATERIALIZE_SCRIPT_FILENAME}"


@dataclass(frozen=True)
class ReeLayout:
    root: Path

    @property
    def history_files(self) -> tuple[Path, ...]:
        return (
            self.manifest,
            self.acquire_script,
            self.materialize_script,
            self.materialize_marker,
        )

    @property
    def history_trees(self) -> tuple[Path, ...]:
        return (self.overlay, self.signatures)

    @property
    def acquire_script(self) -> Path:
        return self.root / ACQUIRE_SCRIPT_FILENAME

    @property
    def materialize_script(self) -> Path:
        return self.root / MATERIALIZE_SCRIPT_FILENAME

    @property
    def git_dir(self) -> Path:
        return self.root / tree.GIT_DIR

    @property
    def snapshot_archive(self) -> Path:
        return self.root / SNAPSHOT_FILENAME

    @property
    def upstream(self) -> Path:
        return self.root / UPSTREAM_DIRNAME

    @property
    def overlay(self) -> Path:
        return self.root / OVERLAY_DIRNAME

    @property
    def signatures(self) -> Path:
        return self.root / SIGNATURES_DIRNAME

    @property
    def workspace(self) -> Path:
        return self.root / WORKSPACE_DIRNAME

    @classmethod
    def for_ree(cls, storage_root: Path | str, ree_id: str) -> ReeLayout:
        return cls(root=Path(storage_root) / ree_id)

    @property
    def manifest(self) -> Path:
        return self.root / REE_MANIFEST_FILENAME

    @property
    def materialize_marker(self) -> Path:
        return self.root / _MATERIALIZE_MARKER_FILENAME

    @property
    def upload_staging(self) -> Path:
        return self.root / _UPLOAD_STAGING_DIRNAME

    @property
    def stages(self) -> Path:
        return self.root / tree.STAGES

    @property
    def artifacts(self) -> Path:
        return self.root / ARTIFACTS_DIRNAME

    def kept_environment(self, declared: str) -> Path:
        if PurePosixPath(declared).parts[:1] == (ARTIFACTS_DIRNAME,):
            return self.root / declared
        return self.artifacts / "experiment-environment" / declared

    @property
    def sbom(self) -> Path:
        return self.artifacts / SBOM_FILENAME

    @property
    def reproducibility_report(self) -> Path:
        return self.artifacts / REPRODUCIBILITY_REPORT_FILENAME

    @property
    def results(self) -> Path:
        return self.root / RESULTS_DIRNAME

    def results_dir(self, name: str) -> Path:
        return _resolve_under(self.results, name)

    @property
    def runs(self) -> Path:
        return self.root / RUNS_DIRNAME

    @property
    def reviews(self) -> Path:
        return self.root / REVIEWS_DIRNAME

    def review(self, review_id: str) -> ReviewLayout:
        return ReviewLayout(root=_resolve_under(self.reviews, validate_path_segment(review_id, kind="review_id")))

    def run_log(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.ndjson"

    def run_cancel_marker(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.cancel"

    def overlay_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.overlay, rel)

    def workspace_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.workspace, rel)

    def ree_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.root, rel)

    def upload_staging_file(self, token: str) -> Path:
        validate_upload_token(token)
        return self.upload_staging / f"{token}.bin"


@dataclass(frozen=True)
class ReviewLayout(ReeLayout):
    @property
    def history_files(self) -> tuple[Path, ...]:
        return (*super().history_files, self.metadata)

    @property
    def history_trees(self) -> tuple[Path, ...]:
        return (*super().history_trees, self.receipts, self.comparisons)

    @property
    def metadata(self) -> Path:
        return self.root / REVIEW_RECORD_FILENAME

    @property
    def receipts(self) -> Path:
        return self.root / RECEIPTS_DIRNAME

    @property
    def comparisons(self) -> Path:
        return self.root / COMPARISONS_DIRNAME

    def run_receipt(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.receipt.json"

    def operation_receipt(self, operation: str) -> Path:
        return _resolve_under(self.receipts, f"{operation}.json")

    def comparison(self, step: str) -> Path:
        return _resolve_under(self.comparisons, f"{step}.json")

    def experiment_receipt(self, experiment_slug: str) -> Path:
        return _resolve_under(self.receipts, PurePosixPath(tree.EXPERIMENTS) / f"{experiment_slug}.json")

    def experiment_comparison(self, experiment_slug: str) -> Path:
        return _resolve_under(self.comparisons, PurePosixPath(tree.EXPERIMENTS) / f"{experiment_slug}.json")


def validate_run_id(run_id: str) -> str:
    return validate_path_segment(run_id, kind="run_id")


def validate_upload_token(token: str) -> None:
    validate_path_segment(token, kind="upload token")


def _resolve_under(base: Path, rel: str | PurePosixPath) -> Path:
    validate_relative_path(rel)
    return base / Path(str(rel))
