import { describe, expect, it } from "vitest";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildWorkflowRunParams,
  deriveWorkflowStepLevel,
  isTerminalWorkflowRunFailure,
  planManualArtifactUpdateSuccess,
  planTerminalWorkflowRunFailure,
  planWorkflowRunCompletion,
  shouldRefreshWorkspaceAfterWorkflowStep,
} from "./workflowRunPolicy";

function buildRee(): ReeEditorViewModel {
  return {
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "activate.sh",
    sbom: "",
    swhid: "",
    hardware_description: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extra_info: {},
    },
  };
}

describe("workflowRunPolicy", () => {
  it("adds activation script only for activation runs", () => {
    const ree = buildRee();

    expect(buildWorkflowRunParams("activation", { timeout: "60" }, ree)).toEqual({
      activation_script_path: "activate.sh",
    });
    expect(buildWorkflowRunParams("build", { no_cache: true }, ree)).toEqual({
      build_runtime_script_path: "",
      produced_runtime_path: "",
    });
  });

  it("flags failure terminal statuses", () => {
    expect(isTerminalWorkflowRunFailure("failed")).toBe(true);
    expect(isTerminalWorkflowRunFailure("canceled")).toBe(true);
    expect(isTerminalWorkflowRunFailure("succeeded")).toBe(false);
  });

  it("marks only build-ish runs for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterWorkflowStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterWorkflowStep("hbom")).toBe(true);
    expect(shouldRefreshWorkspaceAfterWorkflowStep("evaluate")).toBe(false);
  });

  it("recomputes level only for evaluate runs", () => {
    expect(deriveWorkflowStepLevel("evaluate", 2, 4)).toBe(4);
    expect(deriveWorkflowStepLevel("build", 2, 4)).toBe(2);
  });

  it("plans generic workflow completion state", () => {
    expect(planWorkflowRunCompletion("build", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: true,
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
    });
  });

  it("plans terminal failures", () => {
    expect(planTerminalWorkflowRunFailure("build", "failed", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: true,
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
      errorMessage: "build failed",
    });
  });

  it("plans non-workflow completion patches", () => {
    expect(
      planManualArtifactUpdateSuccess({
        key: "swh",
        generatedSwhid: "swh:1:dir:abc",
        timestamp: "2026-01-01T00:00:00Z",
      }).reePatch?.swhid,
    ).toBe("swh:1:dir:abc");

    expect(
      planManualArtifactUpdateSuccess({
        key: "create",
        timestamp: "2026-01-01T00:00:00Z",
      }).lock,
    ).toBe(true);
  });
});
