import pytest
from pydantic import ValidationError
from repo2ree_core.domain.ree import REE


# ================================================
# Helpers
# ================================================


def _ree_with_experiments(*names: str) -> REE:
    return REE.model_validate(
        {
            "name": "demo",
            "experiments": [{"name": n, "command": "pytest"} for n in names],
        }
    )


# ================================================
# Experiment name uniqueness
# ================================================


def test_unique_experiment_names_accepts_distinct_names():
    ree = _ree_with_experiments("smoke", "integration", "benchmark")
    assert [e.name for e in ree.experiments] == ["smoke", "integration", "benchmark"]


def test_unique_experiment_names_rejects_duplicates():
    with pytest.raises(ValidationError, match="experiment names must be unique"):
        _ree_with_experiments("smoke", "integration", "smoke")


def test_unique_experiment_names_allows_multiple_empty_names():
    # Empty names are work-in-progress; uniqueness is only enforced for filled names.
    ree = _ree_with_experiments("", "", "smoke")
    assert len(ree.experiments) == 3


def test_unique_experiment_names_allows_empty_list():
    ree = REE(name="demo")
    assert ree.experiments == []
