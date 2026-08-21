/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../tests/support/renderApp";
import { createTestQueryClient } from "../../../../tests/support/testQueryClient";
import type { ReeRunsClient } from "./client";
import { observeReeRun, useReeRunLogsQuery, useReeRunQuery, useReeRunsQuery } from "./queries";

const wireRun = (status: "running" | "succeeded" = "succeeded") => ({
  run_id: "run-1",
  ree_id: "ree-1",
  operation: "build" as const,
  status,
  created_at: "2026-01-01T00:00:00Z",
  started_at: "2026-01-01T00:00:01Z",
  finished_at: status === "succeeded" ? "2026-01-01T00:00:02Z" : null,
  outputs: {},
  failure: null,
});

describe("run queries", () => {
  it("loads run lists, detail and logs through the scoped data client", async () => {
    const listRuns = vi.fn().mockResolvedValue({ runs: [wireRun()], next_cursor: null });
    const getRun = vi.fn().mockResolvedValue(wireRun());
    const listRunLogs = vi.fn().mockResolvedValue({
      entries: [
        {
          seq: 1,
          ts: "2026-01-01T00:00:01Z",
          level: "info",
          stream: "stdout",
          message: "built",
        },
      ],
      next_cursor: null,
      has_more: false,
    });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ runs: { listRuns, getRun, listRunLogs } }),
    });
    const { result } = renderHook(
      () => ({
        runs: useReeRunsQuery(),
        run: useReeRunQuery(undefined, "run-1"),
        logs: useReeRunLogsQuery(undefined, "run-1"),
      }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.logs.isSuccess).toBe(true));
    expect(result.current.runs.data).toEqual([expect.objectContaining({ runId: "run-1" })]);
    expect(result.current.run.data).toMatchObject({ status: "succeeded" });
    expect(result.current.logs.data?.lines).toEqual([
      expect.objectContaining({ type: "out", msg: "built" }),
    ]);
  });

  it("keeps optional detail and log queries disabled without a run id", () => {
    const { Wrapper } = createShellWrapper({ reeId: "ree-1" });
    const { result } = renderHook(
      () => ({
        run: useReeRunQuery(undefined, undefined),
        logs: useReeRunLogsQuery(undefined, undefined),
      }),
      { wrapper: Wrapper },
    );
    expect(result.current.run.fetchStatus).toBe("idle");
    expect(result.current.logs.fetchStatus).toBe("idle");
  });

  it("resumes log polling from the cursor stored in the query cache", async () => {
    const listRunLogs = vi
      .fn()
      .mockResolvedValueOnce({
        entries: [
          {
            seq: 1,
            ts: "2026-01-01T00:00:01Z",
            level: "info",
            stream: "stdout",
            message: "first",
          },
        ],
        next_cursor: null,
        has_more: false,
      })
      .mockResolvedValueOnce({
        entries: [
          {
            seq: 2,
            ts: "2026-01-01T00:00:02Z",
            level: "info",
            stream: "stdout",
            message: "second",
          },
        ],
        next_cursor: null,
        has_more: false,
      });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ runs: { listRunLogs } }),
    });
    const { result } = renderHook(() => useReeRunLogsQuery(undefined, "run-1"), {
      wrapper: Wrapper,
    });

    // Read `data` before refetch so TanStack Query tracks that property for
    // observer notifications (tracking only `isSuccess` would not rerender,
    // because it stays true across a successful refetch).
    await waitFor(() =>
      expect(result.current.data?.lines.map((line) => line.msg)).toEqual(["first"]),
    );
    const refetched = await act(() => result.current.refetch());

    expect(listRunLogs).toHaveBeenNthCalledWith(1, "ree-1", "run-1", {
      cursor: undefined,
      limit: 200,
    });
    expect(listRunLogs).toHaveBeenNthCalledWith(2, "ree-1", "run-1", {
      cursor: "1",
      limit: 200,
    });
    expect(refetched.data?.lines.map((line) => line.msg)).toEqual(["first", "second"]);
    await waitFor(() =>
      expect(result.current.data?.lines.map((line) => line.msg)).toEqual(["first", "second"]),
    );
  });
});

describe("observeReeRun", () => {
  it("polls until terminal, publishes updates, and follows paged logs", async () => {
    const client = {
      getReeRun: vi
        .fn()
        .mockResolvedValueOnce({ ...wireRun("running"), runId: "run-1", reeId: "ree-1" })
        .mockResolvedValueOnce({ ...wireRun(), runId: "run-1", reeId: "ree-1" }),
      getReeRunLogs: vi
        .fn()
        .mockResolvedValueOnce({
          lines: [{ type: "out", msg: "page one" }],
          nextCursor: "2",
          hasMore: true,
        })
        .mockResolvedValueOnce({ lines: [{ type: "ok", msg: "page two" }], hasMore: false })
        .mockResolvedValueOnce({ lines: [{ type: "ok", msg: "done" }], hasMore: false }),
    } as unknown as ReeRunsClient;
    const onUpdate = vi.fn();
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await observeReeRun(createTestQueryClient(), client, {
      reeId: "ree-1",
      runId: "run-1",
      onUpdate,
      sleep,
    });

    expect(result.status).toBe("succeeded");
    expect(onUpdate).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(1500);
    expect(client.getReeRunLogs).toHaveBeenNthCalledWith(2, "ree-1", "run-1", "2");
  });

  it("caps and sanitizes log output when the polling window expires", async () => {
    const lines = Array.from({ length: 2001 }, (_, index) => ({
      type: "out" as const,
      msg: index === 2000 ? "x".repeat(4100) : `line ${index}`,
    }));
    const client = {
      getReeRun: vi.fn().mockResolvedValue({
        ...wireRun("running"),
        runId: "run-1",
        reeId: "ree-1",
        finishedAt: undefined,
        startedAt: undefined,
      }),
      getReeRunLogs: vi.fn().mockResolvedValue({ lines, hasMore: false }),
    } as unknown as ReeRunsClient;
    const now = vi.spyOn(Date, "now").mockReturnValueOnce(0).mockReturnValue(2);

    const result = await observeReeRun(new QueryClient(), client, {
      reeId: "ree-1",
      runId: "run-1",
      timeoutMs: 1,
    });

    expect(result.lines).toHaveLength(2000);
    expect(result.lines.at(-2)?.msg).toContain("[truncated]");
    expect(result.lines.at(-1)?.type).toBe("warn");
    now.mockRestore();
  });

  it("continues past the per-fetch page ceiling before finishing a terminal run", async () => {
    const getReeRunLogs = vi.fn(async (_reeId: string, _runId: string, cursor?: string) => {
      const page = Number(cursor ?? "0") + 1;
      return {
        lines: [{ type: "out" as const, msg: `page ${String(page)}` }],
        nextCursor: String(page),
        hasMore: page < 21,
      };
    });
    const client = {
      getReeRun: vi.fn().mockResolvedValue({
        ...wireRun(),
        runId: "run-1",
        reeId: "ree-1",
      }),
      getReeRunLogs,
    } as unknown as ReeRunsClient;
    const sleep = vi.fn().mockResolvedValue(undefined);

    const result = await observeReeRun(createTestQueryClient(), client, {
      reeId: "ree-1",
      runId: "run-1",
      sleep,
    });

    expect(getReeRunLogs).toHaveBeenCalledTimes(21);
    expect(getReeRunLogs).toHaveBeenLastCalledWith("ree-1", "run-1", "20");
    expect(result.lines).toHaveLength(21);
    expect(result.lines.at(-1)?.msg).toBe("page 21");
    expect(sleep).not.toHaveBeenCalled();
  });
});
