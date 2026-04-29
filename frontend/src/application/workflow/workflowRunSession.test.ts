import { describe, expect, it, vi } from "vitest";
import { createWorkflowRunSession } from "./workflowRunSession";

describe("createWorkflowRunSession", () => {
  it("tracks active workflow runs by key", () => {
    const session = createWorkflowRunSession();

    session.noteRunStarted("build", "run-1");
    expect(session.getActiveRunId("build")).toBe("run-1");

    session.noteRunFinished("build");
    expect(session.getActiveRunId("build")).toBeUndefined();
  });

  it("merges automation step params into the existing service param map", () => {
    const session = createWorkflowRunSession();

    expect(
      session.mergeAutomationStepParams(
        {
          evaluate: { strict: false, swhid_check: true },
          build: { no_cache: true, platform: "linux/amd64" },
          hbom: {},
          sbom: { format: "spdx-json" },
          activation: { timeout: "60", verbose: false },
        },
        "build",
        { no_cache: true, platform: "linux/arm64" },
      ),
    ).toEqual({
      evaluate: { strict: false, swhid_check: true },
      build: { no_cache: true, platform: "linux/arm64" },
      hbom: {},
      sbom: { format: "spdx-json" },
      activation: { timeout: "60", verbose: false },
    });
  });

  it("cancels tracked runs through the provided adapter", async () => {
    const session = createWorkflowRunSession();
    const cancelRun = vi.fn(async () => undefined);
    session.noteRunStarted("source", "run-7");

    await expect(session.cancelTrackedRun({ key: "source", cancelRun })).resolves.toEqual({
      ok: true,
      message: "Cancel requested for source",
    });
    expect(cancelRun).toHaveBeenCalledWith("run-7");
  });

  it("surfaces cancellation failures with a user-facing message", async () => {
    const session = createWorkflowRunSession();
    session.noteRunStarted("build", "run-2");

    await expect(
      session.cancelTrackedRun({
        key: "build",
        cancelRun: vi.fn(async () => {
          throw new Error("network down");
        }),
      }),
    ).resolves.toEqual({
      ok: false,
      message: "Failed to cancel build: network down",
    });
  });
});
