import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { createEmptyReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { queryKeys } from "../../../data/queryKeys";
import { createSourceActions } from "./sourceActions";

function buildArgs(queryClient: QueryClient) {
  return {
    ree: createEmptyReeEditorViewModel(),
    reeClient: {
      getRee: vi.fn(),
      updateFile: vi.fn(),
      updateReeDraft: vi.fn(),
      deleteFile: vi.fn(),
      getFileBytes: vi.fn(),
      getReeArchive: vi.fn(),
      resetWorkspaceRequest: vi.fn(async () => {}),
    },
    executionRunsClient: {
      startExecutionRun: vi.fn(),
      getExecutionRun: vi.fn(),
      getExecutionRunLogs: vi.fn(),
      cancelExecutionRun: vi.fn(),
    },
    reeId: "ree-1",
    queryClient,
    dispatch: vi.fn(),
    refreshWorkspaceFiles: vi.fn(async () => []),
    showToast: vi.fn(),
    clock: {
      nowIso: () => "2026-01-01T00:00:00Z",
      nowMillis: () => Date.parse("2026-01-01T00:00:00Z"),
    },
    sleep: vi.fn(async () => {}),
  };
}

describe("createSourceActions", () => {
  it("clears the cached evaluate report after a successful source removal", async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(queryKeys.evaluateReport("ree-1"), {
      dependencyLevel: 2,
    });
    const args = buildArgs(queryClient);

    const actions = createSourceActions(args);
    await actions.handleRemoveWorkspaceSource();

    expect(args.reeClient.resetWorkspaceRequest).toHaveBeenCalledWith("ree-1", {
      mode: "clear",
    });
    expect(queryClient.getQueryData(queryKeys.evaluateReport("ree-1"))).toBeNull();
  });

  it("preserves the cached evaluate report when source removal fails", async () => {
    const queryClient = new QueryClient();
    const cachedReport = { dependencyLevel: 2 };
    queryClient.setQueryData(queryKeys.evaluateReport("ree-1"), cachedReport);
    const args = buildArgs(queryClient);
    args.reeClient.resetWorkspaceRequest = vi.fn(async () => {
      throw new Error("clear failed");
    });

    const actions = createSourceActions(args);
    await actions.handleRemoveWorkspaceSource();

    expect(queryClient.getQueryData(queryKeys.evaluateReport("ree-1"))).toEqual(cachedReport);
  });
});
