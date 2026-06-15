"""Pure construction of the published REE manifest.

The manifest is the JSON payload written to ``manifest.json`` and embedded
into the downloadable bundle as ``ree/ree.json``. It is computed from a
:class:`~repo2ree_core.domain.ree_intent.ReeIntent` and a
:class:`~repo2ree_core.domain.ree_session.ReeSession` together with the
surrounding workspace metadata. This module performs no I/O.
"""

from __future__ import annotations

from typing import Any

from repo2ree_core.domain.ree_intent import REE_MANIFEST_VERSION, ReeIntent
from repo2ree_core.domain.ree_session import ReeSession

_SESSION_MANIFEST_EXCLUDE = {"detected_dependencies", "uploaded_archive", "source_resolved_commit"}


def build_manifest_payload(
    intent: ReeIntent,
    session: ReeSession,
    *,
    ree_id: str,
) -> dict[str, Any]:
    """Build the published manifest from ``intent`` and ``session``."""
    return {
        **intent.model_dump(),
        **session.model_dump(exclude=_SESSION_MANIFEST_EXCLUDE),
        "ree_version": REE_MANIFEST_VERSION,
        "name": intent.name or f"workspace-{ree_id[:8]}",
    }
