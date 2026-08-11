"""Read-only inference of repo2ree's author-facing shell scripts.

Inference produces candidate shell bytes from repository evidence and presents
them; it never writes. The published, versioned decision DAG is the sole
control-flow authority (see ``engine`` and ``registry``). Design overview:
``docs/engineering/explanation/script-inference.md``.
"""

from __future__ import annotations

from repo2ree_core.author_recipes.inference.inference import (
    ENGINE_VERSION,
    infer_scripts,
    resolve_target,
)
from repo2ree_core.author_recipes.inference.models import (
    InferenceReport,
    ScriptCandidate,
    ScriptTarget,
    ScriptTargetSelector,
    TargetInferenceResult,
)

__all__ = [
    "ENGINE_VERSION",
    "InferenceReport",
    "ScriptCandidate",
    "ScriptTarget",
    "ScriptTargetSelector",
    "TargetInferenceResult",
    "infer_scripts",
    "resolve_target",
]
