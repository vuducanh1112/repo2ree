import { describe, expect, it } from "vitest";
import type { ReeAudit } from "../ree/StepEvidence";
import type { ReeRunSummary } from "../runs/ReeRun";
import { projectCurrentSourceRun } from "./sourceRunProjection";

const audit: ReeAudit = {
  source: {
    evidence: "current",
    payload: "missing",
    receiptRunId: "source-run",
    reasons: [],
  },
};

describe("projectCurrentSourceRun", () => {
  it("reads the upload name from the backend run bound to the source receipt", () => {
    const runs: ReeRunSummary[] = [
      {
        runId: "source-run",
        operation: "source",
        status: "succeeded",
        createdAt: "2026-08-27T00:00:00Z",
        outputs: {
          mode: "upload",
          archive_name: "python-hello-world.tar.gz",
        },
      },
    ];

    expect(projectCurrentSourceRun(audit, runs)).toEqual({
      sourceState: {
        sourceAcquiredBy: "upload",
        uploadedArchive: "python-hello-world.tar.gz",
        sourceSnapshotArchive: "python-hello-world.tar.gz",
      },
      displayName: "python-hello-world.tar.gz",
    });
  });

  it("does not reuse an old run when the REE has no current source receipt", () => {
    expect(projectCurrentSourceRun({}, [])).toEqual({ sourceState: {} });
  });
});
