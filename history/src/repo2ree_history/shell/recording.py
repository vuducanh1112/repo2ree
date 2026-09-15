"""Collect recording files and Git availability once, before pure assembly."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from repo2ree_history.core.assembly import assemble
from repo2ree_history.core.evidence import (
    AssemblyResult,
    Diagnostic,
    DocumentBatch,
    GitDocument,
    RecordingSnapshot,
    SourceDocument,
)
from repo2ree_history.core.models import Artifact, RecordLocator, SourceReference, SpanLocator
from repo2ree_history.core.normalize import trace_context
from repo2ree_history.shell.files import contained
from repo2ree_history.shell.git import commit_exists, read_operations


def read_documents(root: Path, name: str) -> tuple[bytes | None, DocumentBatch]:
    path = contained(root, name + ".ndjson")
    if not path.exists():
        return None, DocumentBatch(())
    data = path.read_bytes()
    documents = []
    diagnostics = []
    for line, raw in enumerate(data.splitlines(), 1):
        if not raw.strip():
            continue
        ref = SourceReference(artifact_id=name, locator=RecordLocator(line=line))
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("expected an object")
            if name == "traces":
                ref = SourceReference(
                    artifact_id=name,
                    locator=SpanLocator(**trace_context(value["context"]).model_dump(), line=line),
                )
        except (KeyError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(
                    code="malformed_record",
                    severity="invalid",
                    detail=f"{path.name}:{line}: {exc}",
                    source_refs=(ref,),
                )
            )
            continue
        documents.append(SourceDocument(value, ref))
    return data, DocumentBatch(tuple(documents), tuple(diagnostics))


def read_manifest(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(contained(root, "manifest.json").read_text())
    if not isinstance(value, dict):
        raise ValueError("manifest.json: expected an object")
    if value.get("schema_version") != 1:
        raise ValueError("unsupported test manifest schema")
    for key in ("execution_id", "nodeid", "started", "finished", "repositories"):
        if key not in value:
            raise ValueError(f"manifest missing {key}")
    return value


def load_recording(recording_dir: Path) -> RecordingSnapshot:
    root = recording_dir.resolve()
    manifest = read_manifest(root)
    artifacts = [Artifact(artifact_id="manifest", kind="report", uri="manifest.json")]
    diagnostics: list[Diagnostic] = []
    operations: list[GitDocument] = []
    documents = {}
    for name in ("traces", "state"):
        data, sources = read_documents(root, name)
        documents[name] = sources.documents
        diagnostics.extend(sources.diagnostics)
        if data is None:
            diagnostics.append(Diagnostic(code="missing_artifact", detail=name + ".ndjson"))
        else:
            artifacts.append(
                Artifact(
                    artifact_id=name,
                    kind="telemetry" if name == "traces" else "state",
                    uri=name + ".ndjson",
                    sha256=sha256(data).hexdigest(),
                )
            )
    repositories: dict[str, Path] = {}
    for index, repository in enumerate(manifest["repositories"]):
        if repository.get("status") != "recorded":
            diagnostics.append(
                Diagnostic(code="repository_unavailable", detail=f"repository {index}: {repository.get('status')}")
            )
            continue
        relative = repository["path"]
        base = contained(root, relative)
        scopes = [(relative, "author")]
        reviews = base / "reviews"
        if reviews.exists():
            scopes.extend(
                (str(path.relative_to(root)), path.name)
                for path in sorted(reviews.iterdir())
                if path.is_dir() and (path / ".git").is_dir()
            )
        for scope_index, (path, scope) in enumerate(scopes):
            artifact_id = f"repository-{index}-{scope_index}"
            artifacts.append(
                Artifact(artifact_id=artifact_id, kind="git_repository", uri=path, repository_id=artifact_id)
            )
            repositories[artifact_id] = contained(root, path)
            operations.extend(
                GitDocument(record, ref, artifact_id, scope)
                for record, ref, _ in read_operations(root, path, artifact_id, diagnostics)
            )
    candidates = {
        source.document[field]
        for source in operations
        for field in ("before_snapshot_id", "after_snapshot_id")
        if isinstance(source.document.get(field), str) and source.document[field]
    }
    candidates.update(
        source.document.get("attributes", {})[field]
        for source in documents["traces"]
        for field in ("repo2ree.history.before_snapshot_id", "repo2ree.history.after_snapshot_id")
        if isinstance(source.document.get("attributes"), dict)
        and isinstance(source.document["attributes"].get(field), str)
        and source.document["attributes"][field]
    )
    available = frozenset(
        (repo_id, commit)
        for repo_id, path in repositories.items()
        for commit in sorted(candidates)
        if commit_exists(path, commit)
    )
    return RecordingSnapshot(
        str(root),
        manifest,
        tuple(artifacts),
        documents["traces"],
        documents["state"],
        tuple(operations),
        available,
        tuple(diagnostics),
    )


def assemble_recording(recording_dir: Path) -> AssemblyResult:
    return assemble(load_recording(recording_dir))
