import type { LogLine } from "../ree/ReeTypes";
import type { ReeRunStatus } from "./ReeRunStatus";

export interface ReeRun {
  runId: string;
  status: ReeRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface ReeRunLogChunk {
  lines: LogLine[];
  nextCursor?: string;
  hasMore: boolean;
}
