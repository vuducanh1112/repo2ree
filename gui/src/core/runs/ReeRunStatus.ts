export type ReeRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export type TerminalReeRunFailure = Extract<ReeRunStatus, "failed" | "canceled">;

const TERMINAL_EXECUTION_RUN_STATUSES: ReadonlySet<ReeRunStatus> = new Set<ReeRunStatus>([
  "succeeded",
  "failed",
  "canceled",
]);

export function isTerminalReeRunStatus(status: ReeRunStatus | undefined): boolean {
  return status ? TERMINAL_EXECUTION_RUN_STATUSES.has(status) : false;
}

export function isTerminalReeRunFailure(status: ReeRunStatus): status is TerminalReeRunFailure {
  return status === "failed" || status === "canceled";
}
