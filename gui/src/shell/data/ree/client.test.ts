import { asReeId } from "@core/ree/ReeId";
import { ApiRequestError } from "@shell/infra/api/ApiClient";
import { describe, expect, it, vi } from "vitest";
import type { ReeRuntimeValue } from "../apiRuntime";
import { createReeClient } from "./client";

function harness() {
  const reeApi = {
    putFileContent: vi.fn().mockResolvedValue({}),
    patchReeDefinition: vi.fn().mockResolvedValue({}),
    deleteFileContent: vi.fn().mockResolvedValue({}),
    getReeFileBytes: vi.fn().mockResolvedValue(new ArrayBuffer(2)),
    sealRee: vi.fn().mockResolvedValue({ ree_id: "ree-1" }),
    getReeArchive: vi.fn().mockResolvedValue({ bytes: new ArrayBuffer(1), fileName: "ree.zip" }),
    deleteRee: vi.fn().mockResolvedValue({}),
    removeSource: vi.fn().mockResolvedValue(undefined),
    acquireSource: vi.fn().mockResolvedValue({}),
    initUpload: vi.fn().mockResolvedValue({ upload_token: "token", upload_url: "/upload" }),
    uploadStagedBytes: vi.fn().mockResolvedValue(undefined),
    completeUpload: vi.fn().mockResolvedValue({}),
  };
  const runtime = {
    reeId: asReeId("ree-1"),
    reeApi,
    runsApi: {},
  } as unknown as ReeRuntimeValue;
  return { client: createReeClient(runtime), reeApi };
}

describe("createReeClient", () => {
  it("maps basic file, intent, seal and archive operations", async () => {
    const { client, reeApi } = harness();
    await client.updateFile("ree-1", "run.sh", "echo ok");
    await client.updateReeIntent("ree-1", {
      name: "Renamed",
      catalog: {},
      build_runtime: {},
      experiments: [],
      hardware: {},
    });
    await client.deleteFile("ree-1", "old.txt");
    await expect(client.getReeFileBytes("ree-1", "result.txt")).resolves.toBeInstanceOf(
      ArrayBuffer,
    );
    await client.sealRee("ree-1", {
      includeSource: true,
      includeRuntime: false,
      includeResults: true,
    });
    await expect(client.getReeArchive("ree-1")).resolves.toMatchObject({ fileName: "ree.zip" });

    expect(reeApi.putFileContent).toHaveBeenCalledWith("ree-1", {
      path: "run.sh",
      content: "echo ok",
    });
    expect(reeApi.patchReeDefinition).toHaveBeenCalledWith("ree-1", {
      definition_patch: expect.objectContaining({ name: "Renamed" }),
    });
  });

  it("treats an already absent workspace as successfully released", async () => {
    const { client, reeApi } = harness();
    reeApi.deleteRee.mockRejectedValueOnce(new ApiRequestError(404, "not_found", "Missing", false));
    await expect(client.releaseRee("ree-1")).resolves.toBeUndefined();
  });

  it("propagates release failures other than not found", async () => {
    const { client, reeApi } = harness();
    reeApi.deleteRee.mockRejectedValueOnce(
      new ApiRequestError(503, "unavailable", "Unavailable", true),
    );
    await expect(client.releaseRee("ree-1")).rejects.toMatchObject({ status: 503 });
  });

  it("resets a workspace by clearing or downloading source", async () => {
    const { client, reeApi } = harness();
    await client.resetWorkspaceRequest("ree-1", { mode: "clear" });
    await client.resetWorkspaceRequest("ree-1", {
      mode: "download",
      source: "https://example.test/repo.git",
      sourceType: "git",
      revision: "main",
    });
    expect(reeApi.removeSource).toHaveBeenCalledWith("ree-1");
    expect(reeApi.acquireSource).toHaveBeenCalledWith(
      "ree-1",
      expect.objectContaining({ origin_url: "https://example.test/repo.git" }),
    );
  });

  it("stages uploaded source bytes", async () => {
    const { client, reeApi } = harness();
    await client.resetWorkspaceRequest("ree-1", {
      mode: "upload",
      archiveName: "source.tgz",
      archiveContentBase64: "AQID",
    });
    expect(reeApi.uploadStagedBytes).toHaveBeenCalledWith("/upload", expect.any(ArrayBuffer));
    expect(reeApi.completeUpload).toHaveBeenCalledWith("ree-1", "token", "source.tgz");
  });

  it("rejects unsupported reset modes", async () => {
    const { client } = harness();
    await expect(client.resetWorkspaceRequest("ree-1", { mode: "other" } as never)).rejects.toThrow(
      "Unsupported workspace reset mode",
    );
  });
});
