import { describe, expect, it } from "vitest";
import type { ReeView } from "../../domain/ree/ReeView";
import {
  getReeAssemblyRequirements,
  missingReeAssemblyRequirements,
  shouldRefreshWorkspaceAfterAssemblyStep,
} from "./assemblyPolicies";

function buildRee(): ReeView {
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

describe("assemblyPolicies", () => {
  it("keeps assembly prerequisites separate from catalog metadata", () => {
    expect(getReeAssemblyRequirements("build")).toEqual([
      { field: "sourceAvailable", label: "Source available" },
      { field: "build_runtime_script", label: "Build script" },
    ]);
  });

  it("reports only unmet prerequisites for a assembly step", () => {
    const ree = {
      ...buildRee(),
      sourceAvailable: true,
    };

    expect(missingReeAssemblyRequirements("build", ree)).toEqual([
      { field: "build_runtime_script", label: "Build script" },
    ]);
  });

  it("marks only file-producing assembly steps for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterAssemblyStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterAssemblyStep("activation")).toBe(false);
  });
});
