REE = "Ree"
ATTEMPT = "Attempt"
ACTION = "AuthorApiAction"
RECEIPT = "Receipt"
START_RUN = "start_run"
FOLLOW_RUN = "follow_run"

ACTION_NAME = "action"
RUN_ID = "run_id"
ATTEMPT_ID = "attempt_id"
FAILURE_CATEGORY = "failure_category"
PROVISION = "create_ree"
LOAD_BUNDLE = "load_ree_bundle"
READS = (
    "view_ree",
    "view_ree_state",
    "read_file",
    "list_receipts",
    "view_history",
    "view_reproducibility_report",
    "download_ree",
    "list_actions",
    "view_action",
    "view_action_log",
    "watch_action",
)

OPERATION = "operation"
OUTCOME = "outcome"
COMMIT = "commit"
CHANGED = "changed"
SUCCEEDED = "succeeded"
PENDING = "pending"
EXECUTING = "executing"
COMPLETED = "completed"
CAPTURED = "captured"
CAPTURE_FAILED = "capture_failed"

SEALED = "sealed"

CAUSE = "cause"
BASELINE = "baseline"
KIND = "kind"
CURRENT = "current"
STALE = "stale"
MISSING = "missing"
NOT_APPLICABLE = "not_applicable"
STEP_ORDER = (
    "acquire_source",
    "evaluate_reproducibility",
    "observe_hardware",
    "build_experiment_environment",
    "generate_sbom",
    "cross_check_sbom",
    "activate_experiment_environment",
)

SESSION = "WorkbenchSession"
STORE_ID = "store_id"
WORKBENCH_ID = "workbench_id"
NONCE = "nonce"
REASON = "reason"
CLOSE_CODE = "close_code"
OPENED = "opened"
LOST = "lost"
SESSION_FACT = "session"

STATUS = "status"
