import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import { initialReeStepParams } from "@core/ree-steps/stepCatalog";
import type { StepCommand } from "@core/ree-steps/stepCommands";
import type { SourceCommand } from "@core/workspace/sourceAcquisitionCommands";
import { describe, expect, it, vi } from "vitest";
import { executeSourceCommands, executeStepCommands } from "./stepActionEffects";

describe("stepActionEffects", () => {
  it("executes every step command through typed shell effects", () => {
    const dispatch = vi.fn();
    const persistWorkspaceFile = vi.fn();
    const showToast = vi.fn();
    const reeSpec = { ...createEmptyReeSpec(), name: "Hydrated" };
    const commands: StepCommand[] = [
      { type: "setActionLoading", key: "build" },
      { type: "setActiveRunId", key: "build", runId: "run-1" },
      { type: "setStepRunLog", key: "build", lines: [], ts: "ignored" },
      {
        type: "completeStepRun",
        completion: {
          key: "build",
          runId: "run-1",
          stepRunLog: { lines: [], ts: "2026-01-01" },
          actionState: "done",
          badge: "succeeded",
          timestamp: "2026-01-01",
        },
      },
      {
        type: "hydrateWorkspace",
        workspaceFiles: [],
        reeSpec,
        workspaceSourceState: { sourceAvailable: true },
        artifactStatus: { runtimeIncluded: true },
        evaluationState: { dependencyLevel: 2, environmentLevel: 1, machineLevel: 0 },
      },
      { type: "persistFile", path: "result.txt", content: "ok" },
      { type: "setReeSpec", reeSpec: { name: "Patched" } },
      { type: "setArtifactStatus", artifactStatus: { runtimeIncluded: false } },
      { type: "setEvaluationState", evaluationState: { dependencyLevel: 3 } },
      { type: "setLocked", locked: true },
      { type: "toast", message: "Done", toastType: "success" },
    ];

    executeStepCommands(commands, { dispatch, persistWorkspaceFile, showToast });

    expect(dispatch.mock.calls.map(([action]) => action.type)).toEqual([
      "updateReeSpec",
      "updateReeSpec",
    ]);
    expect(persistWorkspaceFile).toHaveBeenCalledWith("result.txt", "ok");
    expect(showToast).toHaveBeenCalledWith("Done", "success");
  });

  it("executes source state, hydration, outcome and toast commands", () => {
    const dispatch = vi.fn();
    const showToast = vi.fn();
    const commands: SourceCommand[] = [
      { type: "setSourceLoading" },
      { type: "setSourceLog", lines: [], ts: "ignored" },
      { type: "setActiveRunId", key: "source", runId: "run-source" },
      { type: "resetStepsAfterSourceChange", stepParams: initialReeStepParams() },
      {
        type: "hydrateWorkspace",
        workspaceFiles: [],
        reeSpec: createEmptyReeSpec(),
        workspaceSourceState: { sourceAvailable: true },
        artifactStatus: { runtimeIncluded: false },
        evaluationState: { dependencyLevel: 1, environmentLevel: 2, machineLevel: 3 },
      },
      {
        type: "applySourceOutcome",
        outcome: { runId: "run-source", sourceSnapshotArchiveName: "source.tar.gz" },
      },
      { type: "toast", message: "Acquired", toastType: "success" },
    ];

    executeSourceCommands(commands, { dispatch, showToast });

    expect(dispatch.mock.calls.map(([action]) => action.type)).toEqual([
      "resetStepsAfterSourceChange",
      "updateReeSpec",
      "applySourceOutcome",
    ]);
    expect(showToast).toHaveBeenCalledWith("Acquired", "success");
  });
});
