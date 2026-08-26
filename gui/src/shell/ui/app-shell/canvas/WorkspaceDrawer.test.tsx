import { PAGE } from "@core/app-shell/pages";
import { activeNode } from "@core/canvas/canvasNodes";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceDrawer } from "./WorkspaceDrawer";

describe("WorkspaceDrawer", () => {
  beforeEach(() => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1504 });
  });

  it("is a non-modal region that closes from its frame or Escape", () => {
    const onClose = vi.fn();
    render(
      <WorkspaceDrawer node={activeNode(PAGE.METADATA)} onClose={onClose}>
        <p>Metadata fields</p>
      </WorkspaceDrawer>,
    );

    expect(screen.getByRole("region", { name: "Metadata" })).not.toHaveAttribute("aria-modal");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("resizes from the left edge with pointer and keyboard input", () => {
    render(
      <WorkspaceDrawer node={activeNode(PAGE.METADATA)} onClose={vi.fn()}>
        <p>Metadata fields</p>
      </WorkspaceDrawer>,
    );

    const separator = screen.getByRole("separator", { name: "Resize metadata panel" });
    expect(separator).toHaveAttribute("aria-valuenow", "760");

    fireEvent.pointerDown(separator, { button: 0, isPrimary: true, clientX: 700 });
    fireEvent.pointerMove(window, { clientX: 600 });
    fireEvent.pointerUp(window);
    expect(separator).toHaveAttribute("aria-valuenow", "860");

    fireEvent.keyDown(separator, { key: "ArrowRight" });
    expect(separator).toHaveAttribute("aria-valuenow", "836");

    fireEvent.pointerDown(separator, { button: 0, isPrimary: true, clientX: 600 });
    fireEvent.pointerMove(window, { clientX: 2000 });
    expect(separator).toHaveAttribute("aria-valuenow", "440");
    fireEvent.pointerCancel(window);
  });

  it("ignores secondary pointer gestures", () => {
    render(
      <WorkspaceDrawer node={undefined} onClose={vi.fn()}>
        <p>Workspace fields</p>
      </WorkspaceDrawer>,
    );

    const separator = screen.getByRole("separator", { name: "Resize workspace panel" });
    fireEvent.pointerDown(separator, { button: 2, isPrimary: true, clientX: 700 });
    fireEvent.pointerMove(window, { clientX: 600 });

    expect(separator).toHaveAttribute("aria-valuenow", "760");
    expect(screen.getByRole("region", { name: "Workspace page" })).toBeInTheDocument();
  });
});
