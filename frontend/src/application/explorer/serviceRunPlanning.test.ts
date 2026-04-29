import { describe, expect, it } from "vitest";
import type { Ree } from "../../types";
import {
  buildRemoteServiceRunParams,
  deriveServiceRunLevel,
  isTerminalServiceRunFailure,
  planNonWorkflowServiceRunSuccess,
  planServiceRunCompletion,
  planTerminalServiceRunFailure,
  shouldRefreshWorkspaceAfterServiceRun,
} from "./serviceRunPlanning";

function buildRee(): Ree {
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

describe("serviceRunPlanning", () => {
  it("adds activation script only for activation runs", () => {
    const ree = buildRee();

    expect(buildRemoteServiceRunParams("activation", { timeout: "60" }, ree)).toEqual({
      timeout: "60",
      activation_script: "activate.sh",
    });
    expect(buildRemoteServiceRunParams("build", { no_cache: true }, ree)).toEqual({
      no_cache: true,
    });
  });

  it("flags failure terminal statuses", () => {
    expect(isTerminalServiceRunFailure("failed")).toBe(true);
    expect(isTerminalServiceRunFailure("canceled")).toBe(true);
    expect(isTerminalServiceRunFailure("succeeded")).toBe(false);
  });

  it("marks only build-ish runs for workspace refresh", () => {
    expect(shouldRefreshWorkspaceAfterServiceRun("build")).toBe(true);
    expect(shouldRefreshWorkspaceAfterServiceRun("hbom")).toBe(true);
    expect(shouldRefreshWorkspaceAfterServiceRun("evaluate")).toBe(false);
  });

  it("recomputes level only for evaluate runs", () => {
    expect(deriveServiceRunLevel("evaluate", 2, 4)).toBe(4);
    expect(deriveServiceRunLevel("build", 2, 4)).toBe(2);
  });

  it("plans generic service completion state", () => {
    expect(planServiceRunCompletion("build", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: true,
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
    });
  });

  it("plans terminal failures", () => {
    expect(planTerminalServiceRunFailure("build", "failed", "2026-01-01T00:00:00Z")).toEqual({
      actionState: "done",
      badge: true,
      timestamp: "2026-01-01T00:00:00Z",
      shouldRefreshWorkspace: true,
      errorMessage: "build failed",
    });
  });

  it("plans non-workflow completion patches", () => {
    expect(
      planNonWorkflowServiceRunSuccess({
        key: "swh",
        generatedSwhid: "swh:1:dir:abc",
        timestamp: "2026-01-01T00:00:00Z",
      }).reePatch?.swhid,
    ).toBe("swh:1:dir:abc");

    expect(
      planNonWorkflowServiceRunSuccess({
        key: "create",
        timestamp: "2026-01-01T00:00:00Z",
      }).lock,
    ).toBe(true);
  });
});
