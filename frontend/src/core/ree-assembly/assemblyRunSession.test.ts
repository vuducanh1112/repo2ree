import { describe, expect, it, vi } from "vitest";
import { createAssemblyRunSession } from "./assemblyRunSession";

describe("createAssemblyRunSession", () => {
  it("tracks active assembly runs by key", () => {
    const session = createAssemblyRunSession();

    session.noteRunStarted("build", "run-1");
    expect(session.getActiveRunId("build")).toBe("run-1");

    session.noteRunFinished("build");
    expect(session.getActiveRunId("build")).toBeUndefined();
  });

  it("merges automation step params into the existing assembly param map", () => {
    const session = createAssemblyRunSession();

    expect(
      session.mergeAssemblyOperationParams(
        {
          evaluate: { strict: false, swhid_check: true },
          build: {},
          hbom: {},
          sbom: { format: "spdx-json" },
          activation: { timeout: "60", verbose: false },
        },
        "activation",
        { timeout: "120", verbose: true },
      ),
    ).toEqual({
      evaluate: { strict: false, swhid_check: true },
      build: {},
      hbom: {},
      sbom: { format: "spdx-json" },
      activation: { timeout: "120", verbose: true },
    });
  });

  it("cancels tracked runs through the provided adapter", async () => {
    const session = createAssemblyRunSession();
    const cancelRun = vi.fn(async () => undefined);
    session.noteRunStarted("source", "run-7");

    await expect(session.cancelTrackedRun({ key: "source", cancelRun })).resolves.toEqual({
      ok: true,
      message: "Cancel requested for source",
    });
    expect(cancelRun).toHaveBeenCalledWith("run-7");
  });

  it("surfaces cancellation failures with a user-facing message", async () => {
    const session = createAssemblyRunSession();
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
