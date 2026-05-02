export const queryKeys = {
  ree: (id: string) => ["ree", id] as const,
  workflowRun: (workspaceId: string, runId: string) =>
    ["workflow-run", workspaceId, runId] as const,
  workflowRunLogs: (workspaceId: string, runId: string) =>
    ["workflow-run-logs", workspaceId, runId] as const,
  review: (id: string) => ["review", id] as const,
};
