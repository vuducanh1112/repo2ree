/* biome-ignore-all lint/style/useNamingConvention: fixtures use wire names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { OperationHistorySection } from "./OperationHistorySection";

const operation = {
  schema_version: 1 as const,
  selection_version: 1,
  attempt_id: "attempt",
  run_id: "run-1",
  sequence: 2,
  command: { operation: "write_file", args: { path: "example.txt", content: "old content" } },
  scope: ".",
  capture_status: "captured" as const,
  operation_status: "succeeded" as const,
  before_snapshot_id: "before-commit",
  after_snapshot_id: "after-commit",
};

describe("operation history", () => {
  it("shows captured inputs, snapshot references and manual refresh", async () => {
    const listOperationHistory = vi.fn().mockResolvedValue({ operations: [operation] });
    const user = userEvent.setup();
    renderWithShell(<OperationHistorySection enabled />, {
      reeId: "ree-1",
      services: fakeApiServices({ ree: { listOperationHistory } }),
    });
    await user.click(await screen.findByText("#2 write_file · succeeded"));
    expect(screen.getByText("Before: before-commit")).toBeVisible();
    expect(screen.getByText("After: after-commit")).toBeVisible();
    await user.click(screen.getByText("Command and raw record"));
    expect(screen.getByText(/old content/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh history" }));
    await waitFor(() => expect(listOperationHistory).toHaveBeenCalledTimes(2));
  });

  it("explains pending legacy records without inventing an order", async () => {
    renderWithShell(<OperationHistorySection enabled />, {
      reeId: "ree-1",
      services: fakeApiServices({
        ree: {
          listOperationHistory: vi.fn().mockResolvedValue({
            operations: [
              {
                ...operation,
                sequence: null,
                scope: "reviews/review-1",
                capture_status: "pending",
                operation_status: "unknown",
              },
            ],
          }),
        },
      }),
    });
    await userEvent.click(await screen.findByText("Unordered · write_file · unknown"));
    expect(screen.getByText(/completion may be unresolved/)).toBeVisible();
    expect(screen.getByText("Scope: reviews/review-1")).toBeVisible();
  });

  it("does not fetch while closed and reports query errors", async () => {
    const listOperationHistory = vi.fn().mockRejectedValue(new Error("offline"));
    const { rerender } = renderWithShell(<OperationHistorySection enabled={false} />, {
      reeId: "ree-1",
      services: fakeApiServices({ ree: { listOperationHistory } }),
    });
    expect(listOperationHistory).not.toHaveBeenCalled();
    rerender(<OperationHistorySection enabled />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load operation history");
  });
});
