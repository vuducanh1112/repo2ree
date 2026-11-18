import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../../tests/support/renderApp";
import { useWorkspaceFilePersistence } from "./useWorkspaceFilePersistence";

describe("useWorkspaceFilePersistence", () => {
  it("saves, refreshes, and reports success in order", async () => {
    const calls: string[] = [];
    const writeScript = vi.fn(async () => {
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
      services: fakeApiServices({ ree: { writeScript } }),
    });
    const { result } = renderHook(
      () => useWorkspaceFilePersistence({ refreshWorkspaceFiles, showToast }),
      { wrapper: Wrapper },
    );

    await act(() => result.current.persistWorkspaceFile(" new.txt ", "hello"));

    expect(calls).toEqual(["update", "refresh", "toast"]);
    expect(writeScript).toHaveBeenCalledWith("ree-1", {
      path: "new.txt",
      content: "hello",
    });
    expect(showToast).toHaveBeenCalledWith("Saved new.txt to workspace", "success");
  });

  it("turns persistence failures into an actionable error toast", async () => {
    const writeScript = vi.fn().mockRejectedValue(new Error("disk full"));
    const showToast = vi.fn();
    const refreshWorkspaceFiles = vi.fn().mockResolvedValue([]);
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { writeScript } }),
    });
    const { result } = renderHook(
      () => useWorkspaceFilePersistence({ refreshWorkspaceFiles, showToast }),
      { wrapper: Wrapper },
    );

    await act(() => result.current.persistWorkspaceFile("script.sh", "exit 0"));

    expect(refreshWorkspaceFiles).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith("Failed to save script.sh: disk full", "error");
  });
});
