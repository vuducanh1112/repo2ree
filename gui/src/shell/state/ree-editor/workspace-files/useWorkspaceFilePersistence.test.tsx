import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../../tests/support/renderApp";
import { useWorkspaceFilePersistence } from "./useWorkspaceFilePersistence";

describe("useWorkspaceFilePersistence", () => {
  it("renames, saves, refreshes, and reports success in order", async () => {
    const calls: string[] = [];
    const deleteFileContent = vi.fn(async () => {
      calls.push("delete");
      return {};
    });
    const putFileContent = vi.fn(async () => {
      calls.push("update");
      return {};
    });
    const refreshWorkspaceFiles = vi.fn(async () => {
      calls.push("refresh");
      return [];
    });
    const showToast = vi.fn(() => calls.push("toast"));
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { deleteFileContent, putFileContent } }),
    });
    const { result } = renderHook(
      () => useWorkspaceFilePersistence({ refreshWorkspaceFiles, showToast }),
      { wrapper: Wrapper },
    );

    await act(() => result.current.persistWorkspaceFile(" old.txt ", " new.txt ", "hello"));

    expect(calls).toEqual(["delete", "update", "refresh", "toast"]);
    expect(deleteFileContent).toHaveBeenCalledWith("ree-1", "old.txt");
    expect(putFileContent).toHaveBeenCalledWith("ree-1", {
      path: "new.txt",
      content: "hello",
    });
    expect(showToast).toHaveBeenCalledWith("Saved new.txt to workspace", "success");
  });

  it("turns persistence failures into an actionable error toast", async () => {
    const putFileContent = vi.fn().mockRejectedValue(new Error("disk full"));
    const showToast = vi.fn();
    const refreshWorkspaceFiles = vi.fn().mockResolvedValue([]);
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { putFileContent } }),
    });
    const { result } = renderHook(
      () => useWorkspaceFilePersistence({ refreshWorkspaceFiles, showToast }),
      { wrapper: Wrapper },
    );

    await act(() => result.current.persistWorkspaceFile(undefined, "script.sh", "exit 0"));

    expect(refreshWorkspaceFiles).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith("Failed to save script.sh: disk full", "error");
  });
});
