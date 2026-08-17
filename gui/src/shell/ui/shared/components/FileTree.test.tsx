import type { FileTreeNode } from "@core/workspace/FileTree";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileNode } from "./FileTree";

const tree: FileTreeNode = {
  id: "src",
  name: "src",
  type: "folder",
  children: [
    { id: "main", name: "main.py", type: "file" },
    {
      id: "tests",
      name: "tests",
      type: "folder",
      children: [{ id: "test-main", name: "test_main.py", type: "file" }],
    },
  ],
};

function renderTree(props: Partial<Parameters<typeof FileNode>[0]> = {}) {
  const onSelect = vi.fn();
  render(<FileNode node={tree} onSelect={onSelect} selectedId={null} {...props} />);
  return { onSelect };
}

describe("FileNode", () => {
  it("opens the root but leaves deeper folders closed", () => {
    renderTree();
    // depth 0 is open, so its direct children are visible...
    expect(screen.getByRole("button", { name: /\bmain\.py/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /tests/ })).toBeInTheDocument();
    // ...but tests/ is depth 1 and starts closed, so its child is not rendered.
    expect(screen.queryByRole("button", { name: /test_main\.py/ })).not.toBeInTheDocument();
  });

  it("leaves even the root shut when the caller asks for no open depth", () => {
    renderTree({ defaultOpenDepth: 0 });
    expect(screen.getByRole("button", { name: /src/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\bmain\.py/ })).not.toBeInTheDocument();
  });

  it("toggles a folder open and shut instead of selecting it", async () => {
    const { onSelect } = renderTree();

    await userEvent.click(screen.getByRole("button", { name: /tests/ }));
    expect(screen.getByRole("button", { name: /test_main\.py/ })).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /tests/ }));
    expect(screen.queryByRole("button", { name: /test_main\.py/ })).not.toBeInTheDocument();
  });

  it("selects a file, passing the node itself rather than its id", async () => {
    const { onSelect } = renderTree();

    await userEvent.click(screen.getByRole("button", { name: /\bmain\.py/ }));

    expect(onSelect).toHaveBeenCalledWith({ id: "main", name: "main.py", type: "file" });
  });

  it("reveals every folder under forceOpen, which is how filtering shows its hits", () => {
    renderTree({ forceOpen: true });
    expect(screen.getByRole("button", { name: /test_main\.py/ })).toBeInTheDocument();
  });

  it("does not collapse a forced-open folder when it is clicked", async () => {
    renderTree({ forceOpen: true });

    await userEvent.click(screen.getByRole("button", { name: /tests/ }));

    // The click flips the folder's own `open`, but `forceOpen` wins — a filtered
    // tree must not be collapsible out from under the filter.
    expect(screen.getByRole("button", { name: /test_main\.py/ })).toBeInTheDocument();
  });

  it("marks referenced files with a REF badge, and only files", () => {
    renderTree({ highlightedPaths: new Set(["main.py", "tests"]), forceOpen: true });

    const badges = screen.getAllByText("REF");
    expect(badges).toHaveLength(1);
    expect(screen.getByRole("button", { name: /\bmain\.py/ })).toHaveTextContent("REF");
  });

  it("drops the REF badge once the referenced file is the selection", () => {
    renderTree({ highlightedPaths: new Set(["main.py"]), selectedId: "main" });
    expect(screen.queryByText("REF")).not.toBeInTheDocument();
  });
});
