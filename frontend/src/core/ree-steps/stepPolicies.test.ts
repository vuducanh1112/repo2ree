import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  getReeStepRequirements,
  missingReeStepRequirements,
  shouldRefreshWorkspaceAfterStep,
} from "./stepPolicies";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("stepPolicies", () => {
  it("keeps step prerequisites separate from catalog metadata", () => {
    expect(getReeStepRequirements("build")).toEqual([
      { field: "sourceAvailable", label: "Source available" },
    ]);
  });

  it("reports only unmet prerequisites for a step", () => {
    const ree = {
      ...buildRee(),
      sourceAvailable: true,
    };

    expect(missingReeStepRequirements("build", ree)).toEqual([]);
  });

  it("requires only runtime for activation", () => {
    const reeNoRuntime = buildRee();
    expect(missingReeStepRequirements("activation", reeNoRuntime)).toEqual([
      { field: "runtime", label: "Runtime" },
    ]);

    const reeWithRuntime = { ...buildRee(), runtime: "runtime.tar.gz" };
    expect(missingReeStepRequirements("activation", reeWithRuntime)).toEqual([]);
  });

  it("marks only file-producing steps for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterStep("activation")).toBe(false);
  });
});
