/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import type { Lab } from "@core/lab/Lab";
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

const lab: Lab = {
  id: "lab-1",
  label: "lab-host",
  description: "",
  lifecycleMode: "provider_managed",
  profiles: [
    {
      id: "standard",
      revision: "1",
      label: "Standard",
      description: "",
      substrate: "docker-nested",
      storagePolicy: "ephemeral",
    },
    {
      id: "shared",
      revision: "2",
      label: "Shared Docker",
      description: "",
      substrate: "docker-host-socket",
      storagePolicy: "ephemeral",
    },
  ],
  status: "connected",
  available: true,
};

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

    renderWithShell(<WorkbenchSetupDrawer lab={lab} loadRequested={false} />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { createRee },
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
        location_id: "lab-1",
        profile_id: "standard",
      }),
    );
    expect(await screen.findByText("image ready")).toBeInTheDocument();
    expect(await screen.findByText("Lab online — seating the specimen")).toBeInTheDocument();
  });

  it("sends the chosen fixed profile", async () => {
    const user = userEvent.setup();
    const createRee = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const getRun = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const listRunLogs = vi
      .fn()
      .mockResolvedValue({ entries: [], next_cursor: null, has_more: false });

    renderWithShell(<WorkbenchSetupDrawer lab={lab} loadRequested={false} />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { createRee },
        runs: { getRun, listRunLogs },
      }),
    });

    await user.selectOptions(screen.getByRole("combobox", { name: "Workbench profile" }), "shared");
    await user.click(screen.getByRole("button", { name: "Provision workbench" }));

    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith(
        expect.objectContaining({ location_id: "lab-1", profile_id: "shared" }),
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

    renderWithShell(<WorkbenchSetupDrawer lab={lab} loadRequested />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { createRee, initBundleUpload, uploadStagedBytes, loadReeBundle },
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
      failure: { reason: "workbench_unavailable", message: "no lab" },
    });
    const listRunLogs = vi
      .fn()
      .mockResolvedValue({ entries: [], next_cursor: null, has_more: false });

    renderWithShell(<WorkbenchSetupDrawer lab={lab} loadRequested={false} />, {
      route: "/lab-location",
      reeId: "active",
      services: fakeApiServices({
        ree: { createRee },
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
