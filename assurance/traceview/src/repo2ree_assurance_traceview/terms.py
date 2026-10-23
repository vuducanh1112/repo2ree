"""The specification's words traceview draws by, in one place.

Traceview groups and labels evidence by the subjects, facts, states, and values the behaviour
specification names. Spelled out wherever they are used, a rename in the specification left
pages quietly empty; here, test_terms holds each one to the current specification instead.
"""

# Subjects.
REE = "Ree"
ATTEMPT = "Attempt"
ACTION = "AuthorApiAction"
ALLOCATION = "Allocation"
RECEIPT = "Receipt"
DISPATCH = "dispatch"

# AuthorApiAction's facts, and the action that sets up an REE's workbench.
ACTION_NAME = "action"
RUN_ID = "run_id"  # Carried by the long actions the author watches as runs.
ATTEMPT_ID = "attempt_id"
FAILURE_CATEGORY = "failure_category"
PROVISION = "create_ree"

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

# Allocation's states that end it.
RELEASED = ("released", "failed", "lost")

# Receipt: what caused a change of standing, its standings, and its kinds in authoring order.
CAUSE = "cause"
BASELINE = "baseline"
KIND = "kind"
CURRENT = "current"
STALE = "stale"
MISSING = "missing"
NOT_APPLICABLE = "not_applicable"
STEP_ORDER = ("source", "evaluation", "hardware", "runtime", "sbom", "sbom_cross_check", "test_activation")

# The dispatch exchange's request, its result, and the facts read from them.
EXEC_ACTION = "exec_action"
RESULT = "result"
STATUS = "status"
