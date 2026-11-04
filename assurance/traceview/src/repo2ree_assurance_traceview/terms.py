"""The specification's words traceview draws by, in one place.

Traceview groups and labels evidence by the subjects, facts, states, and values the behaviour
specification names. Spelled out wherever they are used, a rename in the specification left
pages quietly empty; here, test_terms holds each one to the current specification instead.
"""

# Subjects.
REE = "Ree"
ATTEMPT = "Attempt"
ACTION = "AuthorApiAction"
RECEIPT = "Receipt"
DISPATCH = "dispatch"

# AuthorApiAction's facts, and the action that creates an REE.
ACTION_NAME = "action"
RUN_ID = "run_id"  # Carried by the long actions the author watches as runs.
ATTEMPT_ID = "attempt_id"
FAILURE_CATEGORY = "failure_category"
PROVISION = "create_ree"
LOAD_BUNDLE = "load_ree_bundle"  # Restores an REE from a bundle, as an action and as its attempt's operation.
# The actions that only read the REE, which the lifecycle leaves out: polling a run is most of them.
READS = (
    "view_ree",
    "view_ree_state",
    "read_file",
    "list_receipts",
    "view_history",
    "view_evaluation_report",
    "download_ree",
    "list_actions",
    "view_action",
    "view_action_log",
    "watch_action",
)

# Attempt's facts and states.
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

# Ree's state once frozen.
SEALED = "sealed"

# Receipt: what caused a change of standing, its standings, and its kinds in authoring order.
CAUSE = "cause"
BASELINE = "baseline"
KIND = "kind"
CURRENT = "current"
STALE = "stale"
MISSING = "missing"
NOT_APPLICABLE = "not_applicable"
STEP_ORDER = ("source", "evaluation", "hardware", "runtime", "sbom", "sbom_cross_check", "test_activation")

# A workbench's connection, its store, the facts it is drawn by, and the state it opens in.
SESSION = "WorkbenchSession"
STORE_ID = "store_id"
WORKBENCH_ID = "workbench_id"
NONCE = "nonce"
REASON = "reason"
CLOSE_CODE = "close_code"
OPENED = "opened"
LOST = "lost"
# The fact a dispatch names its session by.
SESSION_FACT = "session"

# The dispatch exchange's request, its result, and the facts read from them.
EXEC_ACTION = "exec_action"
RESULT = "result"
STATUS = "status"
