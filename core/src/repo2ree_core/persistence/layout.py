"""Pure description of the on-disk layout of a single REE.

This module is part of the functional core: it contains the data type and
path arithmetic, but performs no filesystem I/O. The imperative shell —
:class:`repo2ree_core.persistence.directory.ReeDirectory` and the read views beside it — uses
``ReeLayout`` to know where to read and write.

The tree under ``<storage_root>/<ree_id>/`` (host) or ``/ree/`` (workbench) is
``repo2ree_ree.layout.REE_TREE``: each entry, who writes it, and how a capture carries it.

``upstream/`` and ``overlay/`` are the sources of truth; ``workspace/`` is
derived and may be rebuilt at any time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Canonical lexical path checks live in the dependency-free leaf module so the
# domain and experiment layers can share them without an import cycle. Import
# them from there, never from here: one spelling per primitive.
from repo2ree_ree import layout as tree
from repo2ree_ree.paths import validate_path_segment, validate_relative_path

# ================================================
# Constants
# ================================================


# The names are the REE tree's (repo2ree_ree.layout, exported as contracts/ree/layout.json); this module
# joins them into paths and keeps the names its callers import.
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
# Published in the aggregate as this REE-root-relative path, which is also where the bundle carries it.
SBOM_ARTIFACT_PATH = f"{ARTIFACTS_DIRNAME}/{SBOM_FILENAME}"
REPRODUCIBILITY_REPORT_FILENAME = tree.REPRODUCIBILITY_REPORT
RESULTS_DIRNAME = tree.RESULTS
WORKSPACE_DIRNAME = tree.WORKSPACE
RUNS_DIRNAME = tree.RUNS
RECEIPTS_DIRNAME = tree.RECEIPTS
REVIEWS_DIRNAME = tree.REVIEWS
REVIEW_RECORD_FILENAME = tree.REVIEW_RECORD
COMPARISONS_DIRNAME = tree.COMPARISONS

# Fixed mount point inside every REE workbench container.
WORKBENCH_ROOT = Path(os.environ.get("REPO2REE_WORKBENCH_ROOT", "/ree"))


# ================================================
# Bundle Layout
# ================================================

# What a published bundle looks like from the outside. It mirrors the tree
# above under a single ``ree/`` prefix, and every entry path here is *derived*
# from the dirnames rather than spelled again — which is what makes the mirror
# a fact instead of a claim. The prefix is the REE root's own name by intent:
# unpacking a bundle produces a directory that then *is* an REE root, so the
# same acquire and materialize scripts run there unchanged.
#
# These strings are a format promise. They appear in every bundle ever
# published, and a reader holding one from a year ago resolves them literally —
# so changing a dirname above changes what is published. ``test_bundle_layout``
# pins each spelling to keep that a decision rather than a side effect.
BUNDLE_ROOT_PREFIX = "ree/"
BUNDLE_REE_MANIFEST_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{REE_MANIFEST_FILENAME}"
BUNDLE_SNAPSHOT_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{SNAPSHOT_FILENAME}"
BUNDLE_OVERLAY_PREFIX = f"{BUNDLE_ROOT_PREFIX}{OVERLAY_DIRNAME}/"
BUNDLE_ARTIFACTS_PREFIX = f"{BUNDLE_ROOT_PREFIX}{ARTIFACTS_DIRNAME}/"
BUNDLE_RESULTS_PREFIX = f"{BUNDLE_ROOT_PREFIX}{RESULTS_DIRNAME}/"
# The reproducer's own entries: a bundle is meant to be run by a human who
# unpacked it, so its entry point and instructions sit at the top level rather
# than under ``ree/``. The scripts they call are the workbench's own, which is
# why those two carry the prefix and these do not.
BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH = tree.REPRODUCER_SCRIPT
BUNDLE_REPRODUCER_README_ENTRY_PATH = tree.REPRODUCER_README
BUNDLE_ACQUIRE_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{ACQUIRE_SCRIPT_FILENAME}"
BUNDLE_MATERIALIZE_ENTRY_PATH = f"{BUNDLE_ROOT_PREFIX}{MATERIALIZE_SCRIPT_FILENAME}"


# ================================================
# Data Models
# ================================================


@dataclass(frozen=True)
class ReeLayout:
    """The on-disk layout for a single REE, as a value.

    Construct with :meth:`for_ree`; every other attribute is a pure
    derivation from :attr:`root`. No method touches the filesystem.

    The tree this describes is the one the shared shell scripts run in:
    ``acquire_source.sh`` fills ``upstream/`` from an origin or a snapshot, and
    ``materialize_workspace.sh`` derives ``workspace/`` from ``upstream/`` plus
    ``overlay/``. Both resolve their paths from their own location, which is
    what lets a review attempt — a :class:`ReviewLayout`, and an REE root in its
    own right — run them unchanged and mean the same thing by them.
    """

    root: Path

    @property
    def history_files(self) -> tuple[Path, ...]:
        """Fixed state files; operational logs and upload staging are not state."""
        return (
            self.manifest,
            self.acquire_script,
            self.materialize_script,
            self.materialize_marker,
        )

    @property
    def history_trees(self) -> tuple[Path, ...]:
        """Open-ended state subtrees, including arbitrary user filenames."""
        return (self.overlay,)

    @property
    def acquire_script(self) -> Path:
        return self.root / ACQUIRE_SCRIPT_FILENAME

    @property
    def materialize_script(self) -> Path:
        return self.root / MATERIALIZE_SCRIPT_FILENAME

    @property
    def git_dir(self) -> Path:
        """Local version storage, excluded from REE file views and bundles."""
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
    def workspace(self) -> Path:
        return self.root / WORKSPACE_DIRNAME

    @classmethod
    def for_ree(cls, storage_root: Path | str, ree_id: str) -> ReeLayout:
        return cls(root=Path(storage_root) / ree_id)

    @classmethod
    def in_workbench(cls) -> ReeLayout:
        """Layout rooted at the fixed workbench mount point (/ree)."""
        return cls(root=WORKBENCH_ROOT)

    @property
    def manifest(self) -> Path:
        """This REE's manifest: what it declares, and what a bundle of it holds."""
        return self.root / REE_MANIFEST_FILENAME

    @property
    def materialize_marker(self) -> Path:
        """What the workspace was last materialized from for drift checks.

        The ``.workspace`` prefix reads as machine bookkeeping beside the
        authored files; it is not what keeps it out of reach. Nothing filters
        dot-prefixed names — writes are confined to the ``overlay/`` and
        ``workspace/`` subtrees, so no root-level file is reachable through the
        file APIs whatever it is called.
        """
        return self.root / _MATERIALIZE_MARKER_FILENAME

    @property
    def upload_staging(self) -> Path:
        return self.root / _UPLOAD_STAGING_DIRNAME

    @property
    def artifacts(self) -> Path:
        return self.root / ARTIFACTS_DIRNAME

    @property
    def sbom(self) -> Path:
        """This REE's software bill of materials, scanned off its experiment environment.

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
    def runs(self) -> Path:
        return self.root / RUNS_DIRNAME

    @property
    def reviews(self) -> Path:
        return self.root / REVIEWS_DIRNAME

    def review(self, review_id: str) -> ReviewLayout:
        return ReviewLayout(root=_resolve_under(self.reviews, validate_path_segment(review_id, kind="review_id")))

    def run_log(self, run_id: str) -> Path:
        """Path to the NDJSON log file for a single action run."""
        return self.runs / f"{validate_run_id(run_id)}.ndjson"

    def run_cancel_marker(self, run_id: str) -> Path:
        """Path whose existence means the action run should stop cooperatively."""
        return self.runs / f"{validate_run_id(run_id)}.cancel"

    def overlay_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.overlay, rel)

    def workspace_file(self, rel: str | PurePosixPath) -> Path:
        return _resolve_under(self.workspace, rel)

    def ree_file(self, rel: str | PurePosixPath) -> Path:
        """A path relative to the REE root itself, e.g. ``artifacts/runtime.tar.gz``.

        The spelling a bundle's manifest uses once packaging has lifted the
        experiment environment out of the workspace (see ``ReeDirectory.author_artifact``).
        """
        return _resolve_under(self.root, rel)

    def upload_staging_file(self, token: str) -> Path:
        validate_upload_token(token)
        return self.upload_staging / f"{token}.bin"


@dataclass(frozen=True)
class ReviewLayout(ReeLayout):
    """Writable evidence namespace for one independent review attempt.

    An attempt root is an REE root: it carries its own ``upstream/``,
    ``overlay/``, ``workspace/`` and ``artifacts/`` under the same dirnames, so
    the shared acquire and materialize scripts — which derive their paths from
    their own location — run here unchanged and mean the same thing, and the
    reviewer's own scan lands beside the author's in ``artifacts/``. It is
    deliberately a *parallel* tree rather than a view onto the author's: the
    author's is only ever read. What this adds is the attempt's own evidence —
    its record, its receipts, and the comparisons they settle.

    Three inherited paths mean something particular on this side, because their
    contents arrive by copy or by the reviewer's own hand rather than by
    authoring:

    ``snapshot_archive``
        The author's frozen snapshot, copied in for a bundled-basis
        acquisition. Present only on attempts that reproduced from the bundle
        rather than from the origin: ``acquire_source.sh`` extracts whatever
        snapshot sits beside it, which is how the same script serves both bases.

    ``overlay``
        The author's recipe files, copied in so the merge never mutates them.

    ``sbom``
        The reviewer's own scan of the experiment environment *they* built, not a copy of the
        author's. In ``artifacts/`` for the reason the author's is: the
        workspace is disposable and pruned after a build, while this document is
        the evidence the build verdict rests on.
    """

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
        """Selected receipt for one reproduced experiment, keyed by its slug.

        The experiments step is the one step with more than one subject, so its
        evidence needs a directory where the others need a file.
        """
        return _resolve_under(self.receipts, PurePosixPath(tree.EXPERIMENTS) / f"{experiment_slug}.json")

    def experiment_comparison(self, experiment_slug: str) -> Path:
        """This attempt's verdict for one experiment, keyed by its slug."""
        return _resolve_under(self.comparisons, PurePosixPath(tree.EXPERIMENTS) / f"{experiment_slug}.json")


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
