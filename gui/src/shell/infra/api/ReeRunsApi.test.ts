import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "./ApiClient";
import { mapRunLogsToLines, ReeRunsApi } from "./ReeRunsApi";

function harness() {
  const request = vi.fn().mockResolvedValue({});
  return {
    request,
    api: new ReeRunsApi({ request } as unknown as ApiClient),
  };
}

describe("ReeRunsApi", () => {
  it("maps each run operation onto its endpoint and payload", async () => {
    const { api, request } = harness();
    await api.createBuildRuntimeRun("ree/1", { idempotency_key: "build-1" });
    await api.createGenerateHbomRun("ree/1", {});
    await api.createGenerateSbomRun("ree/1", {});
    await api.createCrossCheckSbomRun("ree/1", {});
    await api.createActivationTestRun("ree/1", {});
    await api.createEvaluateRun("ree/1", { strict: true });
    await api.createExperimentRun("ree/1", "hello world", {});

    expect(request.mock.calls.map(([path, init]) => [path, init.method, init.body])).toEqual([
      ["/api/v1/rees/ree%2F1/build-runtime", "POST", '{"idempotency_key":"build-1"}'],
      ["/api/v1/rees/ree%2F1/generate-hbom", "POST", "{}"],
      ["/api/v1/rees/ree%2F1/generate-sbom", "POST", "{}"],
      ["/api/v1/rees/ree%2F1/cross-check-sbom", "POST", "{}"],
      ["/api/v1/rees/ree%2F1/activation-test", "POST", "{}"],
      ["/api/v1/rees/ree%2F1/evaluate", "POST", '{"strict":true}'],
      ["/api/v1/rees/ree%2F1/experiments/hello%20world:run", "POST", "{}"],
    ]);
  });

  it("addresses list, detail, cancel and paged log operations", async () => {
    const { api, request } = harness();
    await api.listRuns("ree-1");
    await api.getRun("ree-1", "run/1");
    await api.cancelRun("ree-1", "run/1");
    await api.listRunLogs("ree-1", "run/1", {
      cursor: "12",
      limit: 50,
      sinceTs: "2026-01-01T00:00:00Z",
    });

    expect(request.mock.calls[0]?.slice(0, 2)).toEqual([
      "/api/v1/rees/ree-1/runs",
      { method: "GET" },
    ]);
    expect(request.mock.calls[1]?.[0]).toBe("/api/v1/rees/ree-1/runs/run%2F1");
    expect(request.mock.calls[2]?.[0]).toBe("/api/v1/rees/ree-1/runs/run%2F1:cancel");
    expect(request.mock.calls[3]?.[2].toString()).toBe(
      "cursor=12&limit=50&sinceTs=2026-01-01T00%3A00%3A00Z",
    );
  });
});

describe("mapRunLogsToLines", () => {
  it("maps severity and stream combinations to presentation lines", () => {
    const common = { seq: 1, ts: "2026-01-01T00:00:00Z" };
    expect(
      mapRunLogsToLines([
        { ...common, level: "error", stream: "stderr", message: "failed" },
        { ...common, level: "warn", stream: "system", message: "careful" },
        { ...common, level: "info", stream: "stdout", message: "output" },
        { ...common, level: "debug", stream: "system", message: "detail" },
        { ...common, level: "info", stream: "system", message: "done" },
      ]),
    ).toEqual([
      { type: "err", msg: "failed", ts: common.ts, stream: "stderr" },
      { type: "warn", msg: "careful", ts: common.ts, stream: "system" },
      { type: "out", msg: "output", ts: common.ts, stream: "stdout" },
      { type: "info", msg: "detail", ts: common.ts, stream: "system" },
      { type: "ok", msg: "done", ts: common.ts, stream: "system" },
    ]);
  });
});
