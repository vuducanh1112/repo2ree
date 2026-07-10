import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildAssemblyRunParams,
  isTerminalExecutionRunFailure,
  planAssemblyRunCompletion,
  planManualArtifactUpdateSuccess,
  planTerminalExecutionRunFailure,
  shouldRefreshWorkspaceAfterAssemblyStep,
} from "./assemblyRunPlanning";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("assemblyRunPlanning", () => {
  it("sends empty params for activation and build runs", () => {
    const ree = buildRee();

    expect(buildAssemblyRunParams("activation", {}, ree)).toEqual({});
    expect(buildAssemblyRunParams("build", {}, ree)).toEqual({});
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

  it("plans generic assembly run completion state", () => {
    expect(planAssemblyRunCompletion("build", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: "succeeded",
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
    });
  });

  it("plans terminal failures", () => {
    expect(planTerminalExecutionRunFailure("build", "failed", "2026-01-01T00:00:00Z")).toEqual({
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
