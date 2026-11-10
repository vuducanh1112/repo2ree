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
    experiment_environment: { evidence: "current", payload: "absent" },
  },
  workspace_files: [],
  ree_files: [],
  location_id: "lab-1",
  store_id: "lab-1",
};

describe("BenchConsole", () => {
  it("names the lab the REE is kept in", async () => {
    renderWithShell(<BenchConsole provisioned open onOpenChange={vi.fn()} reeName="demo" />, {
      reeId: "ree-1",
      services: fakeApiServices({ ree: { getRee: vi.fn().mockResolvedValue(reeDocument) } }),
    });

    expect(await screen.findByText("lab-1")).toBeVisible();
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
          getRee: vi.fn().mockResolvedValue(reeDocument),
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
