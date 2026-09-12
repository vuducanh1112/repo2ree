"""Materialize reproduction entry points before repository capture."""

from __future__ import annotations

from pathlib import PurePosixPath

from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reproduction.reproducer import reproducer_entries


def prepare_reproducer(layout: ReeLayout, ree: Ree) -> None:
    definition = ree.subject.definition
    source = definition.source
    runtime = definition.build_runtime
    activation = definition.test_activation
    for name, content in reproducer_entries(
        activation_script=str(activation.run_script_path) if activation else "",
        activation_verify_script=str(activation.verify_script_path or "") if activation else "",
        experiments=[
            (exp.name, str(exp.run_script_path), str(exp.verify_script_path or "")) for exp in definition.experiments
        ],
        runtime_workspace_path=str(runtime.runtime_path) if runtime and runtime.runtime_path else "",
        runtime_artifact_basename=PurePosixPath(str(runtime.runtime_path)).name
        if runtime and runtime.runtime_path
        else "",
        origin_url=source.origin_url or "" if source else "",
        source_type=source.source_type if source else "",
        revision=source.requested_ref or "" if source else "",
        swhid=str(ree.subject.receipts.source.observed_swhid or "") if ree.subject.receipts.source else "",
    ):
        target = layout.root / name.removeprefix("ree/")
        if name == "run.sh":
            content = content.replace(b'REE="$HERE/ree"', b'REE="$HERE"')
        if name == "REPRODUCING.md":
            content = content.replace(b"ree/", b"./")
        write_atomic(target, content)
        if target.suffix == ".sh":
            target.chmod(0o755)
