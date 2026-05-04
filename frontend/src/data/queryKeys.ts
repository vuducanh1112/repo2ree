export const queryKeys = {
  ree: (id: string) => ["ree", id] as const,
  workflowRun: (reeId: string, runId: string) => ["workflow-run", reeId, runId] as const,
  workflowRunLogs: (reeId: string, runId: string) => ["workflow-run-logs", reeId, runId] as const,
  review: (id: string) => ["review", id] as const,
};
