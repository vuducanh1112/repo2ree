"""An upstream the stack serves, whose latest release a test publishes between an author's build and a reviewer's."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal

from typed_client import Client

from repo2ree_testbed.api_models import Run
from repo2ree_testbed.showcases import Project

Release = Literal["1.0", "2.0"]
PLACEHOLDER = "@UPSTREAM_URL@"
URL = os.environ.get("E2E_UPSTREAM_URL", "")
DIRECTORY = Path(os.environ.get("E2E_UPSTREAM_DIR", ""))


def publish(project: Project, release: Release) -> None:
    latest = DIRECTORY / "latest"
    shutil.rmtree(latest, ignore_errors=True)
    shutil.copytree(project.directory / "upstream" / release, latest)


def author(client: Client, ree_id: str, project: Project) -> None:
    """Every authoring stage, with the build fetching from this stack's upstream."""
    client.upload_source(ree_id, project)
    script = project.recipe("build_script.sh").replace(PLACEHOLDER, URL)
    build = Run.model_validate(client.api.build(ree_id, script, fixture=project))
    assert build.status == "succeeded", client.logs(ree_id, build)
    activation = client.activate(ree_id, project)
    assert activation.status == "succeeded", client.logs(ree_id, activation)
    experiment = client.run_experiment(ree_id, project)
    assert experiment.status == "succeeded", client.logs(ree_id, experiment)
