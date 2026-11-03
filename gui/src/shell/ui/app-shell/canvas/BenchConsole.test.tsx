/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { BenchConsole } from "./BenchConsole";

const reeDocument = {
  ree_id: "ree-1",
  status: "draft" as const,
  ree: { subject: { definition: { name: "demo" } } },
  audit: {
    source: { evidence: "current", payload: "absent" },
    runtime: { evidence: "current", payload: "absent" },
  },
  workspace_files: [],
  ree_files: [],
  allocation_id: "alloc-1",
  location_id: "lab-1",
  image: "docker.io/library/docker:29-dind",
};

function services(state: string) {
  return fakeApiServices({
    ree: {
      getRee: vi.fn().mockResolvedValue(reeDocument),
      getAllocation: vi.fn().mockResolvedValue({
        request: {
          allocation_id: "alloc-1",
          ree_id: "ree-1",
          location_id: "lab-1",
          image: "docker.io/library/docker:29-dind",
        },
        state,
        resolved_image: "docker.io/library/docker:29-dind",
        detail: "",
        created_at: "2026-01-01T10:00:00Z",
        updated_at: "2026-01-01T10:00:05Z",
      }),
    },
  });
}

function render(state: string) {
  return renderWithShell(<BenchConsole provisioned open onOpenChange={vi.fn()} reeName="demo" />, {
    reeId: "ree-1",
    services: services(state),
  });
}

describe("BenchConsole", () => {
  it("names the image it runs and the allocation that obtained it", async () => {
    render("assigned");

    expect(await screen.findByText("docker:29-dind @ lab-1")).toBeVisible();
    expect(await screen.findByText("alloc-1")).toBeVisible();
    expect(await screen.findByText("Assigned")).toBeVisible();
  });

  it("reports an allocation that has not reached its workbench yet", async () => {
    render("waiting_for_workbench");

    expect(await screen.findByText("Waiting for workbench")).toBeVisible();
  });

  it("deletes an REE kept in a store only once the author confirms", async () => {
    const user = userEvent.setup();
    const deleteRee = vi
      .fn()
      .mockResolvedValue({ deleted_at: "2026-01-01T10:00:00Z", state: "deleted" });
    renderWithShell(<BenchConsole provisioned open onOpenChange={vi.fn()} reeName="demo" />, {
      reeId: "ree-1",
      services: fakeApiServices({
        ree: {
          getRee: vi.fn().mockResolvedValue({
            ...reeDocument,
            allocation_id: null,
            image: null,
            store_id: "lab-1",
          }),
          deleteRee,
        },
      }),
    });

    await user.click(await screen.findByText("Delete REE"));
    expect(deleteRee).not.toHaveBeenCalled();
    expect(screen.getByText("Deletes the REE and its files from the lab's store.")).toBeVisible();

    await user.click(screen.getByText("Confirm: delete this REE"));
    await waitFor(() => expect(deleteRee).toHaveBeenCalledWith("ree-1"));
  });
});
