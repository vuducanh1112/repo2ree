import type { LogLine } from "../ree/ReeTypes";
import type { ExecutionRunStatus } from "./ExecutionRunStatus";

export interface ExecutionRun {
  runId: string;
  status: ExecutionRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface ExecutionRunLogChunk {
  lines: LogLine[];
  nextCursor?: string;
  hasMore: boolean;
}
