import { describe, expect, it } from "vitest";
import type { ReeViewState } from "../../domain/ree/ReeViewState";
import {
  getWorkflowRequirements,
  missingWorkflowRequirements,
  shouldRefreshWorkspaceAfterWorkflowStep,
} from "./workflowPolicies";

function buildRee(): ReeViewState {
  return {
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
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

describe("workflowPolicies", () => {
  it("keeps workflow prerequisites separate from catalog metadata", () => {
    expect(getWorkflowRequirements("build")).toEqual([
      { field: "sourceAvailable", label: "Source available" },
      { field: "build_runtime_script", label: "Build script" },
    ]);
  });

  it("reports only unmet prerequisites for a workflow step", () => {
    const ree = {
      ...buildRee(),
      sourceAvailable: true,
    };

    expect(missingWorkflowRequirements("build", ree)).toEqual([
      { field: "build_runtime_script", label: "Build script" },
    ]);
  });

  it("marks only file-producing workflows for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterWorkflowStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterWorkflowStep("activation")).toBe(false);
  });
});
