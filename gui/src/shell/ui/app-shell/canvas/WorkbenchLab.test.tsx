/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { WorkbenchLab } from "./WorkbenchLab";

const wireRun = (runId: string) => ({
  run_id: runId,
  ree_id: "ree-new",
  operation: "provision" as const,
  status: "succeeded" as const,
  created_at: "2026-01-01T00:00:00Z",
  started_at: "2026-01-01T00:00:01Z",
  finished_at: "2026-01-01T00:00:02Z",
  outputs: {},
  failure: null,
});

function catalogs() {
  return {
    listAgents: vi.fn().mockResolvedValue({
      agents: [
        {
          agent_id: "agent-1",
          hostname: "lab-host",
          version: "1",
          docker_mode: "dind",
          connected_at: "2026-01-01T00:00:00Z",
        },
      ],
    }),
    listWorkbenchImages: vi.fn().mockResolvedValue({
      images: [{ id: "python", ref: "bench:python", label: "Python", description: "Python tools" }],
      default_id: "python",
    }),
  };
}

describe("WorkbenchLab", () => {
  it("provisions a workbench on the selected agent and shows its streamed log", async () => {
    const user = userEvent.setup();
    const createRee = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const getRun = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const listRunLogs = vi.fn().mockResolvedValue({
      entries: [
        {
          seq: 1,
          ts: "2026-01-01T00:00:01Z",
          level: "info",
          stream: "stdout",
          message: "image ready",
        },
      ],
      next_cursor: null,
      has_more: false,
    });
    renderWithShell(
      <WorkbenchLab evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }} />,
      {
        route: "/workspace?agentId=agent-1",
        reeId: "active",
        services: fakeApiServices({
          ree: { ...catalogs(), createRee },
          runs: { getRun, listRunLogs },
        }),
      },
    );

    expect(await screen.findByText("lab-host")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Provision workbench" }));
    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith({
        name: "REE",
        workbench_image: undefined,
        agent_id: "agent-1",
      }),
    );
    expect(await screen.findByText("image ready")).toBeInTheDocument();
    expect(await screen.findByText("Lab online — seating the specimen")).toBeInTheDocument();
  });

  it("requires and restores a selected REE bundle for the load workflow", async () => {
    const user = userEvent.setup();
    const createRee = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const initBundleUpload = vi
      .fn()
      .mockResolvedValue({ upload_url: "/upload", upload_token: "token" });
    const uploadStagedBytes = vi.fn().mockResolvedValue(undefined);
    const loadReeBundle = vi.fn().mockResolvedValue(wireRun("load-2"));
    const getRun = vi
      .fn()
      .mockImplementation((_reeId: string, runId: string) => Promise.resolve(wireRun(runId)));
    const listRunLogs = vi
      .fn()
      .mockResolvedValue({ entries: [], next_cursor: null, has_more: false });
    renderWithShell(
      <WorkbenchLab evaluation={{ dependencyLevel: 0, environmentLevel: 0, machineLevel: 0 }} />,
      {
        route: "/workspace?load=1",
        reeId: "active",
        services: fakeApiServices({
          ree: { ...catalogs(), createRee, initBundleUpload, uploadStagedBytes, loadReeBundle },
          runs: { getRun, listRunLogs },
        }),
      },
    );

    const provision = screen.getByRole("button", { name: "Provision workbench" });
    expect(provision).toBeDisabled();
    const bundle = new File(["bundle"], "hello-world.zip", { type: "application/zip" });
    await user.upload(screen.getByLabelText("REE bundle"), bundle);
    await user.click(screen.getByRole("button", { name: "Provision and load REE" }));

    await waitFor(() =>
      expect(loadReeBundle).toHaveBeenCalledWith("ree-new", "token", "hello-world.zip"),
    );
    expect(initBundleUpload).toHaveBeenCalledWith(
      "ree-new",
      expect.objectContaining({ file_name: "hello-world.zip" }),
    );
    expect(await screen.findByText("REE loaded — opening it")).toBeInTheDocument();
  });
});
