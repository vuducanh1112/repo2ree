import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  getReeAssemblyRequirements,
  missingReeAssemblyRequirements,
  shouldRefreshWorkspaceAfterAssemblyStep,
} from "./assemblyPolicies";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
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

  it("requires both selected runtime and activation script for activation", () => {
    const ree = {
      ...buildRee(),
      runtime: "runtime.tar.gz",
    };

    expect(missingReeAssemblyRequirements("activation", ree)).toEqual([
      { field: "activation_script", label: "Activation script" },
    ]);
  });

  it("marks only file-producing assembly steps for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterAssemblyStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterAssemblyStep("activation")).toBe(false);
  });
});
