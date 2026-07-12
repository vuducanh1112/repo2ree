export const queryKeys = {
  workbenchImages: () => ["workbench-images"] as const,
  agents: () => ["agents"] as const,
  ree: (id: string) => ["ree", id] as const,
  evaluateReport: (reeId: string) => ["evaluate-report", reeId] as const,
  stepRuns: (reeId: string, runId: string) => ["step-run", reeId, runId] as const,
  stepRunLogs: (reeId: string, runId: string) => ["step-run-logs", reeId, runId] as const,
};
