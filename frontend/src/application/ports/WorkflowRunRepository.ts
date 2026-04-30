import type { WorkflowRunLogChunk, WorkflowRunRecord, WorkflowRunStatus } from "./repositoryTypes";

export interface WorkflowRunRepository {
  startWorkflowRun(
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ): Promise<WorkflowRunRecord>;
  getWorkflowRun(id: string, runId: string): Promise<WorkflowRunRecord>;
  getWorkflowRunLogs(id: string, runId: string, cursor?: string): Promise<WorkflowRunLogChunk>;
  cancelWorkflowRun(id: string, runId: string): Promise<WorkflowRunStatus>;
}
