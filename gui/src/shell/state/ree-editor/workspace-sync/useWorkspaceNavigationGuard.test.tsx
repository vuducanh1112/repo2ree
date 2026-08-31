import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, Link, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { useWorkspaceNavigationGuard } from "./useWorkspaceNavigationGuard";

function GuardedWorkspace({
  flush,
  onFlushFailed,
}: {
  flush: () => Promise<void>;
  onFlushFailed?: (error: unknown) => void;
}) {
  useWorkspaceNavigationGuard({ shouldBlock: true, flush, onFlushFailed });
  return <Link to="/home">Leave workspace</Link>;
}

function renderGuard(flush: () => Promise<void>, onFlushFailed?: (error: unknown) => void) {
  const router = createMemoryRouter(
    [
      {
        path: "/workspace",
        element: <GuardedWorkspace flush={flush} onFlushFailed={onFlushFailed} />,
      },
      { path: "/home", element: <div>Home</div> },
    ],
    { initialEntries: ["/workspace"] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe("useWorkspaceNavigationGuard", () => {
  it("flushes pending edits before allowing route navigation", async () => {
    const flush = vi.fn().mockResolvedValue(undefined);
    const router = renderGuard(flush);

    fireEvent.click(screen.getByRole("link", { name: "Leave workspace" }));

    await waitFor(() => expect(flush).toHaveBeenCalledOnce());
    await waitFor(() => expect(router.state.location.pathname).toBe("/home"));
  });

  // The guard delays an exit until the draft is durable; it does not hold
  // someone in a workspace a failing server will never let them leave. It used
  // to cancel the navigation outright, which turned any unsaveable draft — a
  // sealed REE, an offline backend — into a route with no way out and no
  // explanation. The exit goes ahead and the failure is announced instead.
  it("lets the exit through when the flush fails, and says so", async () => {
    const flush = vi.fn().mockRejectedValue(new Error("offline"));
    const onFlushFailed = vi.fn();
    const router = renderGuard(flush, onFlushFailed);

    fireEvent.click(screen.getByRole("link", { name: "Leave workspace" }));

    await waitFor(() => expect(flush).toHaveBeenCalledOnce());
    await waitFor(() => expect(router.state.location.pathname).toBe("/home"));
    expect(onFlushFailed).toHaveBeenCalledOnce();
  });

  it("warns before a browser-level exit while edits are pending", () => {
    renderGuard(vi.fn().mockResolvedValue(undefined));
    const event = new Event("beforeunload", { cancelable: true });

    act(() => window.dispatchEvent(event));

    expect(event.defaultPrevented).toBe(true);
  });
});
