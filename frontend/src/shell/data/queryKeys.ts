export const queryKeys = {
  ree: (id: string) => ["ree", id] as const,
  evaluateReport: (reeId: string) => ["evaluate-report", reeId] as const,
  assemblyRun: (reeId: string, runId: string) => ["assembly-run", reeId, runId] as const,
  assemblyRunLogs: (reeId: string, runId: string) => ["assembly-run-logs", reeId, runId] as const,
};
