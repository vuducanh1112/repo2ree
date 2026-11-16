"""Images the testbed pins: Python on its own, as every machine is built from (testbed/environments/machine.nix),
and Docker with a daemon of its own, a reviewer's offline machine."""

from __future__ import annotations

PYTHON_SLIM_IMAGE = (
    "docker.io/library/python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534"
)
DOCKER_IMAGE = (
    "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515"
)
