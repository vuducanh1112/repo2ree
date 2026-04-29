import type { AutomationStepParams } from "./workflow";

export type {
  CPUDefinition,
  GPUDefinition,
  HBOM,
  MemoryDefinition,
  NetworkDefinition,
  Ree,
  StorageDefinition,
} from "./reeModel";

export type Badges = Record<string, boolean>;
export type Timestamps = Record<string, string>;
export type ActionStates = Record<string, "loading" | "done">;
export type ServiceLogs = Record<string, LogEntry>;
export type ServiceParams = AutomationStepParams;

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
