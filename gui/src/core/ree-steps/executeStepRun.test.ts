import { describe, expect, it, vi } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import { executeStepRun } from "./executeStepRun";
import type { StepCommandPlannerMap } from "./stepCommands";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

function buildHandlers(): StepCommandPlannerMap {
  return {
    evaluate: () => [{ type: "toast", message: "Evaluate complete", toastType: "success" }],
    build: () => [{ type: "toast", message: "Build complete", toastType: "success" }],
    hbom: () => [{ type: "toast", message: "HBOM complete", toastType: "success" }],
    sbom: () => [{ type: "toast", message: "SBOM complete", toastType: "success" }],
    activation: () => [{ type: "toast", message: "Activation complete", toastType: "success" }],
  };
}

function executedCommands(executeCommands: ReturnType<typeof vi.fn>) {
  return executeCommands.mock.calls.flatMap(([commands]) => commands);
}

describe("executeStepRun", () => {
  it("runs a step, refreshes build outputs, and executes planned commands", async () => {
    const executeCommands = vi.fn();
    const refreshWorkspace = vi.fn(async () => ({
      files: [{ id: "runtime", name: "runtime.tar.gz", type: "file" as const }],
    }));

    const result = await executeStepRun({
      key: "build",
      params: {},
      ree: buildRee(),
      workspaceFiles: [],
      executionRunner: {
        startReeRun: vi.fn(async () => ({ runId: "run-1" })),
        pollRun: vi.fn(async () => ({
          status: "succeeded" as const,
          lines: [{ type: "ok" as const, msg: "built" }],
          ts: "2026-01-01T00:00:00Z",
        })),
      },
      stepCommandPlanners: buildHandlers(),
      executeCommands,
      refreshWorkspace,
    });

    expect(result.ts).toBe("2026-01-01T00:00:00Z");
    expect(refreshWorkspace).toHaveBeenCalled();
    expect(executedCommands(executeCommands)).toEqual([
      { type: "setActionLoading", key: "build" },
      { type: "setActiveRunId", key: "build", runId: "run-1" },
      {
        type: "completeStepRun",
        completion: {
          key: "build",
          runId: "run-1",
          stepRunLog: { lines: [{ type: "ok", msg: "built" }], ts: "2026-01-01T00:00:00Z" },
          actionState: "done",
          badge: "succeeded",
          timestamp: "2026-01-01T00:00:00Z",
        },
      },
      {
        type: "hydrateWorkspace",
        workspaceFiles: [{ id: "runtime", name: "runtime.tar.gz", type: "file" }],
        reeArtifactFiles: [],
        reeSpec: undefined,
        workspaceSourceState: undefined,
        artifactStatus: undefined,
        evaluationState: undefined,
      },
      { type: "toast", message: "Build complete", toastType: "success" },
    ]);
  });

  it("plans terminal failure feedback and refreshes workspace without running success handlers", async () => {
    const executeCommands = vi.fn();
    const refreshWorkspace = vi.fn();

    await executeStepRun({
      key: "build",
      params: {},
      ree: buildRee(),
      workspaceFiles: [],
      executionRunner: {
        startReeRun: vi.fn(async () => ({ runId: "run-1" })),
        pollRun: vi.fn(async () => ({
          status: "failed" as const,
          lines: [{ type: "err" as const, msg: "nope" }],
          ts: "2026-01-01T00:00:00Z",
        })),
      },
      stepCommandPlanners: buildHandlers(),
      executeCommands,
      refreshWorkspace,
    });

    expect(refreshWorkspace).toHaveBeenCalled();
    expect(executedCommands(executeCommands)).toContainEqual({
      type: "toast",
      message: "build failed",
      toastType: "error",
    });
    expect(executedCommands(executeCommands)).not.toContainEqual({
      type: "toast",
      message: "Build complete",
      toastType: "success",
    });
  });

  it("writes no spec patch for a deposit step", async () => {
    const executeCommands = vi.fn();

    await executeStepRun({
      key: "swh",
      params: {},
      ree: buildRee(),
      workspaceFiles: [],
      executionRunner: {
        startReeRun: vi.fn(async () => ({ runId: "run-1" })),
        pollRun: vi.fn(async () => ({
          status: "succeeded" as const,
          lines: [],
          ts: "2026-01-01T00:00:00Z",
        })),
      },
      stepCommandPlanners: buildHandlers(),
      executeCommands,
      refreshWorkspace: vi.fn(),
    });

    // The identifier a deposit yields belongs to an archive-binding attestation
    // held server-side, not to the REE spec — so the step touches no spec field.
    expect(executedCommands(executeCommands)).not.toContainEqual(
      expect.objectContaining({ type: "setReeSpec" }),
    );
  });
});
