"""The file tree of an REE root: what each entry holds, who writes it, and how a bundle carries it.

One tree serves every place an REE root exists: ``<storage_root>/<ree_id>/`` on the host, ``/ree/``
in a workbench, a review attempt's ``reviews/<review>/``, and what a bundle unpacks to. The names are
spelled here once; the core's layout joins them into paths, and ``contracts/ree/layout.json`` is this
tree exported (``just generate-ree-schema``).

An entry whose name is a ``{key}`` stands for one entry per key, e.g. ``results/{experiment}/``.
"""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.reserved_paths import RESERVED_SCRIPT_DIR

Kind = Literal["file", "directory"]
# Who writes it. ``acquired``: the source acquisition. ``authored``: the author, through the file APIs.
# ``produced``: a run, as evidence. ``derived``: rebuilt from other entries at any time.
# ``repo2ree``: repo2ree itself, the same for every REE. ``working``: the state of runs in progress.
Origin = Literal["document", "acquired", "authored", "produced", "derived", "repo2ree", "working"]
# How a capture carries it: committed, committed as an LFS payload, or not at all.
Capture = Literal["git", "lfs", "never"]
Key = Literal["experiment", "experiment_slug", "experiment_environment", "operation", "step", "run", "review", "upload"]

REE_MANIFEST = "ree.json"
GIT_DIR = ".git"
GIT_ATTRIBUTES = ".gitattributes"
GIT_IGNORE = ".gitignore"
ACQUIRE_SCRIPT = "acquire_source.sh"
MATERIALIZE_SCRIPT = "materialize_workspace.sh"
MATERIALIZE_MARKER = ".workspace.materialized.json"
SNAPSHOT = "snapshot.tar.gz"
UPSTREAM = "upstream"
OVERLAY = "overlay"
ARTIFACTS = "artifacts"
SBOM = "sbom.json"
REPRODUCIBILITY_REPORT = "reproducibility-report.json"
RESULTS = "results"
WORKSPACE = "workspace"
REPRODUCER_SCRIPT = "run.sh"
REPRODUCER_README = "REPRODUCING.md"
RUNS = "runs"
UPLOAD_STAGING = "upload-staging"
REVIEWS = "reviews"
REVIEW_RECORD = "review.json"
RECEIPTS = "receipts"
COMPARISONS = "comparisons"
EXPERIMENTS = "experiments"

LAYOUT_FORMAT = "repo2ree-ree-layout/1"


class TreeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: Kind
    origin: Origin
    capture: Capture
    description: str
    key: Key | None = None
    # The REE document field whose value names this entry; such an entry is found through that field, not by name.
    named_by: str | None = None
    # A review attempt's root is an REE root in its own right: it holds the root's entries too.
    ree_root: bool = False
    children: tuple[TreeEntry, ...] = ()

    def at(self, *names: str) -> TreeEntry:
        """The entry these names lead to, spelled as the tree spells them (``{key}`` for a keyed one)."""
        entry = self
        for name in names:
            entry = next((child for child in entry.children if child.name == name), None) or _missing(entry, name)
        return entry

    def names(self, name: str) -> bool:
        """Whether this entry is the one called ``name``: by its own name, or as one of its keyed kind."""
        return name == self.name or (self.key is not None and _matches(self.name, name))

    def find(self, path: str | PurePosixPath) -> TreeEntry:
        """The entry a path relative to this one falls in: its deepest ancestor the tree names."""
        entry = self
        for part in PurePosixPath(path).parts:
            children = (*entry.children, *(REE_TREE.children if entry.ree_root else ()))
            matched = next((child for child in children if child.name == part), None) or next(
                (child for child in children if child.key and not child.named_by and _matches(child.name, part)),
                None,
            )
            if matched is None:
                return entry
            entry = matched
        return entry


def _missing(entry: TreeEntry, name: str) -> TreeEntry:
    raise KeyError(f"{entry.name} has no entry {name}")


def _matches(pattern: str, name: str) -> bool:
    return re.fullmatch(re.sub(r"\\\{[a-z_]+\\\}", ".+", re.escape(pattern)), name) is not None


def _file(
    name: str,
    origin: Origin,
    capture: Capture,
    description: str,
    key: Key | None = None,
    named_by: str | None = None,
) -> TreeEntry:
    return TreeEntry(
        name=name, kind="file", origin=origin, capture=capture, description=description, key=key, named_by=named_by
    )


_ARTIFACT_PATH = "definition.experiment_environment.artifact_path"
_RUN_LOGS = (
    _file("{run}.ndjson", "working", "never", "A run's log.", key="run"),
    _file("{run}.cancel", "working", "never", "Present while the run is asked to stop.", key="run"),
)


def _directory(
    name: str,
    origin: Origin,
    capture: Capture,
    description: str,
    *children: TreeEntry,
    key: Key | None = None,
    ree_root: bool = False,
) -> TreeEntry:
    return TreeEntry(
        name=name,
        kind="directory",
        origin=origin,
        capture=capture,
        description=description,
        key=key,
        ree_root=ree_root,
        children=children,
    )


_SCRIPTS = _directory(
    RESERVED_SCRIPT_DIR,
    "authored",
    "git",
    "The REE's scripts; the overlay holds these and nothing else.",
    _file("build_experiment_environment.sh", "authored", "git", "Builds the experiment environment."),
    _file("activate_experiment_environment.sh", "authored", "git", "Enters the experiment environment."),
    _directory(
        EXPERIMENTS,
        "authored",
        "git",
        "One run script and one optional verify script per experiment.",
        _file("{experiment_slug}.sh", "authored", "git", "Runs the experiment.", key="experiment_slug"),
        _file("{experiment_slug}.verify.sh", "authored", "git", "Verifies its outputs.", key="experiment_slug"),
    ),
)

_REVIEW = _directory(
    "{review}",
    "working",
    "git",
    "One review attempt: an REE root of its own, beside the author's, which it only reads. "
    "Its overlay and snapshot are copies of the author's; its artifacts are its own.",
    _file(REVIEW_RECORD, "working", "git", "The attempt's record."),
    _directory(
        RECEIPTS,
        "produced",
        "git",
        "The receipt the attempt selected for each step.",
        _file("{operation}.json", "produced", "git", "The receipt of one step.", key="operation"),
        _directory(
            EXPERIMENTS,
            "produced",
            "git",
            "One receipt per reproduced experiment.",
            _file("{experiment_slug}.json", "produced", "git", "The receipt of one experiment.", key="experiment_slug"),
        ),
    ),
    _directory(
        COMPARISONS,
        "produced",
        "git",
        "The attempt's verdict on each step, against the author's evidence.",
        _file("{step}.json", "produced", "git", "The verdict on one step.", key="step"),
        _directory(
            EXPERIMENTS,
            "produced",
            "git",
            "One verdict per reproduced experiment.",
            _file("{experiment_slug}.json", "produced", "git", "The verdict on one experiment.", key="experiment_slug"),
        ),
    ),
    _directory(
        RUNS,
        "working",
        "never",
        "The attempt's run logs, and each run's receipt.",
        *_RUN_LOGS,
        _file("{run}.receipt.json", "produced", "git", "The receipt a run wrote.", key="run"),
    ),
    key="review",
    ree_root=True,
)

REE_TREE = _directory(
    ".",
    "repo2ree",
    "git",
    "An REE root: on the host, in a workbench at /ree, a review attempt, and what a bundle unpacks to.",
    _file(REE_MANIFEST, "document", "git", "The REE document: what it declares, what its receipts prove, its seal."),
    _directory(GIT_DIR, "repo2ree", "never", "The REE's history: each capture is a commit here."),
    _file(GIT_ATTRIBUTES, "repo2ree", "git", "Which captured paths are LFS payloads."),
    _file(GIT_IGNORE, "repo2ree", "git", "What a capture leaves out."),
    _file(ACQUIRE_SCRIPT, "repo2ree", "git", "Fills upstream/ from the origin, or from the snapshot beside it."),
    _file(MATERIALIZE_SCRIPT, "repo2ree", "git", "Derives workspace/ from upstream/ and overlay/."),
    _file(MATERIALIZE_MARKER, "repo2ree", "git", "What workspace/ was last materialized from, for drift checks."),
    _file(SNAPSHOT, "acquired", "lfs", "The frozen upstream archive."),
    _directory(UPSTREAM, "derived", "never", "The snapshot, extracted; read only."),
    _directory(OVERLAY, "authored", "git", "The author's files, laid over upstream/ in the workspace.", _SCRIPTS),
    _directory(
        ARTIFACTS,
        "produced",
        "git",
        "Produced evidence, with one fixed place each.",
        _file(SBOM, "produced", "git", "The software bill of materials of the experiment environment."),
        _file(REPRODUCIBILITY_REPORT, "produced", "git", "The evaluate step's report."),
        _file(
            "{experiment_environment}",
            "produced",
            "lfs",
            "The experiment environment as sealed or loaded: lifted here from the workspace by its file name.",
            key="experiment_environment",
            named_by=_ARTIFACT_PATH,
        ),
    ),
    _directory(
        RESULTS,
        "produced",
        "lfs",
        "The author's captured outputs, for a reviewer to compare against.",
        _directory("{experiment}", "produced", "lfs", "One experiment's outputs.", key="experiment"),
    ),
    _directory(
        WORKSPACE,
        "derived",
        "never",
        "upstream/ with overlay/ laid over it, where builds and experiments run.",
        _file(
            "{experiment_environment}",
            "produced",
            "never",
            "The experiment environment as the build script wrote it, at the definition's artifact_path.",
            key="experiment_environment",
            named_by=_ARTIFACT_PATH,
        ),
    ),
    _file(REPRODUCER_SCRIPT, "repo2ree", "git", "A bundle's reproducer: runs the REE without repo2ree."),
    _file(REPRODUCER_README, "repo2ree", "git", "How to run the reproducer."),
    _directory(
        RUNS,
        "working",
        "never",
        "One log per run, and the marker that asks a run to stop.",
        *_RUN_LOGS,
    ),
    _directory(
        UPLOAD_STAGING,
        "working",
        "never",
        "Source uploads in flight.",
        _file("{upload}.bin", "working", "never", "One upload, by its token.", key="upload"),
    ),
    _directory(REVIEWS, "working", "git", "The review attempts on this REE.", _REVIEW),
)


# What a digest field is the digest of. ``file``: one file. ``tree``: every file under a directory.
# ``paths``: the files a field names, under an entry. ``subject``: the REE document's canonical subject.
# ``outside``: something the REE does not hold, such as a pulled image.
Covers = Literal["file", "tree", "paths", "subject", "outside"]


class DigestOf(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    covers: Covers
    # The entries of the tree it is the digest of, spelled as the tree spells them.
    entries: tuple[str, ...] = ()
    # The REE document field whose value names the file or files.
    named_by: str | None = None


def digest_of(covers: Covers, *entries: str, named_by: str | None = None) -> Any:
    """A digest field's ``Field``: what in the tree it covers, written into the schema as ``x-digest-of``."""
    for entry in entries:
        if entry != ".":
            REE_TREE.at(*PurePosixPath(entry).parts)
    of = DigestOf(covers=covers, entries=entries, named_by=named_by)
    return Field(json_schema_extra={"x-digest-of": of.model_dump(mode="json", exclude_defaults=True)})


def layout_document() -> str:
    """``contracts/ree/layout.json``: the tree, for readers that do not import this package."""
    document = {"format": LAYOUT_FORMAT, "root": REE_TREE.model_dump(mode="json", exclude_defaults=True)}
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
