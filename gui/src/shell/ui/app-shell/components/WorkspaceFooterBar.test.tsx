/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { WorkspaceFooterBar } from "./WorkspaceFooterBar";

function services(runs: unknown[] = []) {
  return fakeApiServices({
    ree: {
      getRee: vi.fn().mockResolvedValue({
        ree_id: "ree-1",
        status: "draft" as const,
        ree: { subject: { definition: { name: "demo" } } },
        audit: {
          source: { evidence: "current", payload: "absent" },
          runtime: { evidence: "current", payload: "absent" },
        },
        workspace_files: [],
        ree_files: [],
        workbench_image: "ghcr.io/repo2ree/bench:python",
      }),
    },
    runs: { listRuns: vi.fn().mockResolvedValue({ runs, next_cursor: null }) },
  });
}

function render(props: Partial<Parameters<typeof WorkspaceFooterBar>[0]> = {}, runs?: unknown[]) {
  return renderWithShell(
    <WorkspaceFooterBar
      provisioned
      benchOpen={false}
      logsOpen={false}
      onBenchOpenChange={vi.fn()}
      onLogsOpenChange={vi.fn()}
      {...props}
    />,
    { reeId: "ree-1", services: services(runs) },
  );
}

describe("WorkspaceFooterBar", () => {
  it("reports the workbench image and the newest run, and toggles both consoles", async () => {
    const user = userEvent.setup();
    const onBenchOpenChange = vi.fn();
    const onLogsOpenChange = vi.fn();

    render({ onBenchOpenChange, onLogsOpenChange, logsOpen: true }, [
      {
        run_id: "build-1",
        ree_id: "ree-1",
        operation: "build",
        status: "succeeded",
        created_at: "2026-01-01T10:00:00Z",
        started_at: "2026-01-01T10:00:01Z",
        finished_at: "2026-01-01T10:00:02Z",
        outputs: {},
        failure: null,
      },
    ]);

    expect(screen.getByRole("region", { name: "Workbench status" })).toBeVisible();
    expect(await screen.findByText("ghcr.io/repo2ree/bench:python")).toBeVisible();
    expect(await screen.findByText("Build · succeeded")).toBeVisible();

    // Each cell shows whether the console it owns is open.
    expect(screen.getByRole("button", { name: /Workbench/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("button", { name: /Logs/ })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: /Workbench/ }));
    await user.click(screen.getByRole("button", { name: /Logs/ }));
    expect(onBenchOpenChange).toHaveBeenCalledWith(true);
    expect(onLogsOpenChange).toHaveBeenCalledWith(false);
  });

  it("says so when there is no workbench and nothing has run", async () => {
    render({ provisioned: false });

    expect(screen.getByText("Awaiting workbench")).toBeVisible();
    await waitFor(() => expect(screen.getByText("No runs yet")).toBeVisible());
  });
});
