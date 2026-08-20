import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FocusDock } from "./FocusDock";

describe("FocusDock", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("exposes modal semantics, traps focus, and restores the opener", () => {
    vi.spyOn(HTMLElement.prototype, "getClientRects").mockReturnValue([
      new DOMRect(0, 0, 20, 20),
    ] as unknown as DOMRectList);
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();

    const { unmount } = render(
      <FocusDock node={undefined} originRect={null} closable onClose={vi.fn()}>
        <button type="button">Last action</button>
      </FocusDock>,
    );

    const dialog = screen.getByRole("dialog", { name: "Step page" });
    const close = screen.getByRole("button", { name: "Close" });
    const last = screen.getByRole("button", { name: "Last action" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(close).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "ArrowRight" });

    unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it("keeps an unclosable empty dock focused as a modal boundary", () => {
    const onClose = vi.fn();
    render(
      <FocusDock
        node={undefined}
        originRect={new DOMRect(10, 20, 30, 40)}
        closable={false}
        onClose={onClose}
      >
        <p>Required setup</p>
      </FocusDock>,
    );

    const dialog = screen.getByRole("dialog", { name: "Step page" });
    fireEvent.keyDown(dialog, { key: "Tab" });
    fireEvent.click(screen.getByRole("button", { name: "Back to constellation" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
