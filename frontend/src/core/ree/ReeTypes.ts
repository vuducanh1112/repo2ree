import type { ReeAssemblyOperationParams as ReeAssemblyOperationParamsShape } from "../ree-assembly/ReeAssemblyOperationParams";

// Terminal outcome of an assembly run, kept on the badge entry so the UI can
// tell a failed run apart from a successful one. Values are truthy on purpose:
// consumers that only care about "has this step run" keep using `!!badges[key]`.
export type AssemblyRunOutcome = "succeeded" | "failed" | "canceled";

// `boolean` remains for writers outside the assembly-run flow (source
// acquisition, archive repos) that only track completion.
export type Badges = Record<string, boolean | AssemblyRunOutcome>;

/** True when the entry records a run that finished without succeeding. */
export function isFailedAssemblyOutcome(value: Badges[string] | undefined): boolean {
  return value === "failed" || value === "canceled";
}
export type Timestamps = Record<string, string>;
export type ActionStates = Record<string, "loading" | "done">;
export type ExecutionRunLogs = Record<string, LogEntry>;
export type ReeAssemblyOperationParams = ReeAssemblyOperationParamsShape;

export interface LogLine {
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
  ts?: string;
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
