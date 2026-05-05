import { describe, expect, it, vi } from "vitest";
import type { ReeView } from "../../domain/ree/ReeView";
import type { AssemblyCommandPlannerMap } from "./assemblyCommands";
import { executeAssemblyRun } from "./executeAssemblyRun";

function buildRee(): ReeView {
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

function buildHandlers(): AssemblyCommandPlannerMap {
  return {
    evaluate: (_params, newLevel) => [
      { type: "patchRee", patch: { evalLevel: newLevel } },
      { type: "toast", message: `Evaluated at L${newLevel}`, toastType: "success" },
    ],
    build: () => [{ type: "toast", message: "Build complete", toastType: "success" }],
    hbom: () => [{ type: "toast", message: "HBOM complete", toastType: "success" }],
    sbom: () => [{ type: "toast", message: "SBOM complete", toastType: "success" }],
    activation: () => [{ type: "toast", message: "Activation complete", toastType: "success" }],
  };
}

const generatedIds = {
  swhid: "swh:1:dir:abc",
  zenodoDoi: "10.5281/zenodo.1234567",
  dataverseDoi: "doi:10.5072/DVN/123456",
};

function executedCommands(executeCommands: ReturnType<typeof vi.fn>) {
  return executeCommands.mock.calls.flatMap(([commands]) => commands);
}

describe("executeAssemblyRun", () => {
  it("runs a workflow step, refreshes build outputs, and executes planned commands", async () => {
    const executeCommands = vi.fn();
    const refreshWorkspace = vi.fn(async () => ({
      files: [{ id: "runtime", name: "runtime.tar.gz", type: "file" as const }],
    }));

    const result = await executeAssemblyRun({
      key: "build",
      params: { no_cache: true },
      ree: buildRee(),
      level: 2,
      workspaceFiles: [],
      executionRunner: {
        startExecutionRun: vi.fn(async () => ({ runId: "run-1" })),
        pollRun: vi.fn(async () => ({
          status: "succeeded" as const,
          lines: [{ type: "ok" as const, msg: "built" }],
          ts: "2026-01-01T00:00:00Z",
        })),
      },
      assemblyCommandPlanners: buildHandlers(),
      generatedIds,
      executeCommands,
      refreshWorkspace,
    });

    expect(result.ts).toBe("2026-01-01T00:00:00Z");
    expect(refreshWorkspace).toHaveBeenCalled();
    expect(executedCommands(executeCommands)).toEqual([
      { type: "setActionLoading", key: "build" },
      { type: "setActiveRunId", key: "build", runId: "run-1" },
      {
        type: "completeAssemblyRun",
        completion: {
          key: "build",
          assemblyRunLog: { lines: [{ type: "ok", msg: "built" }], ts: "2026-01-01T00:00:00Z" },
          actionState: "done",
          badge: true,
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

  it("plans terminal failure feedback without refreshing or running success handlers", async () => {
    const executeCommands = vi.fn();
    const refreshWorkspace = vi.fn();

    await executeAssemblyRun({
      key: "build",
      params: {},
      ree: buildRee(),
      level: 2,
      workspaceFiles: [],
      executionRunner: {
        startExecutionRun: vi.fn(async () => ({ runId: "run-1" })),
        pollRun: vi.fn(async () => ({
          status: "failed" as const,
          lines: [{ type: "err" as const, msg: "nope" }],
          ts: "2026-01-01T00:00:00Z",
        })),
      },
      assemblyCommandPlanners: buildHandlers(),
      generatedIds,
      executeCommands,
      refreshWorkspace,
    });

    expect(refreshWorkspace).not.toHaveBeenCalled();
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

  it("uses generated IDs for non-workflow completion patches", async () => {
    const executeCommands = vi.fn();

    await executeAssemblyRun({
      key: "swh",
      params: {},
      ree: buildRee(),
      level: 2,
      workspaceFiles: [],
      executionRunner: {
        startExecutionRun: vi.fn(async () => ({ runId: "run-1" })),
        pollRun: vi.fn(async () => ({
          status: "succeeded" as const,
          lines: [],
          ts: "2026-01-01T00:00:00Z",
        })),
      },
      assemblyCommandPlanners: buildHandlers(),
      generatedIds,
      executeCommands,
      refreshWorkspace: vi.fn(),
    });

    expect(executedCommands(executeCommands)).toContainEqual({
      type: "patchRee",
      patch: { swhid: "swh:1:dir:abc" },
    });
  });
});
