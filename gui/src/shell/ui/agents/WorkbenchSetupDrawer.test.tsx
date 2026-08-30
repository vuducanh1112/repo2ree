/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import type { Agent } from "@core/agent/Agent";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../tests/support/renderApp";
import { WorkbenchSetupDrawer } from "./WorkbenchSetupDrawer";

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

const lab: Agent = {
  id: "agent-1",
  hostname: "lab-host",
  version: "1",
  dockerMode: "dind",
  connectedAt: "2026-01-01T00:00:00Z",
  status: "connected",
};

function catalogs() {
  return {
    listWorkbenchImages: vi.fn().mockResolvedValue({
      images: [{ id: "python", ref: "bench:python", label: "Python", description: "Python tools" }],
      default_id: "python",
    }),
  };
}

describe("WorkbenchSetupDrawer", () => {
  it("provisions a workbench on the chosen lab and shows its streamed log", async () => {
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

    renderWithShell(<WorkbenchSetupDrawer agent={lab} loadRequested={false} />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { ...catalogs(), createRee },
        runs: { getRun, listRunLogs },
      }),
    });

    // The lab is settled before this drawer opens, so it states it rather than
    // asking again.
    expect(screen.getByText("lab-host")).toBeInTheDocument();

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

  it("sends the chosen base image rather than the catalog default", async () => {
    const user = userEvent.setup();
    const createRee = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const getRun = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const listRunLogs = vi
      .fn()
      .mockResolvedValue({ entries: [], next_cursor: null, has_more: false });

    renderWithShell(<WorkbenchSetupDrawer agent={lab} loadRequested={false} />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { ...catalogs(), createRee },
        runs: { getRun, listRunLogs },
      }),
    });

    await user.click(await screen.findByRole("button", { name: /Python/ }));
    await user.click(screen.getByRole("button", { name: "Provision workbench" }));

    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith(
        expect.objectContaining({ workbench_image: "bench:python" }),
      ),
    );
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

    renderWithShell(<WorkbenchSetupDrawer agent={lab} loadRequested />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { ...catalogs(), createRee, initBundleUpload, uploadStagedBytes, loadReeBundle },
        runs: { getRun, listRunLogs },
      }),
    });

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

  it("surfaces the typed failure reason when provisioning fails", async () => {
    const user = userEvent.setup();
    const createRee = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const getRun = vi.fn().mockResolvedValue({
      ...wireRun("provision-1"),
      status: "failed" as const,
      failure: { reason: "workbench_unavailable", message: "no agent" },
    });
    const listRunLogs = vi
      .fn()
      .mockResolvedValue({ entries: [], next_cursor: null, has_more: false });

    renderWithShell(<WorkbenchSetupDrawer agent={lab} loadRequested={false} />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { ...catalogs(), createRee },
        runs: { getRun, listRunLogs },
      }),
    });

    await user.click(screen.getByRole("button", { name: "Provision workbench" }));

    // A bare "failed" tells the author nothing they can act on.
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveAttribute("data-tone", "danger");
    expect(alert).not.toHaveTextContent(/^Provisioning failed$/);
  });
});
