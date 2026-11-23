import { auditReceiptRunId, isAuditCurrent, type ReeAudit } from "../ree/StepEvidence";
import type { ReeRunSummary } from "../runs/ReeRun";
import type { WorkspaceSourceState } from "./WorkspaceSourceState";

interface SourceRunProjection {
  sourceState: Partial<WorkspaceSourceState>;
  displayName?: string;
}

export function projectCurrentSourceRun(
  audit: ReeAudit,
  runs: readonly ReeRunSummary[],
): SourceRunProjection {
  if (!isAuditCurrent(audit, "acquire_source")) {
    return { sourceState: {} };
  }

  const receiptRunId = auditReceiptRunId(audit, "acquire_source");
  const run = receiptRunId
    ? runs.find((candidate) => candidate.runId === receiptRunId)
    : runs.find(
        (candidate) => candidate.operation === "acquire_source" && candidate.status === "succeeded",
      );
  if (!run || run.operation !== "acquire_source" || run.status !== "succeeded") {
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
