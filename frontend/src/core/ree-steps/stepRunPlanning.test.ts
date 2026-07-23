import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildStepRunParams,
  planManualArtifactUpdateSuccess,
  planStepRunCompletion,
  planTerminalReeRunFailure,
  shouldRefreshWorkspaceAfterStep,
} from "./stepRunPlanning";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("stepRunPlanning", () => {
  it("sends empty params for activation and build runs", () => {
    const ree = buildRee();

    expect(buildStepRunParams("activation", {}, ree)).toEqual({});
    expect(buildStepRunParams("build", {}, ree)).toEqual({});
  });

  it("marks only build-ish runs for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterStep("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterStep("hbom")).toBe(true);
    expect(shouldRefreshWorkspaceAfterStep("evaluate")).toBe(false);
  });

  it("plans generic step run completion state", () => {
    expect(planStepRunCompletion("build", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: "succeeded",
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
    });
  });

  it("plans terminal failures", () => {
    expect(planTerminalReeRunFailure("build", "failed", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: "failed",
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
      }).reeSpecPatch?.swhid,
    ).toBe("swh:1:dir:abc");

    expect(
      planManualArtifactUpdateSuccess({
        key: "create",
        timestamp: "2026-01-01T00:00:00Z",
      }).lock,
    ).toBe(true);
  });
});
