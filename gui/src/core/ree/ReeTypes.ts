import type { ReeStepParams as ReeStepParamsShape } from "../ree-steps/ReeStepParams";

export type StepRunOutcome = "succeeded" | "failed" | "canceled";

export type Badges = Record<string, boolean | StepRunOutcome>;

export function isSuccessfulStepOutcome(value: Badges[string] | undefined): boolean {
  return value === true || value === "succeeded";
}

export type Timestamps = Record<string, string>;
export type ActionStates = Record<string, "loading" | "done">;
export type ReeRunLogs = Record<string, LogEntry>;
export type ReeStepParams = ReeStepParamsShape;

export interface LogLine {
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
  ts?: string;
  stream?: "stdout" | "stderr" | "system";
}

export interface LogEntry {
  lines: LogLine[];
  ts: string;
}

export interface SourceUploadCommit {
  mode: "archive";
  archiveName?: string;
  archiveFile?: File;
}

export interface ReeFile {
  id: string;
  name: string;
  type: "file";
  tag?: string;
  content?: string;
  size?: number;
}
