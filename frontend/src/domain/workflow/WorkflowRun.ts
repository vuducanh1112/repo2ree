import type { LogLine } from "../ree/ReeTypes";

export type WorkflowRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export interface WorkflowRunRecord {
  runId: string;
  status: WorkflowRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface WorkflowRunLogChunk {
  lines: LogLine[];
  nextCursor?: string;
  hasMore: boolean;
}
