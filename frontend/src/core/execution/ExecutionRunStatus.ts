export type ExecutionRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

const TERMINAL_EXECUTION_RUN_STATUSES: ReadonlySet<ExecutionRunStatus> =
  new Set<ExecutionRunStatus>(["succeeded", "failed", "canceled"]);

export function isTerminalExecutionRunStatus(status: ExecutionRunStatus | undefined): boolean {
  return status ? TERMINAL_EXECUTION_RUN_STATUSES.has(status) : false;
}
