import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import { initialReeAssemblyOperationParams } from "../ree-assembly/assemblyCatalog";
import type { SourceChangeInput } from "./sourceChangeConsequences";
import { computeSourceChangeConsequences } from "./sourceChangeConsequences";

function buildWorkspaceState(): SourceChangeInput {
  return {
    reeSpec: {
      ...createEmptyReeSpec(),
      name: "demo",
      origin_url: "https://example.org/repo.git",
      source_type: "git",
      runtime: "runtime.tar.gz",
      build_runtime_script: "build.sh",
      activation_script: "activate.sh",
      sbom: "sbom.json",
      swhid: "swh:1:dir:abc",
      repro_level: "L3",
      detected_dependencies: "3 dependencies",
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
    evaluationState: { evalLevel: 3 },
    actionStates: {},
    badges: {},
    timestamps: {},
    assemblyOperationParams: initialReeAssemblyOperationParams(),
  };
}

describe("computeSourceChangeConsequences", () => {
  it("clears assembly artifacts while preserving unrelated workspace state", () => {
    const workspace = buildWorkspaceState();
    const nextAssemblyOperationParams = initialReeAssemblyOperationParams();
    workspace.assemblyOperationParams = nextAssemblyOperationParams;

    const reset = computeSourceChangeConsequences(workspace);

    expect(reset.assemblyOperationParams).toEqual(nextAssemblyOperationParams);
    expect(reset.badges).toEqual({});
    expect(reset.sourceSnapshotArchiveName).toBe("");
    expect(reset.reeSpec.runtime).toBe("");
    expect(reset.reeSpec.origin_url).toBe("");
    expect(reset.evaluationState.evalLevel).toBe(0);
  });
});
