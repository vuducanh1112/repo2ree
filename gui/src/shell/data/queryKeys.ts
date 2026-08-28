export const queryKeys = {
  reeSteps: () => ["ree-steps"] as const,
  workbenchImages: () => ["workbench-images"] as const,
  scriptTemplates: () => ["script-templates"] as const,
  agents: () => ["agents"] as const,
  reeIndex: (depositedOnly: boolean) => ["ree-index", depositedOnly] as const,
  ree: (id: string) => ["ree", id] as const,
  evaluateReport: (reeId: string) => ["evaluate-report", reeId] as const,
  reviews: (reeId: string) => ["reviews", reeId] as const,
  scriptLintDraft: (kind: string, experimentName: string, source: string) =>
    ["script-lint-draft", kind, experimentName, source] as const,
  scriptLintSaved: (reeId: string, kind: string, experimentName: string, source: string) =>
    ["script-lint-saved", reeId, kind, experimentName, source] as const,
  reeRuns: (reeId: string) => ["ree-runs", reeId] as const,
  stepRuns: (reeId: string, runId: string) => ["step-run", reeId, runId] as const,
  stepRunLogs: (reeId: string, runId: string) => ["step-run-logs", reeId, runId] as const,
};
