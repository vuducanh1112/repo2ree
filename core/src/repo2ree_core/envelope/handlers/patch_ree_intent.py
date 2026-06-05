"""Handler for the patch_ree_intent operation.

Applies a partial patch to reeIntent in /ree/.workspace.json.
All ReeIntent fields are user-editable; no whitelist needed.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.envelope.handlers._common import patch_ree_intent
from repo2ree_protocol.command import PatchReeIntentArgs
from repo2ree_protocol.result import ActionResult
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck

_INTENT_FIELDS: frozenset[str] = frozenset(ReeIntent.model_fields)


def handle_patch_ree_intent(
    args: PatchReeIntentArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "patch_ree_intent canceled before start")
        return ActionResult(status="canceled")

    unsupported = sorted(set(args.patch) - _INTENT_FIELDS)
    if unsupported:
        log("system", "error", f"patch contains unknown fields: {unsupported}")
        return ActionResult(status="failed", exit_code=1)

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        log("system", "error", "metadata not found — was init-ree run?")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", f"patch_ree_intent: {sorted(args.patch)}")
    try:
        patch_ree_intent(store, args.patch)
    except Exception as exc:
        log("system", "error", f"patch_ree_intent failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    return ActionResult(status="succeeded", exit_code=0)
