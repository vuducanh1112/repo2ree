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
    ]);
  });

  it("reports only unmet prerequisites for a assembly step", () => {
    const ree = {
      ...buildRee(),
      sourceAvailable: true,
    };

    expect(missingReeAssemblyRequirements("build", ree)).toEqual([]);
  });

  it("requires only runtime for activation", () => {
    const reeNoRuntime = buildRee();
    expect(missingReeAssemblyRequirements("activation", reeNoRuntime)).toEqual([
      { field: "runtime", label: "Runtime" },
    ]);

    const reeWithRuntime = { ...buildRee(), runtime: "runtime.tar.gz" };
    expect(missingReeAssemblyRequirements("activation", reeWithRuntime)).toEqual([]);
  });

  it("marks only file-producing assembly steps for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterAssemblyStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterAssemblyStep("activation")).toBe(false);
  });
});
