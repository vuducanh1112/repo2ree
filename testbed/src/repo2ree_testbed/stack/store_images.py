"""The images a stack's stores offer the REEs created in them, and the tests name.

The pins match the GUI suite's (gui/tests/helpers/flow.ts) and the provider's default bench, so a
test reads the same ref whichever compute the stack runs.
"""

from __future__ import annotations

# Python on its own: the base image is the experiment environment environment.
PYTHON_SLIM_IMAGE = (
    "docker.io/library/python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534"
)
# The Docker CLI, for REEs whose scripts build and run images with the engine they are given.
DOCKER_IMAGE = (
    "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515"
)
# What a container store offers, the first its default: the Docker CLI, as the provider's default bench.
STORE_IMAGES = (DOCKER_IMAGE, PYTHON_SLIM_IMAGE)
