"""Materialize and seal the bundle described by a portable REE subject."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from repo2ree_core.bundle.plan import build_zip_bytes
from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.primitives import Digest, ReePath, UtcInstant
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import BundleContents, BundleEntry, Ree
from repo2ree_core.domain.ree.transitions import ReePreconditionError, record_seal, replace_contents, revision_of
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import list_tree_relpaths, write_atomic
from repo2ree_core.persistence.layout import (
    BUNDLE_ARTIFACTS_PREFIX,
    BUNDLE_OVERLAY_PREFIX,
    BUNDLE_REE_MANIFEST_ENTRY_PATH,
    BUNDLE_RESULTS_PREFIX,
    BUNDLE_SNAPSHOT_ENTRY_PATH,
    ReeLayout,
)
from repo2ree_core.persistence.ree_manifest import ree_manifest_bytes
from repo2ree_core.persistence.repository import save_ree
from repo2ree_core.reproduction.reproducer import reproducer_entries


class SealOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sealed_at: UtcInstant
    ree_digest: Digest


def _reproducer(ree: Ree) -> list[tuple[str, bytes]]:
    definition = ree.subject.definition
    source = definition.source
    runtime = definition.build_runtime
    activation = definition.test_activation
    return reproducer_entries(
        activation_script=str(activation.run_script_path) if activation else "",
        activation_verify_script=str(activation.verify_script_path or "") if activation else "",
        experiments=[
            (experiment.name, str(experiment.run_script_path), str(experiment.verify_script_path or ""))
            for experiment in definition.experiments
        ],
        runtime_workspace_path=str(runtime.runtime_path) if runtime and runtime.runtime_path else "",
        runtime_artifact_basename=(
            PurePosixPath(str(runtime.runtime_path)).name if runtime and runtime.runtime_path else ""
        ),
        origin_url=source.origin_url or "" if source else "",
        source_type=source.source_type if source else "",
        revision=source.requested_ref or "" if source else "",
        swhid=str(ree.subject.receipts.source.observed_swhid or "") if ree.subject.receipts.source else "",
    )


def _tree_entries(root: Path, bundle_prefix: str) -> list[tuple[str, bytes]]:
    return [(f"{bundle_prefix}{rel}", (root / rel).read_bytes()) for rel in list_tree_relpaths(root)]


def _collect_entries(
    store: ReeDirectory,
    ree: Ree,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> list[tuple[str, bytes]]:
    layout = store.layout
    entries = _reproducer(ree)
    entries.extend(_tree_entries(layout.overlay, BUNDLE_OVERLAY_PREFIX))
    entries.extend(_tree_entries(layout.artifacts, BUNDLE_ARTIFACTS_PREFIX))
    if source_included and layout.snapshot_archive.is_file():
        entries.append((BUNDLE_SNAPSHOT_ENTRY_PATH, layout.snapshot_archive.read_bytes()))
    runtime = ree.subject.definition.build_runtime
    if runtime_included and runtime is not None and runtime.runtime_path is not None:
        runtime_file = layout.workspace / str(runtime.runtime_path)
        target = f"{BUNDLE_ARTIFACTS_PREFIX}{PurePosixPath(str(runtime.runtime_path)).name}"
        if runtime_file.is_file() and all(path != target for path, _ in entries):
            entries.append((target, runtime_file.read_bytes()))
    if results_included:
        entries.extend(_tree_entries(layout.results, BUNDLE_RESULTS_PREFIX))
    return sorted(entries, key=lambda item: item[0])


def _inventory(entries: list[tuple[str, bytes]]) -> BundleContents:
    return BundleContents(
        entries=tuple(
            BundleEntry(path=ReePath(path), digest=digest_bytes(content), size=len(content))
            for path, content in entries
        )
    )


def _refuse_stale_evidence(ree: Ree) -> None:
    """Refuse to seal an REE whose receipts no longer describe what it holds.

    Sealing is the step that turns an aggregate into something citable, and a
    stale receipt is the one defect a reader cannot detect for themselves: the
    digests all agree, the evidence is all present, and it describes a build
    script or a source that the bundle no longer contains. Publishing that is
    worse than publishing nothing, so it is a refusal rather than a warning.

    *Missing* evidence is deliberately not refused. An REE with no SBOM and no
    activation test is incomplete, which its own audit says plainly and which a
    reader can weigh; an author may have nothing more to add. Incomplete and
    self-contradictory are different failures and only the second is a lie.
    """
    stale = audit(ree).stale_steps()
    if not stale:
        return
    detail = "; ".join(f"{name}: {', '.join(step.reasons)}" for name, step in stale)
    raise ReePreconditionError(
        f"cannot seal an REE with stale evidence — re-run the affected steps or drop what they describe ({detail})"
    )


def seal_ree(
    layout: ReeLayout,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
    sealed_at: UtcInstant,
) -> SealOutputs:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = store.read_ree()
    _refuse_stale_evidence(ree)
    before_revision = revision_of(ree)
    entries = _collect_entries(
        store,
        ree,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )
    sealed = record_seal(replace_contents(ree, _inventory(entries)), sealed_at=sealed_at)
    archive_entries = [*entries, (BUNDLE_REE_MANIFEST_ENTRY_PATH, ree_manifest_bytes(sealed))]
    archive_entries.sort(key=lambda item: item[0])
    write_atomic(store.layout.sealed_archive, build_zip_bytes(archive_entries))
    save_ree(store.layout, store, sealed, expected_revision=before_revision)
    seal = sealed.seal
    if seal is None:  # pragma: no cover - record_seal establishes this postcondition
        raise RuntimeError("seal transition did not produce a seal")
    return SealOutputs(sealed_at=seal.sealed_at, ree_digest=seal.ree_digest)


def build_ree_archive(layout: ReeLayout) -> bytes:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = store.read_ree()
    if ree.seal is not None:
        if not store.layout.sealed_archive.is_file():
            raise RuntimeError("sealed archive file is missing")
        return store.layout.sealed_archive.read_bytes()
    entries = _collect_entries(
        store,
        ree,
        source_included=True,
        runtime_included=True,
        results_included=True,
    )
    draft = replace_contents(ree, _inventory(entries))
    entries.append((BUNDLE_REE_MANIFEST_ENTRY_PATH, ree_manifest_bytes(draft)))
    entries.sort(key=lambda item: item[0])
    return build_zip_bytes(entries)
