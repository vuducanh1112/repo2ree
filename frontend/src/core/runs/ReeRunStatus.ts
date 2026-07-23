// The lifecycle a backend run moves through. Declared here once: the step, the
// source-acquisition, and the experiment paths all speak this same vocabulary,
// so a new status must not have to be found in half a dozen local copies.
export type ReeRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

/** A run that reached a terminal state without succeeding. */
export type TerminalReeRunFailure = Extract<ReeRunStatus, "failed" | "canceled">;

const TERMINAL_EXECUTION_RUN_STATUSES: ReadonlySet<ReeRunStatus> = new Set<ReeRunStatus>([
  "succeeded",
  "failed",
  "canceled",
]);

export function isTerminalReeRunStatus(status: ReeRunStatus | undefined): boolean {
  return status ? TERMINAL_EXECUTION_RUN_STATUSES.has(status) : false;
}

/**
 * Terminal *and* unsuccessful — the runs a caller must report rather than treat
 * as a completed step. Cancellation counts: the work did not land.
 */
export function isTerminalReeRunFailure(status: ReeRunStatus): status is TerminalReeRunFailure {
  return status === "failed" || status === "canceled";
}
