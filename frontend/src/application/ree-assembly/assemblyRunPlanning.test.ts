import { describe, expect, it } from "vitest";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildAssemblyRunParams,
  deriveReeAssemblyStepLevel,
  isTerminalExecutionRunFailure,
  planAssemblyRunCompletion,
  planManualArtifactUpdateSuccess,
  planTerminalExecutionRunFailure,
  shouldRefreshWorkspaceAfterAssemblyStep,
} from "./assemblyRunPlanning";

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

describe("assemblyRunPlanning", () => {
  it("adds activation script only for activation runs", () => {
    const ree = buildRee();

    expect(buildAssemblyRunParams("activation", { timeout: "60" }, ree)).toEqual({
      activation_script_path: "activate.sh",
    });
    expect(buildAssemblyRunParams("build", { no_cache: true }, ree)).toEqual({
      build_runtime_script_path: "",
      produced_runtime_path: "",
    });
  });

  it("flags failure terminal statuses", () => {
    expect(isTerminalExecutionRunFailure("failed")).toBe(true);
    expect(isTerminalExecutionRunFailure("canceled")).toBe(true);
    expect(isTerminalExecutionRunFailure("succeeded")).toBe(false);
  });

  it("marks only build-ish runs for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterAssemblyStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterAssemblyStep("hbom")).toBe(true);
    expect(shouldRefreshWorkspaceAfterAssemblyStep("evaluate")).toBe(false);
  });

  it("recomputes level only for evaluate runs", () => {
    expect(deriveReeAssemblyStepLevel("evaluate", 2, 4)).toBe(4);
    expect(deriveReeAssemblyStepLevel("build", 2, 4)).toBe(2);
  });

  it("plans generic assembly run completion state", () => {
    expect(planAssemblyRunCompletion("build", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: true,
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
    });
  });

  it("plans terminal failures", () => {
    expect(planTerminalExecutionRunFailure("build", "failed", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: true,
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
      errorMessage: "build failed",
    });
  });

  it("plans manual artifact completion patches", () => {
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
