import type { LogLine } from "../ree/ReeTypes";
import type { ReeRunStatus } from "./ReeRunStatus";

export interface ReeRun {
  runId: string;
  status: ReeRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
}

/** Backend run operation keys, as recorded on every run summary. */
export type ReeRunOperation =
  | "provision"
  | "source"
  | "build"
  | "sbom"
  | "crosscheck"
  | "hbom"
  | "activation"
  | "evaluate"
  | "swh"
  | "zenodo"
  | "dataverse"
  | "experiment";

/** A run as returned by the run-listing endpoint: a ReeRun plus its operation. */
export interface ReeRunSummary extends ReeRun {
  operation: ReeRunOperation;
}

export interface ReeRunLogChunk {
  lines: LogLine[];
  nextCursor?: string;
  hasMore: boolean;
}
