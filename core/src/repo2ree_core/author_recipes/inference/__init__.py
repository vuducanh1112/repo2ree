from __future__ import annotations

from repo2ree_authoring.targets import resolve_target
from repo2ree_core.author_recipes.inference.inference import ENGINE_VERSION, infer_scripts
from repo2ree_protocol.command import ScriptTarget
from repo2ree_protocol.inference import InferenceReport, ScriptCandidate, TargetInferenceResult

__all__ = [
    "ENGINE_VERSION",
    "InferenceReport",
    "ScriptCandidate",
    "ScriptTarget",
    "TargetInferenceResult",
    "infer_scripts",
    "resolve_target",
]
