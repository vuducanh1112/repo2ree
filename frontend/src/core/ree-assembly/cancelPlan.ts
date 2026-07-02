// Pure decisions for cancelling an in-flight assembly/source run. The effect
// (calling the cancel API) and the state read live in the shell; this module
// only decides *whether* there is a run to cancel and *what* to tell the user.

export function planCancelRequest(activeRunId: string | undefined): { runId: string } | null {
  return activeRunId ? { runId: activeRunId } : null;
}

export function cancelSuccessMessage(key: string): string {
  return `Cancel requested for ${key}`;
}

export function cancelFailureMessage(key: string, error: unknown): string {
  return error instanceof Error
    ? `Failed to cancel ${key}: ${error.message}`
    : `Failed to cancel ${key}`;
}
