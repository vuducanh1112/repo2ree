import { auditReceiptRunId, isAuditCurrent, type ReeAudit } from "../ree/StepEvidence";
import type { ReeRunSummary } from "../runs/ReeRun";
import type { WorkspaceSourceState } from "./WorkspaceSourceState";

interface SourceRunProjection {
  sourceState: Partial<WorkspaceSourceState>;
  displayName?: string;
}

/**
 * Read acquisition metadata from the backend run bound to the REE's current
 * source receipt. The original upload name is operational provenance rather
 * than part of SourceDefinition, so its durable owner is the run output.
 */
export function projectCurrentSourceRun(
  audit: ReeAudit,
  runs: readonly ReeRunSummary[],
): SourceRunProjection {
  if (!isAuditCurrent(audit, "source")) {
    return { sourceState: {} };
  }

  const receiptRunId = auditReceiptRunId(audit, "source");
  const run = receiptRunId
    ? runs.find((candidate) => candidate.runId === receiptRunId)
    : runs.find(
        (candidate) => candidate.operation === "source" && candidate.status === "succeeded",
      );
  if (!run || run.operation !== "source" || run.status !== "succeeded") {
    return { sourceState: {} };
  }

  const mode = run.outputs?.mode;
  if (mode !== "upload" && mode !== "download") {
    return { sourceState: {} };
  }

  const archiveName =
    mode === "upload" && typeof run.outputs?.archive_name === "string"
      ? run.outputs.archive_name
      : undefined;
  return {
    sourceState: {
      sourceAcquiredBy: mode,
      uploadedArchive: archiveName,
      sourceSnapshotArchive: archiveName,
    },
    displayName: archiveName,
  };
}
