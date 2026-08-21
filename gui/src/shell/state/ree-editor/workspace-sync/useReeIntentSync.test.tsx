import { emptyEvaluationState } from "@core/evaluate/EvaluationState";
import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useReeIntentSync } from "./useReeIntentSync";

const mocks = vi.hoisted(() => ({
  fetchWorkspace: vi.fn(),
  updateReeIntent: vi.fn(),
}));

const remoteRee = {
  reeSpec: createEmptyReeSpec(),
  workspaceSourceState: { sourceAvailable: false },
  artifactStatus: { runtimeIncluded: false },
  evaluationState: emptyEvaluationState(),
};

const workspaceFixture = { files: [], reeFiles: [], ree: remoteRee };

vi.mock("@shell/data/ree/queries", () => ({
  useRefreshReeQuery: () => mocks.fetchWorkspace,
}));
vi.mock("@shell/data/ree/mutations", () => ({
  useUpdateReeIntentMutation: () => ({ mutateAsync: mocks.updateReeIntent }),
}));

describe("useReeIntentSync", () => {
  beforeEach(() => {
    mocks.fetchWorkspace.mockReset().mockResolvedValue(workspaceFixture);
    mocks.updateReeIntent.mockReset().mockResolvedValue(undefined);
  });

  it("does no remote work before a workspace is provisioned", async () => {
    const hydrateWorkspace = vi.fn();
    const ree = createEmptyReeEditorViewModel();
    const { result } = renderHook(() =>
      useReeIntentSync({ ree, reeId: "ree-1", provisioned: false, hydrateWorkspace }),
    );

    await act(() => result.current.flush());
    expect(mocks.fetchWorkspace).not.toHaveBeenCalled();
    expect(mocks.updateReeIntent).not.toHaveBeenCalled();
    expect(hydrateWorkspace).not.toHaveBeenCalled();
  });

  it("hydrates on provision and flushes the latest edit without waiting for debounce", async () => {
    const hydrateWorkspace = vi.fn();
    const initial = createEmptyReeEditorViewModel();
    const { result, rerender } = renderHook(
      ({ ree, provisioned }) =>
        useReeIntentSync({ ree, reeId: "ree-1", provisioned, hydrateWorkspace }),
      { initialProps: { ree: initial, provisioned: false } },
    );

    rerender({ ree: initial, provisioned: true });
    await waitFor(() => expect(hydrateWorkspace).toHaveBeenCalledOnce());
    expect(hydrateWorkspace).toHaveBeenCalledWith({
      workspaceFiles: [],
      reeArtifactFiles: [],
      ree: remoteRee,
    });

    rerender({
      ree: patchReeEditorViewModel(initial, { spec: { name: "Edited now" } }),
      provisioned: true,
    });
    await waitFor(() => expect(result.current.syncState.phase).toBe("dirty"));
    await act(() => result.current.flush());

    expect(mocks.updateReeIntent).toHaveBeenCalledOnce();
    expect(mocks.updateReeIntent).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Edited now" }),
    );
    expect(mocks.fetchWorkspace).toHaveBeenCalledTimes(2);
    expect(result.current.syncState.phase).toBe("clean");
  });

  it("surfaces flush failures to callers", async () => {
    mocks.updateReeIntent.mockRejectedValueOnce(new Error("offline"));
    const initial = createEmptyReeEditorViewModel();
    const hydrateWorkspace = vi.fn();
    const { result, rerender } = renderHook(
      ({ ree }) =>
        useReeIntentSync({
          ree,
          reeId: "ree-1",
          provisioned: true,
          hydrateWorkspace,
        }),
      { initialProps: { ree: initial } },
    );
    await waitFor(() => expect(result.current.hydration.status).toBe("ready"));
    rerender({ ree: patchReeEditorViewModel(initial, { spec: { name: "Unsaved" } }) });

    await act(async () => {
      await expect(result.current.flush()).rejects.toThrow("offline");
    });
    await waitFor(() =>
      expect(result.current.syncState).toEqual({
        phase: "error",
        error: expect.objectContaining({ message: "offline" }),
      }),
    );

    await act(() => result.current.retrySync());
    expect(result.current.syncState.phase).toBe("clean");
  });

  it("reports initial hydration failure without sending the default draft", async () => {
    mocks.fetchWorkspace.mockRejectedValueOnce(new Error("offline"));
    const hydrateWorkspace = vi.fn();
    const initial = createEmptyReeEditorViewModel();
    const { result, rerender } = renderHook(
      ({ ree }) =>
        useReeIntentSync({
          ree,
          reeId: "ree-1",
          provisioned: true,
          hydrateWorkspace,
        }),
      { initialProps: { ree: initial } },
    );

    await waitFor(() => expect(result.current.hydration.status).toBe("error"));
    expect(result.current.hydration).toEqual({
      status: "error",
      error: expect.objectContaining({ message: "offline" }),
    });

    rerender({
      ree: patchReeEditorViewModel(initial, { spec: { name: "Must not be sent" } }),
    });
    await new Promise((resolve) => setTimeout(resolve, 350));

    expect(hydrateWorkspace).not.toHaveBeenCalled();
    expect(mocks.updateReeIntent).not.toHaveBeenCalled();
  });

  it("treats a response without a REE definition as a hydration failure", async () => {
    mocks.fetchWorkspace.mockResolvedValueOnce({ files: [], reeFiles: [] });
    const hydrateWorkspace = vi.fn();
    const { result } = renderHook(() =>
      useReeIntentSync({
        ree: createEmptyReeEditorViewModel(),
        reeId: "ree-1",
        provisioned: true,
        hydrateWorkspace,
      }),
    );

    await waitFor(() => expect(result.current.hydration.status).toBe("error"));
    expect(result.current.hydration).toEqual({
      status: "error",
      error: expect.objectContaining({
        message: "The workspace response did not contain its REE definition",
      }),
    });
    expect(hydrateWorkspace).not.toHaveBeenCalled();
    expect(mocks.updateReeIntent).not.toHaveBeenCalled();
  });

  it("retries failed hydration and opens only after applying the remote REE", async () => {
    mocks.fetchWorkspace
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(workspaceFixture);
    const hydrateWorkspace = vi.fn();
    const { result } = renderHook(() =>
      useReeIntentSync({
        ree: createEmptyReeEditorViewModel(),
        reeId: "ree-1",
        provisioned: true,
        hydrateWorkspace,
      }),
    );

    await waitFor(() => expect(result.current.hydration.status).toBe("error"));
    act(() => result.current.retryHydration());
    await waitFor(() => expect(result.current.hydration.status).toBe("ready"));

    expect(hydrateWorkspace).toHaveBeenCalledOnce();
    expect(hydrateWorkspace).toHaveBeenCalledWith({
      workspaceFiles: [],
      reeArtifactFiles: [],
      ree: remoteRee,
    });
    expect(mocks.updateReeIntent).not.toHaveBeenCalled();
  });
});
