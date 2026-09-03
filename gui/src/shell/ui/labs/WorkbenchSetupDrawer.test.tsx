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
  images: [
    {
      id: "standard",
      ref: "docker.io/library/docker:29-dind",
      label: "Standard (docker)",
      description: "Lean docker-in-docker bench.",
    },
    {
      id: "python",
      ref: "docker.io/library/python:3.11-slim",
      label: "Python 3.11",
      description: "",
    },
  ],
  acceptsCustomImage: true,
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

    // Nothing was picked, so nothing is asserted: a blank image lets the lab
    // resolve its own default, which is the entry the selector already shows
    // as chosen. Sending its ref instead would pin whatever the catalog held
    // when this drawer happened to load.
    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith({ name: "REE", location_id: "lab-1", image: "" }),
    );
    expect(await screen.findByText("image ready")).toBeInTheDocument();
    expect(await screen.findByText("Lab online — seating the specimen")).toBeInTheDocument();
  });

  it("shows every entry's ref, and sends the one the author picks", async () => {
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

    // Every ref is on screen before anything is committed — the whole catalog
    // at once, not one entry at a time behind a closed control. It is the base
    // of everything this REE will later claim to reproduce.
    expect(screen.getByText("docker.io/library/docker:29-dind")).toBeInTheDocument();
    expect(screen.getByText("docker.io/library/python:3.11-slim")).toBeInTheDocument();

    // The lab's first entry reads as chosen before the author picks anything,
    // because that is what a blank image resolves to server-side.
    expect(screen.getByRole("button", { name: /Standard \(docker\)/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: /Python 3\.11/ }));
    await user.click(screen.getByRole("button", { name: "Provision workbench" }));

    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith(
        expect.objectContaining({
          location_id: "lab-1",
          image: "docker.io/library/python:3.11-slim",
        }),
      ),
    );
  });

  it("provisions from a custom ref when the lab accepts one", async () => {
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

    await user.click(screen.getByRole("button", { name: /Custom…/ }));
    // Custom picked but still blank would silently provision the lab default,
    // so the button waits for the ref rather than guessing.
    expect(screen.getByRole("button", { name: "Provision workbench" })).toBeDisabled();

    await user.type(
      screen.getByRole("textbox", { name: "Custom image reference" }),
      "ghcr.io/me/bench:v3",
    );
    await user.click(screen.getByRole("button", { name: "Provision workbench" }));

    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith(
        expect.objectContaining({ image: "ghcr.io/me/bench:v3" }),
      ),
    );
  });

  it("offers no custom-image path at a lab that refuses one", () => {
    renderWithShell(
      <WorkbenchSetupDrawer lab={{ ...lab, acceptsCustomImage: false }} loadRequested={false} />,
      { route: "/lab-location", reeId: "active", services: fakeApiServices({}) },
    );

    expect(screen.queryByRole("button", { name: /Custom…/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Standard \(docker\)/ })).toBeInTheDocument();
  });

  it("asks for no image at a pre-provisioned lab, whose bench already exists", async () => {
    const user = userEvent.setup();
    const createRee = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const getRun = vi.fn().mockResolvedValue(wireRun("provision-1"));
    const listRunLogs = vi
      .fn()
      .mockResolvedValue({ entries: [], next_cursor: null, has_more: false });

    renderWithShell(
      <WorkbenchSetupDrawer
        lab={{ ...lab, lifecycleMode: "externally_managed", images: [], acceptsCustomImage: false }}
        loadRequested={false}
      />,
      {
        route: "/lab-location",
        reeId: "active",
        services: fakeApiServices({ ree: { createRee }, runs: { getRun, listRunLogs } }),
      },
    );

    expect(screen.queryByText("Base image")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Provision workbench" }));

    await waitFor(() =>
      expect(createRee).toHaveBeenCalledWith({ name: "REE", location_id: "lab-1", image: "" }),
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
