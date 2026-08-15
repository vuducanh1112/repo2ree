import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useReeIntentSync } from "./useReeIntentSync";

const mocks = vi.hoisted(() => ({
  fetchWorkspace: vi.fn(),
  updateReeIntent: vi.fn(),
}));

vi.mock("@shell/data/ree/queries", () => ({
  useRefreshReeQuery: () => mocks.fetchWorkspace,
}));
vi.mock("@shell/data/ree/mutations", () => ({
  useUpdateReeIntentMutation: () => ({ mutateAsync: mocks.updateReeIntent }),
}));

describe("useReeIntentSync", () => {
  beforeEach(() => {
    mocks.fetchWorkspace.mockReset().mockResolvedValue({ files: [], reeFiles: [] });
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
      ree: undefined,
    });

    rerender({ ree: { ...initial, name: "Edited now" }, provisioned: true });
    await act(() => result.current.flush());

    expect(mocks.updateReeIntent).toHaveBeenCalledOnce();
    expect(mocks.updateReeIntent).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Edited now" }),
    );
    expect(mocks.fetchWorkspace).toHaveBeenCalledTimes(2);
  });

  it("surfaces flush failures to callers", async () => {
    mocks.updateReeIntent.mockRejectedValueOnce(new Error("offline"));
    const initial = createEmptyReeEditorViewModel();
    const { result, rerender } = renderHook(
      ({ ree }) =>
        useReeIntentSync({
          ree,
          reeId: "ree-1",
          provisioned: true,
          hydrateWorkspace: vi.fn(),
        }),
      { initialProps: { ree: initial } },
    );
    await waitFor(() => expect(mocks.fetchWorkspace).toHaveBeenCalledOnce());
    rerender({ ree: { ...initial, name: "Unsaved" } });

    await expect(act(() => result.current.flush())).rejects.toThrow("offline");
  });
});
