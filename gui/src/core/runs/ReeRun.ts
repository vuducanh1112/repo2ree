import { isOneOf } from "@core/contract/unknownNames";
import { RECEIPT_OPERATIONS, type ReeRunOperation } from "@core/generated/vocabulary";
import type { LogLine } from "../ree/ReeTypes";
import type { ReeRunStatus } from "./ReeRunStatus";

export type ReeRunFailureCategory =
  | "validation"
  | "precondition"
  | "conflict"
  | "execution"
  | "timeout"
  | "unavailable"
  | "internal";

export type ReeRunFailureOrigin = "api" | "supervisor" | "workbench" | "executor" | "core";

export interface ReeRunFailure {
  category: ReeRunFailureCategory;
  message: string;
  retryable: boolean;
  origin: ReeRunFailureOrigin;
  details?: Record<string, unknown>;
}

export interface ReeRun {
  runId: string;
  status: ReeRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  failure?: ReeRunFailure;
  outputs?: Record<string, unknown>;
}

export function filesReceipt(operation: ReeRunOperation): boolean {
  return isOneOf(RECEIPT_OPERATIONS, operation);
}

export interface ReeRunSummary extends ReeRun {
  operation: ReeRunOperation;
}

export interface ReeRunLogChunk {
  lines: LogLine[];
  nextCursor?: string;
  hasMore: boolean;
}
