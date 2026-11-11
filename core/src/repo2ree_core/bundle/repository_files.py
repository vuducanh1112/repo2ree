"""Materialize reproduction entry points before repository capture."""

from __future__ import annotations

from pathlib import PurePosixPath

from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reproduction.reproducer import reproducer_entries
from repo2ree_ree.model import Ree


def prepare_reproducer(layout: ReeLayout, ree: Ree) -> None:
    definition = ree.subject.definition
    source = definition.source
    experiment_environment = definition.experiment_environment
    activate = definition.activate_experiment_environment
    for name, content in reproducer_entries(
        activate_experiment_environment_script=str(activate.activate_experiment_environment_script_path)
        if activate
        else "",
        experiments=[
            (exp.name, str(exp.run_script_path), str(exp.verify_script_path or "")) for exp in definition.experiments
        ],
        experiment_environment_workspace_path=str(experiment_environment.artifact_path)
        if experiment_environment and experiment_environment.artifact_path
        else "",
        experiment_environment_artifact_basename=PurePosixPath(str(experiment_environment.artifact_path)).name
        if experiment_environment and experiment_environment.artifact_path
        else "",
        origin_url=source.origin_url or "" if source else "",
        source_type=source.source_type if source else "",
        revision=source.requested_ref or "" if source else "",
        swhid=str(ree.subject.receipts.source.observed_swhid or "") if ree.subject.receipts.source else "",
        workbench_environment=definition.workbench_environment,
    ):
        target = layout.root / name.removeprefix("ree/")
        if name == "run.sh":
            content = content.replace(b'REE="$HERE/ree"', b'REE="$HERE"')
        if name == "REPRODUCING.md":
            content = content.replace(b"ree/", b"./")
        write_atomic(target, content)
        if target.suffix == ".sh":
            target.chmod(0o755)
