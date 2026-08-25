/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { PAGE } from "@core/app-shell/pages";
import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { exampleEditorRee } from "../../../../../tests/support/stepPageFixture";
import { CanvasHub } from "./CanvasHub";

const reeDocument = {
  ree_id: "ree-1",
  status: "draft" as const,
  ree: { subject: { definition: { name: "Python hello world" } } },
  audit: {
    source: { evidence: "current", payload: "absent" },
    runtime: { evidence: "current", payload: "absent" },
  },
  workspace_files: [],
  ree_files: [],
  workbench_image: "bench:python",
};

const authorReceipts = parseAuthorReceipts({
  source: {
    operation: "acquire_source",
    run_id: "run-source",
    duration_ms: 1000,
    recorded_at: "2026-01-01T00:00:01Z",
  },
});

function services() {
  return fakeApiServices({
    ree: {
      listReeSteps: vi.fn().mockResolvedValue({
        steps: [
          { key: "source", order: 1, label: "Source", requires: [], actions: [] },
          { key: "build", order: 2, label: "Build Runtime", requires: ["source"], actions: [] },
          {
            key: "crosscheck",
            order: 3,
            label: "Cross-check SBOM",
            requires: ["build"],
            actions: [],
          },
        ],
      }),
      getRee: vi.fn().mockResolvedValue(reeDocument),
      listWorkbenchImages: vi.fn().mockResolvedValue({
        images: [{ id: "python", ref: "bench:python", label: "Python", description: "" }],
        default_id: "python",
      }),
      listReviews: vi.fn().mockResolvedValue({ reviews: [] }),
    },
  });
}

describe("CanvasHub", () => {
  it("navigates lifecycle nodes and operates its ambient consoles", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onFilesConsoleOpenChange = vi.fn();
    const { container } = renderWithShell(
      <CanvasHub
        page={PAGE.CANVAS}
        ree={{
          ...exampleEditorRee,
          spec: {
            ...exampleEditorRee.spec,
            experiments: [
              {
                ...createEmptyReeExperiment(),
                name: "hello",
                runScript: "overlay/experiments/hello.sh",
              },
            ],
          },
        }}
        evaluation={{ dependencyLevel: 2, environmentLevel: 2, machineLevel: 1 }}
        badges={{ build: true, sbom: "succeeded" }}
        provisioned
        dimmed={false}
        onNavigate={onNavigate}
        workspaceFiles={[{ id: "ws:main.py", name: "main.py", type: "file", content: "print()" }]}
        reeFiles={[
          { id: "readme", name: "README.md", type: "file", content: "hello" },
          { id: "sbom", name: "artifacts/sbom.json", type: "file", content: "{}" },
        ]}
        sourceRepo={{
          name: "hello",
          origin: "https://example.test/repo.git",
          acquiredBy: "authoring",
          sourceType: "git",
          swhid: "swh:1:dir:abc",
          sizeBytes: null,
          sizeLabel: null,
        }}
        authorReceipts={authorReceipts}
        filesConsoleOpen
        onFilesConsoleOpenChange={onFilesConsoleOpenChange}
        receiptsConsoleOpen
        onReceiptsConsoleOpenChange={vi.fn()}
        benchConsoleOpen
        onBenchConsoleOpenChange={vi.fn()}
      />,
      { reeId: "ree-1", services: services() },
    );

    await user.click(screen.getByRole("button", { name: "Build" }));
    expect(onNavigate).toHaveBeenCalledWith(PAGE.BUILD, expect.anything());
    expect(screen.queryByRole("button", { name: "Decompose" })).not.toBeInTheDocument();

    const zoomIn = screen.getByTitle("Zoom in");
    const camera = container.querySelector<HTMLElement>('[style*="--world-z"]');
    expect(camera).toHaveStyle("--world-z: 1");
    await user.click(zoomIn);
    expect(camera).toHaveStyle("--world-z: 1.2");
    await user.click(screen.getByTitle("Zoom out"));
    expect(camera).toHaveStyle("--world-z: 1");

    const stage = zoomIn.closest("[data-canvas-hud]")?.parentElement;
    vi.spyOn(stage as HTMLElement, "getBoundingClientRect").mockReturnValue(
      DOMRect.fromRect({ width: 1200, height: 800 }),
    );
    await user.click(screen.getByRole("button", { name: "Fit canvas to viewport" }));
    expect(camera).toHaveAttribute("data-animate");

    await user.click(screen.getByRole("button", { name: "README.md" }));
    expect(screen.getByRole("region", { name: "Open files" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close README.md" }));

    // The one console browses both inventories, and a workspace file names
    // itself with the `workspace/` prefix the wire format strips.
    await user.click(screen.getByRole("button", { name: "main.py" }));
    expect(screen.getByText("workspace/main.py")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Collapse files" }));
    expect(onFilesConsoleOpenChange).toHaveBeenCalledWith(false);
    expect(await screen.findByText("Source acquired")).toBeInTheDocument();
    // The footer bar owns the bench console's resting state, so it is handed to
    // the canvas already open rather than expanded from a collapsed card here.
    expect((await screen.findAllByText("bench:python")).length).toBeGreaterThan(0);
  });

  it("makes the background canvas inert while a focused page is open", () => {
    const { container } = renderWithShell(
      <CanvasHub
        page={PAGE.METADATA}
        ree={exampleEditorRee}
        evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }}
        badges={{}}
        provisioned
        dimmed
        onNavigate={vi.fn()}
        workspaceFiles={[]}
        reeFiles={[]}
        sourceRepo={undefined}
        authorReceipts={[]}
        filesConsoleOpen={false}
        onFilesConsoleOpenChange={vi.fn()}
        receiptsConsoleOpen={false}
        onReceiptsConsoleOpenChange={vi.fn()}
        benchConsoleOpen={false}
        onBenchConsoleOpenChange={vi.fn()}
      />,
      { reeId: "ree-1", services: services() },
    );

    expect(container.querySelector("[data-dimmed]")).toHaveAttribute("inert");
  });
});
