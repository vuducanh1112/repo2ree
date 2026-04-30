import { describe, expect, it, vi } from "vitest";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { createSourceUseCase } from "./acquireSource";

function buildRee(): ReeDraftViewModel {
  return {
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
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

const workspaceFiles: FileTreeNode[] = [{ id: "readme", name: "README.md", type: "file" }];

function executedCommands(executeCommands: ReturnType<typeof vi.fn>) {
  return executeCommands.mock.calls.flatMap(([commands]) => commands);
}

describe("createSourceUseCase", () => {
  it("downloads source and applies the planned source outcome", async () => {
    const executeCommands = vi.fn();
    const sourceChanged = vi.fn();
    const runSourceAction = vi.fn(async () => ({ status: "succeeded" as const }));

    const useCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands,
      sourceChanged,
      runSourceAction,
      refreshWorkspaceFiles: vi.fn(async () => workspaceFiles),
      clearWorkspace: vi.fn(),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.downloadSource("git", " https://example.org/repo.git ");

    expect(sourceChanged).toHaveBeenCalledWith({ silent: true });
    expect(runSourceAction).toHaveBeenCalledWith(
      {
        mode: "download",
        source: "https://example.org/repo.git",
        sourceType: "git",
      },
      {
        mode: "download",
        source: "https://example.org/repo.git",
        sourceType: "git",
      },
    );
    expect(executedCommands(executeCommands)).toContainEqual({ type: "setSourceLoading" });
    expect(executedCommands(executeCommands)).toContainEqual({
      type: "toast",
      message: "Source files downloaded into workspace",
      toastType: "success",
    });
  });

  it("reports download validation errors without starting the source workflow", async () => {
    const executeCommands = vi.fn();
    const sourceChanged = vi.fn();
    const runSourceAction = vi.fn();

    const useCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands,
      sourceChanged,
      runSourceAction,
      refreshWorkspaceFiles: vi.fn(),
      clearWorkspace: vi.fn(),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.downloadSource("", "");

    expect(sourceChanged).not.toHaveBeenCalled();
    expect(runSourceAction).not.toHaveBeenCalled();
    expect(executedCommands(executeCommands)).toEqual([
      { type: "toast", message: "Set origin URL and origin type first", toastType: "error" },
    ]);
  });

  it("plans upload failure commands for terminal workflow failures", async () => {
    const executeCommands = vi.fn();

    const useCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands,
      sourceChanged: vi.fn(),
      runSourceAction: vi.fn(async () => ({ status: "failed" as const })),
      refreshWorkspaceFiles: vi.fn(),
      clearWorkspace: vi.fn(),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.uploadSource({ archiveName: "source.tar.gz", archiveContentBase64: "abc" });

    expect(executedCommands(executeCommands)).toContainEqual({
      type: "toast",
      message: "Source failed",
      toastType: "error",
    });
    expect(executedCommands(executeCommands)).not.toContainEqual({
      type: "toast",
      message: "Archive extracted into workspace",
      toastType: "success",
    });
  });

  it("reports upload validation errors without resetting workflow state", async () => {
    const executeCommands = vi.fn();
    const sourceChanged = vi.fn();
    const runSourceAction = vi.fn();

    const useCase = createSourceUseCase({
      ree: { ...buildRee(), _sourceAvailable: true, _sourceAcquiredBy: "download" },
      executeCommands,
      sourceChanged,
      runSourceAction,
      refreshWorkspaceFiles: vi.fn(),
      clearWorkspace: vi.fn(),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.uploadSource({ archiveName: "source.tar.gz", archiveContentBase64: "abc" });

    expect(sourceChanged).not.toHaveBeenCalled();
    expect(runSourceAction).not.toHaveBeenCalled();
    expect(executedCommands(executeCommands)).toContainEqual({
      type: "toast",
      message: "Source already provided via origin download. Change source to switch method.",
      toastType: "error",
    });
  });

  it("clears workspace source and applies clear state", async () => {
    const executeCommands = vi.fn();
    const clearWorkspace = vi.fn(async () => {});
    const refreshWorkspaceFiles = vi.fn(async () => workspaceFiles);

    const useCase = createSourceUseCase({
      ree: { ...buildRee(), origin_url: "https://example.org/repo.git" },
      executeCommands,
      sourceChanged: vi.fn(),
      runSourceAction: vi.fn(),
      refreshWorkspaceFiles,
      clearWorkspace,
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.removeSource();

    expect(clearWorkspace).toHaveBeenCalled();
    expect(refreshWorkspaceFiles).toHaveBeenCalled();
    expect(executedCommands(executeCommands)).toContainEqual({
      type: "toast",
      message: "Source files removed from workspace — choose download or upload again",
      toastType: "info",
    });
  });
});
