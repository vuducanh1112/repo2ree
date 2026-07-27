"""Handler for the patch_ree_intent operation.

Applies a partial patch to reeIntent in /ree/.workspace.json.
All ReeIntent fields are user-editable; no whitelist needed.
"""

from __future__ import annotations

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.envelope.handlers._common import open_ree_store, patch_ree_intent
from repo2ree_core.receipts import prune_author_experiment_receipts
from repo2ree_core.run_script import CancelCheck
from repo2ree_protocol.command import PatchReeIntentArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

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
        return ActionResult.failed(
            "validation",
            f"patch contains unknown fields: {unsupported}",
            details={"fields": unsupported},
        )

    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    if args.expected_version:
        actual_version = store.read_metadata().updated_at
        if args.expected_version != actual_version:
            log(
                "system",
                "error",
                f"intent version mismatch: expected {args.expected_version}, actual {actual_version}",
            )
            return ActionResult.failed(
                "conflict",
                "REE intent changed since it was read",
                retryable=True,
                outputs={
                    "expected_version": args.expected_version,
                    "actual_version": actual_version,
                },
            )

    log("system", "info", f"patch_ree_intent: {sorted(args.patch)}")
    try:
        patch_ree_intent(store, args.patch)
        prune_author_experiment_receipts(layout, store.read_intent())
    except Exception as exc:
        log("system", "error", f"patch_ree_intent failed: {exc}")
        return ActionResult.failed("internal", f"patch_ree_intent failed: {exc}")

    return ActionResult(status="succeeded", exit_code=0)
