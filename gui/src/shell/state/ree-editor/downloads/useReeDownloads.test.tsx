import { asReeId } from "@core/ree/ReeId";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../../tests/support/renderApp";
import { useReeDownloads } from "./useReeDownloads";

describe("useReeDownloads", () => {
  afterEach(() => vi.restoreAllMocks());

  it("downloads workspace bytes and the REE archive with planned names", async () => {
    const getReeFileBytes = vi.fn().mockResolvedValue(new Uint8Array([1, 2]).buffer);
    const getReeArchive = vi.fn().mockResolvedValue({
      bytes: new Uint8Array([3]).buffer,
      fileName: "server-name.zip",
    });
    const downloadBlob = vi
      .spyOn(appShellPorts.browserDownloads, "downloadBlob")
      .mockImplementation(() => {});
    const showToast = vi.fn();
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { getReeFileBytes, getReeArchive } }),
    });
    const { result } = renderHook(
      () =>
        useReeDownloads({
          getReeName: () => "Example REE",
          showToast,
          reeId: asReeId("ree-1"),
        }),
      { wrapper: Wrapper },
    );

    await act(() => result.current.downloadWorkspaceFile("results/output.txt"));
    act(() => result.current.handleDownloadRee());
    await waitFor(() => expect(getReeArchive).toHaveBeenCalledOnce());

    expect(getReeFileBytes).toHaveBeenCalledWith("ree-1", "workspace/results/output.txt");
    expect(downloadBlob).toHaveBeenNthCalledWith(1, expect.any(ArrayBuffer), {
      fileName: "output.txt",
      mimeType: "application/octet-stream",
    });
    expect(downloadBlob).toHaveBeenNthCalledWith(2, expect.any(ArrayBuffer), {
      fileName: "server-name.zip",
      mimeType: "application/zip",
    });
    expect(showToast).toHaveBeenCalledWith("Downloaded output.txt", "success");
  });

  it("reports file and archive failures without triggering browser downloads", async () => {
    const getReeFileBytes = vi.fn().mockRejectedValue(new Error("missing"));
    const getReeArchive = vi.fn().mockRejectedValue(new Error("offline"));
    const downloadBlob = vi
      .spyOn(appShellPorts.browserDownloads, "downloadBlob")
      .mockImplementation(() => {});
    const showToast = vi.fn();
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { getReeFileBytes, getReeArchive } }),
    });
    const { result } = renderHook(
      () =>
        useReeDownloads({
          getReeName: () => "",
          showToast,
          reeId: asReeId("ree-1"),
        }),
      { wrapper: Wrapper },
    );
    await act(() => result.current.downloadWorkspaceFile("missing.txt"));
    act(() => result.current.handleDownloadRee());
    await waitFor(() =>
      expect(showToast).toHaveBeenCalledWith("Backend archive download failed: offline", "error"),
    );
    expect(showToast).toHaveBeenCalledWith("Failed to download missing.txt: missing", "error");
    expect(downloadBlob).not.toHaveBeenCalled();
  });
});
