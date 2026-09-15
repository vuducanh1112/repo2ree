import json
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from repo2ree_history.core.evidence import Diagnostic
from repo2ree_history.core.models import CommitLocator, RecordLocator, SourceReference
from repo2ree_history.shell.files import contained


def git(repository: Path, *args: str) -> str:
    # No checkout, filters, hooks, or repository configuration writes.
    result = subprocess.run(
        [os.environ.get("HISTORY_GIT", "git"), "--no-pager", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1"},
    )
    return result.stdout


def commit_exists(repository: Path, commit: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        return False
    try:
        git(repository, "cat-file", "-e", commit + "^{commit}")
        return True
    except subprocess.CalledProcessError:
        return False


def read_operations(
    root: Path, relative: str, artifact_id: str, diagnostics: list[Diagnostic] | None = None
) -> Iterator[tuple[dict[str, Any], SourceReference, Path]]:
    diagnostics = diagnostics if diagnostics is not None else []
    repository = contained(root, relative)
    if (repository / ".git").is_symlink():
        raise ValueError("repository .git must be local")
    refs = git(
        repository, "for-each-ref", "--format=%(refname)", "refs/heads/ree-history", "refs/repo2ree/imports/"
    ).splitlines()
    published = set()
    if refs:
        entries = git(repository, "log", "--format=%H%x00%B%x00", *refs, "--").split("\0")
        for index in range(0, len(entries) - 1, 2):
            commit, body = entries[index].strip(), entries[index + 1]
            _, _, metadata = body.partition("\n\n")
            if not metadata.lstrip().startswith("{"):
                continue
            ref = SourceReference(artifact_id=artifact_id, locator=CommitLocator(commit_id=commit))
            try:
                value = json.loads(metadata)
                if not isinstance(value, dict):
                    raise ValueError("expected operation metadata object")
                if value.get("kind") != "operation.completed":
                    continue
                if value.get("schema_version") != 2:
                    raise ValueError("unsupported operation metadata schema")
                record = value["record"]
                if not isinstance(record, dict) or not isinstance(record.get("attempt_id"), str):
                    raise ValueError("operation record requires an attempt ID")
                published.add(record["attempt_id"])
                record = {**record, "after_snapshot_id": commit}
            except (KeyError, ValueError, TypeError) as exc:
                diagnostics.append(
                    Diagnostic(code="malformed_git_metadata", severity="invalid", detail=str(exc), source_refs=(ref,))
                )
                continue
            yield record, ref, repository
    directory = contained(root, relative + "/.git/repo2ree/operations")
    for path in sorted(directory.glob("*.json")):
        path = contained(root, str(path.relative_to(root.resolve())))
        ref = SourceReference(artifact_id=artifact_id, locator=RecordLocator(path=str(path.relative_to(repository))))
        try:
            record = json.loads(path.read_text())
            if not isinstance(record, dict) or not isinstance(record.get("attempt_id"), str):
                raise ValueError("operation record requires an attempt ID")
        except (ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(code="malformed_git_metadata", severity="invalid", detail=str(exc), source_refs=(ref,))
            )
            continue
        if record["attempt_id"] not in published:
            yield record, ref, repository
