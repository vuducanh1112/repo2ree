from pathlib import Path

import pytest


@pytest.fixture
def resources_dir() -> Path:
    resources_dir = Path(__file__).parent / "resources"
    return resources_dir


@pytest.fixture
def output_dir() -> Path:
    output_dir = Path(__file__).parent / "output"
    return output_dir
