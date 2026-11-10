import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import {
  getReeStepRequirements,
  missingReeStepRequirements,
  shouldRefreshWorkspaceAfterStep,
} from "./stepPolicies";

function buildRee() {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("stepPolicies", () => {
  it("keeps step prerequisites separate from catalog metadata", () => {
    expect(getReeStepRequirements("build_experiment_environment")).toEqual([
      { field: "sourceAvailable", label: "Source available" },
    ]);
  });

  it("reports only unmet prerequisites for a step", () => {
    const ree = {
      ...buildRee(),
      sourceAvailable: true,
    };

    expect(missingReeStepRequirements("build_experiment_environment", ree)).toEqual([]);
  });

  it("requires only experiment environment for activation", () => {
    const reeNoExperimentEnvironment = buildRee();
    expect(missingReeStepRequirements("activation", reeNoExperimentEnvironment)).toEqual([
      { field: "experimentEnvironmentPath", label: "Experiment environment" },
    ]);

    const reeWithExperimentEnvironment = {
      ...buildRee(),
      experimentEnvironmentPath: "runtime.tar.gz",
    };
    expect(missingReeStepRequirements("activation", reeWithExperimentEnvironment)).toEqual([]);
  });

  it("marks only file-producing steps for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterStep("build_experiment_environment")).toBe(true);
    expect(shouldRefreshWorkspaceAfterStep("activation")).toBe(false);
  });
});
