import { asReeId } from "@core/ree/ReeId";
import type { RunSummary } from "@shell/infra/api/apiTypes";
import { describe, expect, it, vi } from "vitest";
import type { ReeRuntimeValue } from "../apiRuntime";
import { createReeRunsClient, nextRunLogCursor } from "./client";

function wireRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    ree_id: "ree-1",
    operation: "build",
    status: "succeeded",
    created_at: "2026-01-01T00:00:00Z",
    started_at: null,
    finished_at: null,
    failure: null,
    outputs: {},
    ...overrides,
  };
}

function harness() {
  const reeApi = {
    createRee: vi.fn().mockResolvedValue(wireRun()),
    acquireSource: vi.fn().mockResolvedValue(wireRun()),
    initUpload: vi.fn().mockResolvedValue({ upload_token: "token", upload_url: "/upload" }),
    uploadStagedBytes: vi.fn().mockResolvedValue(undefined),
    completeUpload: vi.fn().mockResolvedValue(wireRun()),
    initBundleUpload: vi.fn().mockResolvedValue({
      upload_token: "bundle-token",
      upload_url: "/bundle-upload",
    }),
    loadReeBundle: vi.fn().mockResolvedValue(wireRun()),
  };
  const runsApi = {
    createBuildRuntimeRun: vi.fn().mockResolvedValue(wireRun()),
    createGenerateHbomRun: vi.fn().mockResolvedValue(wireRun()),
    createGenerateSbomRun: vi.fn().mockResolvedValue(wireRun()),
    createCrossCheckSbomRun: vi.fn().mockResolvedValue(wireRun()),
    createActivationTestRun: vi.fn().mockResolvedValue(wireRun()),
    createEvaluateRun: vi.fn().mockResolvedValue(wireRun()),
    createExperimentRun: vi.fn().mockResolvedValue(wireRun()),
    listRuns: vi.fn().mockResolvedValue({ runs: [wireRun()], next_cursor: null }),
    getRun: vi.fn().mockResolvedValue(wireRun()),
    listRunLogs: vi.fn().mockResolvedValue({
      entries: [
        {
          seq: 2,
          ts: "2026-01-01T00:00:01Z",
          level: "info",
          stream: "stdout",
          message: "hello",
        },
      ],
      next_cursor: null,
      has_more: false,
    }),
    cancelRun: vi.fn().mockResolvedValue({ status: "canceled" }),
  };
  const runtime = {
    reeId: asReeId("ree-1"),
    reeApi,
    runsApi,
  } as unknown as ReeRuntimeValue;
  return { client: createReeRunsClient(runtime), reeApi, runsApi };
}

describe("nextRunLogCursor", () => {
  it("uses the backend cursor when another page is available", () => {
    expect(nextRunLogCursor("20", [{ seq: 19 }], "10")).toBe("20");
  });

  it("advances to the last seen log sequence at the current end of the feed", () => {
    expect(nextRunLogCursor(undefined, [{ seq: 1 }, { seq: 2 }], undefined)).toBe("2");
  });

  it("keeps the current cursor when polling returns no new lines", () => {
    expect(nextRunLogCursor(undefined, [], "2")).toBe("2");
  });
});

describe("createReeRunsClient", () => {
  it("provisions a named workspace and trims optional placement inputs", async () => {
    const { client, reeApi } = harness();
    await expect(
      client.createWorkspace("Demo", " image:latest ", " agent-1 "),
    ).resolves.toMatchObject({
      reeId: "ree-1",
      run: { runId: "run-1", status: "succeeded" },
    });
    expect(reeApi.createRee).toHaveBeenCalledWith({
      name: "Demo",
      workbench_image: "image:latest",
      agent_id: "agent-1",
    });
  });

  it("maps every named execution operation", async () => {
    const { client, runsApi } = harness();
    await client.startReeRun("ree-1", "build", { idempotencyKey: "b-1" });
    await client.startReeRun("ree-1", "hbom", { idempotencyKey: "h-1" });
    await client.startReeRun("ree-1", "sbom");
    await client.startReeRun("ree-1", "crosscheck");
    await client.startReeRun("ree-1", "activation");
    await client.startReeRun("ree-1", "evaluate", { strict: true });

    expect(runsApi.createBuildRuntimeRun).toHaveBeenCalledWith("ree-1", {
      idempotency_key: "b-1",
    });
    expect(runsApi.createGenerateHbomRun).toHaveBeenCalledWith("ree-1", {
      idempotency_key: "h-1",
    });
    expect(runsApi.createGenerateSbomRun).toHaveBeenCalled();
    expect(runsApi.createCrossCheckSbomRun).toHaveBeenCalled();
    expect(runsApi.createActivationTestRun).toHaveBeenCalled();
    expect(runsApi.createEvaluateRun).toHaveBeenCalledWith("ree-1", { strict: true });
  });

  it("maps source download and upload operations", async () => {
    const { client, reeApi } = harness();
    await client.startReeRun("ree-1", "source", {
      mode: "download",
      source: "https://example.test/repo.git",
      sourceType: "git",
      revision: "main",
    });
    await client.startReeRun("ree-1", "source", {
      mode: "upload",
      archiveName: "source.tgz",
      archiveContentBase64: "AQID",
    });
    expect(reeApi.acquireSource).toHaveBeenCalledWith(
      "ree-1",
      expect.objectContaining({ origin_url: "https://example.test/repo.git", revision: "main" }),
    );
    expect(reeApi.uploadStagedBytes).toHaveBeenCalledWith("/upload", expect.any(ArrayBuffer));
    expect(reeApi.completeUpload).toHaveBeenCalledWith("ree-1", "token", "source.tgz");
  });

  it("rejects unsupported operations", async () => {
    const { client } = harness();
    await expect(client.startReeRun("ree-1", "unknown")).rejects.toThrow(
      "Unsupported execution run operation",
    );
    await expect(client.startReeRun("ree-1", "source", { mode: "other" })).rejects.toThrow(
      "Unsupported source acquisition mode",
    );
  });

  it("uploads and loads a downloaded bundle", async () => {
    const { client, reeApi } = harness();
    const bundle = new File([new Uint8Array([1, 2])], "demo.zip", { type: "application/zip" });
    await client.loadReeBundle("ree-1", bundle);
    expect(reeApi.initBundleUpload).toHaveBeenCalledWith("ree-1", {
      file_name: "demo.zip",
      size: 2,
      content_type: "application/zip",
    });
    expect(reeApi.loadReeBundle).toHaveBeenCalledWith("ree-1", "bundle-token", "demo.zip");
  });

  it("maps experiment, history, logs, failure and cancellation", async () => {
    const { client, runsApi } = harness();
    runsApi.getRun.mockResolvedValueOnce(
      wireRun({
        status: "failed",
        failure: {
          category: "execution",
          message: "boom",
          retryable: false,
          origin: "executor",
          details: { exit_code: 1 },
        },
      }),
    );
    await expect(client.startExperimentRun("ree-1", "hello")).resolves.toMatchObject({
      reeId: "ree-1",
      run: { runId: "run-1" },
    });
    await expect(client.listReeRuns("ree-1")).resolves.toEqual([
      expect.objectContaining({ operation: "build" }),
    ]);
    await expect(client.getReeRun("ree-1", "run-1")).resolves.toMatchObject({
      status: "failed",
      failure: { message: "boom", details: { exit_code: 1 } },
    });
    await expect(client.getReeRunLogs("ree-1", "run-1", "1")).resolves.toEqual({
      lines: [expect.objectContaining({ type: "out", msg: "hello" })],
      nextCursor: "2",
      hasMore: false,
    });
    await expect(client.cancelReeRun("ree-1", "run-1")).resolves.toBe("canceled");
  });
});
