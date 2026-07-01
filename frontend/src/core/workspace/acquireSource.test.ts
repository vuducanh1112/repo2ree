import { describe, expect, it, vi } from "vitest";
import type { FileTreeNode } from "../../core/workspace/FileTree";
import { createSourceUseCase } from "./acquireSource";
import type { WorkspaceSourceState } from "./WorkspaceSourceState";

function buildRee(): WorkspaceSourceState {
  return {};
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

  it("passes a trimmed git revision through to the source execution run", async () => {
    const executeCommands = vi.fn();
    const runSourceAction = vi.fn(async () => ({ status: "succeeded" as const }));

    const useCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands,
      sourceChanged: vi.fn(),
      runSourceAction,
      refreshWorkspaceFiles: vi.fn(async () => workspaceFiles),
      clearWorkspace: vi.fn(),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.downloadSource("git", "https://example.org/repo.git", "  v1.2.3  ");

    const request = {
      mode: "download",
      source: "https://example.org/repo.git",
      sourceType: "git",
      revision: "v1.2.3",
    };
    expect(runSourceAction).toHaveBeenCalledWith(request, request);
  });

  it("omits the revision for non-git sources", async () => {
    const runSourceAction = vi.fn(async (_request: unknown, _reset: unknown) => ({
      status: "succeeded" as const,
    }));

    const useCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands: vi.fn(),
      sourceChanged: vi.fn(),
      runSourceAction,
      refreshWorkspaceFiles: vi.fn(async () => workspaceFiles),
      clearWorkspace: vi.fn(),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await useCase.downloadSource("tarball", "https://example.org/s.tgz", "v1.2.3");

    const [resetRequest] = runSourceAction.mock.calls[0];
    expect(resetRequest).not.toHaveProperty("revision");
  });

  it("reports download validation errors without starting the source execution run", async () => {
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

  it("plans upload failure commands for terminal execution run failures", async () => {
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

  it("reports upload validation errors without resetting assembly state", async () => {
    const executeCommands = vi.fn();
    const sourceChanged = vi.fn();
    const runSourceAction = vi.fn();

    const useCase = createSourceUseCase({
      ree: { ...buildRee(), sourceAvailable: true, sourceAcquiredBy: "download" },
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
      ree: buildRee(),
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

  it("returns whether the source clear actually succeeded", async () => {
    const successUseCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands: vi.fn(),
      sourceChanged: vi.fn(),
      runSourceAction: vi.fn(),
      refreshWorkspaceFiles: vi.fn(async () => workspaceFiles),
      clearWorkspace: vi.fn(async () => {}),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    const failedUseCase = createSourceUseCase({
      ree: buildRee(),
      executeCommands: vi.fn(),
      sourceChanged: vi.fn(),
      runSourceAction: vi.fn(),
      refreshWorkspaceFiles: vi.fn(),
      clearWorkspace: vi.fn(async () => {
        throw new Error("boom");
      }),
      nowIso: () => "2026-01-01T00:00:00Z",
    });

    await expect(successUseCase.removeSource()).resolves.toBe(true);
    await expect(failedUseCase.removeSource()).resolves.toBe(false);
  });
});
