import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { userEvent } from "vitest/browser";
import "../../theme/index.css";
import { FileTabsPanel } from "./FileTabsPanel";

const entries = [
  { node: { id: "a", name: "a.txt", type: "file" as const, content: "alpha" }, path: "a.txt" },
  { node: { id: "b", name: "b.txt", type: "file" as const, content: "beta" }, path: "src/b.txt" },
];

describe("FileTabsPanel keyboard interaction", () => {
  it("moves tab focus and activation with wrapping arrow navigation", async () => {
    const onActivate = vi.fn();
    const { getByRole } = render(
      <FileTabsPanel
        openEntries={entries}
        activeEntry={entries[0]}
        left={20}
        top={30}
        onActivate={onActivate}
        onClose={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    const first = getByRole("tab", { name: "a.txt" });
    const second = getByRole("tab", { name: "b.txt" });

    first.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onActivate).toHaveBeenLastCalledWith("b");
    expect(second).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onActivate).toHaveBeenLastCalledWith("a");
    expect(first).toHaveFocus();
  });

  it("keeps close-file and dismiss-window actions distinct", async () => {
    const onClose = vi.fn();
    const onDismiss = vi.fn();
    const { getByRole } = render(
      <FileTabsPanel
        openEntries={entries}
        activeEntry={entries[0]}
        left={0}
        top={0}
        onActivate={vi.fn()}
        onClose={onClose}
        onDismiss={onDismiss}
      />,
    );
    await userEvent.click(getByRole("button", { name: "Close a.txt" }));
    expect(onClose).toHaveBeenCalledWith("a");
    expect(onDismiss).not.toHaveBeenCalled();
    await userEvent.click(getByRole("button", { name: "Close" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
