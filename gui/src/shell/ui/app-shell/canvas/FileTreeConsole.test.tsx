import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileTreeConsole } from "./FileTreeConsole";

// The workspace is materialized from upstream + overlay, so an authored script
// is genuinely present in both inventories under the same path. That collision
// is the reason node ids are namespaced by inventory.
const workspaceFiles: FileTreeNode[] = [
  { id: "ws:build.sh", name: "build.sh", type: "file", content: "workspace copy" },
  {
    id: "ws-dir:src",
    name: "src",
    type: "folder",
    children: [{ id: "ws:src/main.py", name: "main.py", type: "file", content: "print()" }],
  },
];

const reeFiles: ReeFile[] = [
  { id: "ree:overlay/build.sh", name: "overlay/build.sh", type: "file", content: "overlay copy" },
  { id: "ree:artifacts/sbom.json", name: "artifacts/sbom.json", type: "file", content: "{}" },
];

function renderConsole(props: Partial<Parameters<typeof FileTreeConsole>[0]> = {}) {
  const onOpenChange = vi.fn();
  const view = render(
    <FileTreeConsole
      workspaceFiles={workspaceFiles}
      reeFiles={reeFiles}
      open
      onOpenChange={onOpenChange}
      {...props}
    />,
  );
  return { onOpenChange, container: view.container };
}

describe("FileTreeConsole", () => {
  it("browses each inventory under its own heading", () => {
    renderConsole();

    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("REE")).toBeInTheDocument();
    // The workspace root's files show; its folders start shut, because a source
    // checkout's first level would bury the REE section below it.
    expect(screen.getByRole("button", { name: /src/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /main\.py/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /artifacts/ })).toBeInTheDocument();
  });

  it("counts both inventories in the header", () => {
    renderConsole();
    expect(screen.getByText("2 workspace · 2 REE")).toBeInTheDocument();
  });

  it("keeps same-named files in the two inventories separately openable", async () => {
    const user = userEvent.setup();
    renderConsole();

    // Both trees hold a `build.sh`; the ids namespace them, so opening one does
    // not resolve to the other's content and the tabs do not collapse into one.
    const [workspaceBuild, reeBuild] = screen.getAllByRole("button", { name: /build\.sh/ });
    await user.click(workspaceBuild);
    expect(screen.getByText("workspace copy")).toBeInTheDocument();
    expect(screen.getByText("workspace/build.sh")).toBeInTheDocument();

    await user.click(reeBuild);
    expect(screen.getByText("overlay copy")).toBeInTheDocument();
    expect(screen.getByText("overlay/build.sh")).toBeInTheDocument();
    expect(screen.getAllByRole("tab", { name: "build.sh" })).toHaveLength(2);
  });

  it("filters both trees at once, revealing matches inside shut folders", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.type(screen.getByPlaceholderText("Filter files…"), "main");

    expect(screen.getByRole("button", { name: /main\.py/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sbom\.json/ })).not.toBeInTheDocument();
    expect(screen.getByText("No matching REE files")).toBeInTheDocument();
  });

  // The two trees scroll on their own, so a whole source checkout cannot push
  // the REE section off the bottom. Height is what they divide, and only while
  // both have files to put in it.
  it("divides the console between the inventories once both have files", () => {
    const { container } = renderConsole();
    expect(container.querySelectorAll("[data-share]")).toHaveLength(2);
  });

  it("leaves the workspace the whole console while the REE is empty", () => {
    const { container } = renderConsole({ reeFiles: [] });
    expect(container.querySelector("[data-share]")).toBeNull();
  });

  it("says what each inventory is waiting for when it is empty", () => {
    renderConsole({ workspaceFiles: [], reeFiles: [] });

    expect(screen.getByText("Acquire source to materialize the workspace.")).toBeInTheDocument();
    expect(screen.getByText("Run lifecycle steps to populate the REE.")).toBeInTheDocument();
    expect(screen.getByText("REE filesystem")).toBeInTheDocument();
  });
});
