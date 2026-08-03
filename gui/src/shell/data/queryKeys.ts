export const queryKeys = {
  workbenchImages: () => ["workbench-images"] as const,
  scriptTemplates: () => ["script-templates"] as const,
  agents: () => ["agents"] as const,
  reeIndex: (depositedOnly: boolean) => ["ree-index", depositedOnly] as const,
  ree: (id: string) => ["ree", id] as const,
  evaluateReport: (reeId: string) => ["evaluate-report", reeId] as const,
  authorReceipts: (reeId: string) => ["author-receipts", reeId] as const,
  reviews: (reeId: string) => ["reviews", reeId] as const,
  reeRuns: (reeId: string) => ["ree-runs", reeId] as const,
  stepRuns: (reeId: string, runId: string) => ["step-run", reeId, runId] as const,
  stepRunLogs: (reeId: string, runId: string) => ["step-run-logs", reeId, runId] as const,
};
