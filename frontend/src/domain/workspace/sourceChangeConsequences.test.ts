import { describe, expect, it } from "vitest";
import { initialAutomationStepParams } from "../../application/workflow/WorkflowStepDefinitions";
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
      _evalLevel: 3,
      _sourceAvailable: true,
      _sourceAcquiredBy: "download",
      _uploadedArchive: "archive.tar.gz",
      _sourceSnapshotArchive: "snapshot.tar.gz",
      _sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
      _runtimeIncluded: true,
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
    expect(reset.workspaceFiles).toEqual([]);
    expect(reset.ree.runtime).toBe("");
    expect(reset.ree.origin_url).toBe("");
    expect(reset.ree._evalLevel).toBe(0);
  });
});
