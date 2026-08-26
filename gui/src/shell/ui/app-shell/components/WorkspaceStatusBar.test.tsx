import { PAGE } from "@core/app-shell/pages";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { exampleEditorRee } from "../../../../../tests/support/stepPageFixture";
import { useAuthoringWorkflowModel } from "../canvas/AuthoringConsole";
import { WorkspaceStatusBar } from "./WorkspaceStatusBar";

/** The shell owns the authoring model; this stands in for it. */
function StatusBarHarness({
  ree,
  badges,
  ...props
}: { ree: ReeEditorViewModel; badges: Badges } & Omit<
  Parameters<typeof WorkspaceStatusBar>[0],
  "authoring"
>) {
  return <WorkspaceStatusBar authoring={useAuthoringWorkflowModel(ree, badges)} {...props} />;
}

function services() {
  return fakeApiServices({
    ree: {
      listReeSteps: vi.fn().mockResolvedValue({
        steps: [
          { key: "source", order: 1, label: "Source", requires: [], actions: [] },
          { key: "build", order: 2, label: "Build Runtime", requires: ["source"], actions: [] },
          { key: "sbom", order: 3, label: "Generate SBOM", requires: ["evaluate"], actions: [] },
          {
            key: "crosscheck",
            order: 4,
            label: "Cross-check SBOM",
            requires: ["build"],
            actions: [],
          },
        ],
      }),
      listReviews: vi.fn().mockResolvedValue({ reviews: [] }),
    },
  });
}

describe("WorkspaceStatusBar", () => {
  it("keeps authoring navigation and workspace utilities persistently available", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onFilesOpenChange = vi.fn();
    const onReceiptsOpenChange = vi.fn();

    renderWithShell(
      <StatusBarHarness
        page={PAGE.BUILD}
        ree={{
          ...exampleEditorRee,
          source: { ...exampleEditorRee.source, sourceAvailable: true },
          // Source acquired and the runtime built; nothing downstream has run.
          audit: { source: "current", runtime: "current" },
        }}
        badges={{}}
        experiments={[]}
        workspaceFiles={[
          {
            id: "workspace:src",
            name: "src",
            type: "folder",
            children: [{ id: "workspace:main", name: "main.py", type: "file" }],
          },
        ]}
        reeFiles={[{ id: "readme", name: "README.md", type: "file", content: "demo" }]}
        receiptCount={2}
        filesOpen
        receiptsOpen={false}
        onNavigate={onNavigate}
        onFilesOpenChange={onFilesOpenChange}
        onReceiptsOpenChange={onReceiptsOpenChange}
      />,
      { reeId: "ree-1", services: services() },
    );

    expect(screen.getByRole("region", { name: "Workspace status" })).toBeVisible();
    expect(screen.getByText("1 workspace · 1 REE")).toBeVisible();
    expect(screen.getByText("2 recorded")).toBeVisible();
    expect(screen.getByRole("button", { name: /Files/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Receipts/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    await user.click(screen.getByRole("button", { name: /Files/ }));
    await user.click(screen.getByRole("button", { name: /Receipts/ }));
    expect(onFilesOpenChange).toHaveBeenCalledWith(false);
    expect(onReceiptsOpenChange).toHaveBeenCalledWith(true);
    expect(onNavigate).toHaveBeenCalledWith(PAGE.CANVAS);

    // The graph's own next move: ready, lowest order, and flagged as such in
    // the strip so the bar answers "what now" without being read end to end.
    const crossCheck = await screen.findByRole("button", {
      name: /^Open Cross-check SBOM authoring step, ready, next up/,
    });
    expect(crossCheck).toHaveAttribute("data-next", "true");
    expect(screen.getAllByText("next")).toHaveLength(1);
    await user.click(crossCheck);
    expect(onNavigate).toHaveBeenCalledWith(PAGE.SBOM);
    expect(
      screen.getByRole("button", { name: /^Open Source authoring step, complete/ }),
    ).toHaveAttribute("data-status", "complete");
    expect(
      screen.getByRole("button", { name: /^Open Generate SBOM authoring step, blocked/ }),
    ).toHaveAttribute("data-status", "blocked");
    expect(screen.queryByText("independent")).not.toBeInTheDocument();

    const modeToggle = screen.getByRole("button", { name: "Switch to review workflow" });
    expect(modeToggle).toHaveAttribute("aria-pressed", "false");
    await user.click(modeToggle);
    expect(await screen.findByRole("button", { name: "Strongest" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const reviewToggle = screen.getByRole("button", { name: "Switch to authoring workflow" });
    expect(reviewToggle).toHaveAttribute("aria-pressed", "true");
    await user.click(reviewToggle);
    expect(screen.getByRole("navigation", { name: "Authoring workflow" })).toBeVisible();
  });
});
