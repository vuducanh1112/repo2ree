import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import { initialReeStepParams } from "../ree-steps/stepCatalog";
import type { SourceChangeInput } from "./sourceChangeConsequences";
import { computeSourceChangeConsequences } from "./sourceChangeConsequences";

function buildWorkspaceState(): SourceChangeInput {
  return {
    reeSpec: {
      ...createEmptyReeSpec(),
      name: "demo",
      originUrl: "https://example.org/repo.git",
      sourceType: "git",
      runtime: "runtime.tar.gz",
      sbom: "artifacts/sbom.json",
      swhid: "swh:1:dir:abc",
    },
    workspaceSourceState: {
      sourceAvailable: true,
      sourceAcquiredBy: "download",
      uploadedArchive: "archive.tar.gz",
      sourceSnapshotArchive: "snapshot.tar.gz",
      sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
    },
    artifactStatus: {
      runtimeIncluded: true,
    },
    evaluationState: { dependencyLevel: 3 },
    actionStates: {},
    badges: {},
    timestamps: {},
    stepParams: initialReeStepParams(),
  };
}

describe("computeSourceChangeConsequences", () => {
  it("clears step artifacts while preserving unrelated workspace state", () => {
    const workspace = buildWorkspaceState();
    const nextStepParams = initialReeStepParams();
    workspace.stepParams = nextStepParams;

    const reset = computeSourceChangeConsequences(workspace);

    expect(reset.stepParams).toEqual(nextStepParams);
    expect(reset.badges).toEqual({});
    expect(reset.sourceSnapshotArchiveName).toBe("");
    expect(reset.reeSpec.runtime).toBe("");
    expect(reset.reeSpec.originUrl).toBe("");
    expect(reset.evaluationState.dependencyLevel).toBe(0);
  });
});
