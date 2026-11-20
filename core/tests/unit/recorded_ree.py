"""A test's REE with files it wrote itself, as if an attempt had recorded them."""

from __future__ import annotations

from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.integrity import stamp_ree
from repo2ree_core.persistence.layout import ReeLayout


def as_recorded(layout: ReeLayout) -> ReeLayout:
    """Commit and stamp the REE's files as they are: a test's setup, which is no drift of the REE it sets up."""
    with open_history(layout) as history:
        history.capture(operation="observe_existing_ree", reuse_unchanged=True)
    stamp_ree(layout)
    return layout
