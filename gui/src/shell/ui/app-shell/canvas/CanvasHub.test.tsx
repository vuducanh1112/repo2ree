/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { PAGE } from "@core/app-shell/pages";
import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import {
  exampleEditorRee,
  scriptTemplateCatalog,
} from "../../../../../tests/support/stepPageFixture";
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
  build: {
    operation: "build_runtime",
    run_id: "run-build",
    duration_ms: 2400,
    recorded_at: "2026-01-01T00:01:00Z",
    build_runtime_script_digest: "sha256:build-script",
  },
  experiments: {
    hello: {
      operation: "run_experiment",
      experiment_name: "hello",
      run_id: "run-hello",
      duration_ms: 800,
      recorded_at: "2026-01-01T00:02:00Z",
      run_script_digest: "sha256:hello-script",
    },
  },
});

// One run in flight, so the hub can be checked reporting live work.
const liveBuildRun = {
  run_id: "build-live",
  ree_id: "ree-1",
  operation: "build",
  status: "running",
  created_at: "2026-01-01T00:03:00Z",
  started_at: "2026-01-01T00:03:01Z",
  finished_at: null,
  outputs: {},
  failure: null,
};

function services() {
  return fakeApiServices({
    runs: {
      listRuns: vi.fn().mockResolvedValue({ runs: [liveBuildRun], next_cursor: null }),
    },
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
      listScriptTemplates: vi.fn().mockResolvedValue(scriptTemplateCatalog),
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
        nextPage={PAGE.SBOM}
        provisioned
        onNavigate={onNavigate}
        workspaceFiles={[
          { id: "ws:main.py", name: "main.py", type: "file", content: "print()" },
          {
            id: "ws:overlay",
            name: "overlay",
            type: "folder",
            children: [
              {
                id: "ws:build",
                name: "build.sh",
                type: "file",
                content: "#!/bin/sh\nset -eu\ndocker build .",
              },
              {
                id: "ws:experiments",
                name: "experiments",
                type: "folder",
                children: [
                  {
                    id: "ws:hello",
                    name: "hello.sh",
                    type: "file",
                    content: "python main.py",
                  },
                ],
              },
            ],
          },
        ]}
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

    // The panel the authoring graph is sending you to is flagged, and says so
    // to a screen reader — but keeps its plain name, which is how the canvas
    // navigation is addressed everywhere else.
    const nextPanel = screen.getByRole("button", { name: "SBOM" });
    expect(nextPanel).toHaveAttribute("data-next", "true");
    expect(nextPanel).toHaveAccessibleDescription("Next step");
    expect(screen.queryByRole("button", { name: "Decompose" })).not.toBeInTheDocument();
    expect(screen.getByText("docker build .")).toBeInTheDocument();
    expect(screen.getByText("python main.py")).toBeInTheDocument();
    expect(screen.getAllByText("RECEIPT RECORDED").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("1/1 RECEIPTS")).toBeInTheDocument();

    // A run in flight is reported on its own panel, whoever started it — the
    // listing is the source, not what this tab happens to have kicked off.
    const buildPanel = screen.getByRole("button", { name: "Build" });
    await waitFor(() => expect(buildPanel).toHaveAttribute("data-running", "true"));
    expect(within(buildPanel).getByText("RUNNING")).toBeInTheDocument();
    expect(buildPanel).toHaveAccessibleDescription("Running");
    // Nothing else is running, and a panel with a receipt still reports it.
    expect(screen.getByRole("button", { name: "SBOM" })).not.toHaveAttribute("data-running");

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
});
