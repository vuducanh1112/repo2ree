/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../tests/support/renderApp";
import { useReeRunsQuery } from "../runs/queries";
import { useReeDocumentFollowsRuns, useRunsAwaitingDocument } from "./followRuns";

const run = (operation: string, status: "running" | "succeeded") => ({
  run_id: `${operation}-1`,
  ree_id: "ree-1",
  operation,
  status,
  created_at: "2026-01-01T00:00:00Z",
  started_at: "2026-01-01T00:00:01Z",
  finished_at: status === "succeeded" ? "2026-01-01T00:00:02Z" : null,
  outputs: {},
  failure: null,
});

const document = (runtimeReceiptRunId?: string) => ({
  ree_id: "ree-1",
  status: "draft" as const,
  ree: { subject: { definition: { name: "hello" } } },
  audit: {
    source: { evidence: "current", payload: "present", receipt_run_id: "source-1" },
    runtime: runtimeReceiptRunId
      ? { evidence: "current", payload: "present", receipt_run_id: runtimeReceiptRunId }
      : { evidence: "missing", payload: "missing" },
  },
  workspace_files: [],
  ree_files: [],
});

function follow(operation: string, reads: ReturnType<typeof document>[]) {
  const listRuns = vi
    .fn()
    .mockResolvedValue({ runs: [run(operation, "running")], next_cursor: null });
  const getRee = vi.fn().mockResolvedValue(document());
  const { Wrapper, queryClient } = createShellWrapper({
    reeId: "ree-1",
    services: fakeApiServices({ ree: { getRee }, runs: { listRuns } }),
  });
  const { result } = renderHook(
    () => {
      useReeDocumentFollowsRuns({ reeId: "ree-1", enabled: true });
      // Further subscribers to the run list, as the page has: none of them reads the document.
      useReeRunsQuery("ree-1");
      const listed = useReeRunsQuery("ree-1").data;
      return { listed, awaiting: useRunsAwaitingDocument("ree-1") };
    },
    { wrapper: Wrapper },
  );
  const settle = async () => {
    // The page has loaded with the build running.
    await waitFor(() => expect(result.current.listed).toBeDefined());
    await waitFor(() => expect(getRee).toHaveBeenCalledTimes(1));
    for (const read of reads) getRee.mockResolvedValueOnce(read);
    listRuns.mockResolvedValue({ runs: [run(operation, "succeeded")], next_cursor: null });
    await act(() => queryClient.invalidateQueries({ queryKey: ["ree-runs", "ree-1"] }));
  };
  return { awaiting: () => result.current.awaiting, getRee, settle };
}

describe("useReeDocumentFollowsRuns", () => {
  it("keeps reading the document after a build until it shows the build's receipt", async () => {
    // The run reports success before a read of the document shows its receipt.
    const { awaiting, getRee, settle } = follow("build", [
      document(),
      document(),
      document("build-1"),
    ]);
    await settle();

    await waitFor(() => expect(awaiting().has("build-1")).toBe(true));
    await waitFor(() => expect(awaiting().size).toBe(0), { timeout: 5000 });
    expect(getRee).toHaveBeenCalledTimes(4);
  });

  it("reads the document once when it already shows the receipt", async () => {
    const { awaiting, getRee, settle } = follow("build", [document("build-1")]);
    await settle();

    await waitFor(() => expect(getRee).toHaveBeenCalledTimes(2));
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(getRee).toHaveBeenCalledTimes(2);
    expect(awaiting().size).toBe(0);
  });

  it("does not wait on a run that files no receipt", async () => {
    const { awaiting, getRee, settle } = follow("seal", [document()]);
    await settle();

    await waitFor(() => expect(getRee).toHaveBeenCalledTimes(2));
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(getRee).toHaveBeenCalledTimes(2);
    expect(awaiting().size).toBe(0);
  });
});
