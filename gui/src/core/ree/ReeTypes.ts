import type { ReeStepParams as ReeStepParamsShape } from "../ree-steps/ReeStepParams";

// Terminal outcome of a step run, kept on the badge entry so the UI can
// tell a failed run apart from a successful one.
export type StepRunOutcome = "succeeded" | "failed" | "canceled";

// `boolean` remains for writers outside the step-run flow (source
// acquisition, archive repos) that only track completion.
export type Badges = Record<string, boolean | StepRunOutcome>;

/** True only when an entry records successful completion. */
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
  /** Originating run stream, when the line came from the runs API. */
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
