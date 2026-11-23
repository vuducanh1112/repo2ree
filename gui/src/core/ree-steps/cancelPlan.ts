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
