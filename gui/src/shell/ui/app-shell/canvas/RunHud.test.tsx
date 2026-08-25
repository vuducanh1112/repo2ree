/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { RunHud } from "./RunHud";

const run = (runId: string, operation: "source" | "build", status: "running" | "failed") => ({
  run_id: runId,
  ree_id: "ree-1",
  operation,
  status,
  created_at: "2026-01-01T10:00:00Z",
  started_at: "2026-01-01T10:00:01Z",
  finished_at: status === "failed" ? "2026-01-01T10:00:02Z" : null,
  outputs: {},
  failure:
    status === "failed"
      ? { category: "execution", message: "compiler failed", retryable: true, origin: "worker" }
      : null,
});

describe("RunHud", () => {
  it("follows an active run, filters its streams, and exposes failed history", async () => {
    const user = userEvent.setup();
    const buildRun = run("build-2", "build", "running");
    const sourceRun = run("source-1", "source", "failed");
    const listRuns = vi.fn().mockResolvedValue({ runs: [buildRun, sourceRun], next_cursor: null });
    const getRun = vi
      .fn()
      .mockResolvedValue({ ...buildRun, status: "succeeded", finished_at: "2026-01-01T10:00:03Z" });
    const listRunLogs = vi.fn().mockResolvedValue({
      entries: [
        {
          seq: 1,
          ts: "2026-01-01T10:00:01Z",
          level: "info",
          stream: "stdout",
          message: "building",
        },
        {
          seq: 2,
          ts: "2026-01-01T10:00:02Z",
          level: "error",
          stream: "stderr",
          message: "warning output",
        },
        {
          seq: 3,
          ts: "2026-01-01T10:00:03Z",
          level: "info",
          stream: "system",
          message: "complete",
        },
      ],
      next_cursor: null,
      has_more: false,
    });
    renderWithShell(<RunHud open onOpenChange={vi.fn()} />, {
      reeId: "ree-1",
      services: fakeApiServices({ runs: { listRuns, getRun, listRunLogs } }),
    });

    // Auto-follow lands on the active run's tab once the run list resolves, so
    // opening the console from the footer shows whatever ran last.
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "Build" })).toHaveAttribute("aria-selected", "true"),
    );
    expect(await screen.findByText("building")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "stderr" }));
    expect(screen.queryByText("warning output")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "stdout" }));
    await user.click(screen.getByRole("button", { name: "system" }));
    await waitFor(() => expect(screen.getByText("warning output")).toBeInTheDocument());

    await user.click(screen.getByRole("tab", { name: "Source" }));
    expect(screen.getByRole("status", { name: "Run failed" })).toBeInTheDocument();
    expect(screen.getByText("compiler failed")).toBeInTheDocument();
    expect(screen.getByText("retryable")).toBeInTheDocument();
  });
});
