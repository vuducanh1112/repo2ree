import { describe, expect, it } from "vitest";
import { initialAutomationStepParams } from "../../application/workflow/workflowCatalog";
import type { WorkspaceSourceResetInput } from "./sourceChangeConsequences";
import { computeSourceChangeConsequences } from "./sourceChangeConsequences";

function buildWorkspaceState(): WorkspaceSourceResetInput {
  return {
    ree: {
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
      hardware_description: {
        cpus: {},
        gpus: {},
        memory: {},
        storage: {},
        network: {},
        extra_info: {},
      },
      evalLevel: 3,
      sourceAvailable: true,
      sourceAcquiredBy: "download",
      uploadedArchive: "archive.tar.gz",
      sourceSnapshotArchive: "snapshot.tar.gz",
      sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
      runtimeIncluded: true,
    },
  };
}

describe("computeSourceChangeConsequences", () => {
  it("clears workflow artifacts while preserving unrelated workspace state", () => {
    const workspace = buildWorkspaceState();
    const nextWorkflowParams = initialAutomationStepParams();

    const reset = computeSourceChangeConsequences(workspace, nextWorkflowParams);

    expect(reset.workflowParams).toEqual(nextWorkflowParams);
    expect(reset.badges).toEqual({});
    expect(reset.sourceSnapshotArchiveName).toBe("");
    expect(reset.ree.runtime).toBe("");
    expect(reset.ree.origin_url).toBe("");
    expect(reset.ree.evalLevel).toBe(0);
  });
});
