import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import {
  buildStepRunParams,
  planManualArtifactUpdateSuccess,
  planStepRunCompletion,
  planTerminalReeRunFailure,
  shouldRefreshWorkspaceAfterStep,
} from "./stepRunPlanning";

function buildRee() {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("stepRunPlanning", () => {
  it("sends empty params for activation and build runs", () => {
    const ree = buildRee();

    expect(buildStepRunParams("activation", {}, ree)).toEqual({});
    expect(buildStepRunParams("build_experiment_environment", {}, ree)).toEqual({});
  });

  it("marks only build-ish runs for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterStep("build_experiment_environment")).toBe(true);
    expect(shouldRefreshWorkspaceAfterStep("hbom")).toBe(true);
    expect(shouldRefreshWorkspaceAfterStep("evaluate")).toBe(false);
  });

  it("plans generic step run completion state", () => {
    expect(planStepRunCompletion("build_experiment_environment", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: "succeeded",
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
    });
  });

  it("plans terminal failures", () => {
    expect(
      planTerminalReeRunFailure("build_experiment_environment", "failed", "2026-01-01T00:00:00Z"),
    ).toEqual({
      actionState: "done",
      badge: "failed",
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
      errorMessage: "build_experiment_environment failed",
    });
  });

  it("plans manual artifact completion patches", () => {
    // Deposit steps settle server-side as archive-binding attestations, so they
    // carry no spec patch — only the completion bookkeeping.
    expect(
      planManualArtifactUpdateSuccess({
        key: "swh",
        timestamp: "2026-01-01T00:00:00Z",
      }).reeSpecPatch,
    ).toBeUndefined();

    expect(
      planManualArtifactUpdateSuccess({
        key: "create",
        timestamp: "2026-01-01T00:00:00Z",
      }).lock,
    ).toBe(true);
  });
});
