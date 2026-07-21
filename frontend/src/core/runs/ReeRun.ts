import type { LogLine } from "../ree/ReeTypes";
import type { ReeRunStatus } from "./ReeRunStatus";

/**
 * Coarse machine-readable class of a failure, mirroring the protocol's
 * ``FailureCategory``. Lets the UI act on *why* a run failed — retry a
 * transient outage, surface a conflict, flag a validation error — without
 * parsing the log stream. Kept as a domain type (not the wire type) so core
 * stays free of the infra layer; the mapping boundary reconciles the two.
 */
export type ReeRunFailureCategory =
  | "validation"
  | "precondition"
  | "conflict"
  | "execution"
  | "timeout"
  | "unavailable"
  | "internal";

/** The component that first observed the failure, as recorded on the run. */
export type ReeRunFailureOrigin = "api" | "supervisor" | "agent" | "executor" | "core";

/** The typed reason a run reached a ``failed`` status. */
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
  /** Set on a ``failed`` run: the typed reason it did not succeed. */
  failure?: ReeRunFailure;
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
