"""Fixtures for the system suite: a running deployment, reached only through its API.

The suite runs inside ``python -m repo2ree_testbed e2e`` (``just test-e2e-system``),
which owns the stack, passes its address, and collects the run's behaviour
recording afterwards. Every REE a test authors is downloaded before it is
released, as its owner would, so the recording holds each REE's Git history.
"""

from system_client import api, new_ree, pytest_collection_modifyitems

__all__ = ["api", "new_ree", "pytest_collection_modifyitems"]
