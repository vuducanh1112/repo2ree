import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, Link, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { useWorkspaceNavigationGuard } from "./useWorkspaceNavigationGuard";

function GuardedWorkspace({ flush }: { flush: () => Promise<void> }) {
  useWorkspaceNavigationGuard({ shouldBlock: true, flush });
  return <Link to="/home">Leave workspace</Link>;
}

function renderGuard(flush: () => Promise<void>) {
  const router = createMemoryRouter(
    [
      { path: "/workspace", element: <GuardedWorkspace flush={flush} /> },
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

  it("keeps the editor open when the flush fails", async () => {
    const flush = vi.fn().mockRejectedValue(new Error("offline"));
    const router = renderGuard(flush);

    fireEvent.click(screen.getByRole("link", { name: "Leave workspace" }));

    await waitFor(() => expect(flush).toHaveBeenCalledOnce());
    expect(router.state.location.pathname).toBe("/workspace");
  });

  it("warns before a browser-level exit while edits are pending", () => {
    renderGuard(vi.fn().mockResolvedValue(undefined));
    const event = new Event("beforeunload", { cancelable: true });

    act(() => window.dispatchEvent(event));

    expect(event.defaultPrevented).toBe(true);
  });
});
