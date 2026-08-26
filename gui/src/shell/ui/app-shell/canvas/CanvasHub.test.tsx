/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { PAGE } from "@core/app-shell/pages";
import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import { fireEvent, screen } from "@testing-library/react";
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
        nextPage={PAGE.SBOM}
        provisioned
        openPages={[]}
        renderPage={() => null}
        onClosePage={vi.fn()}
        onPositionPage={vi.fn()}
        onSizePage={vi.fn()}
        pageTitle={() => undefined}
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

    // The panel the authoring graph is sending you to is flagged, and says so
    // to a screen reader — but keeps its plain name, which is how the canvas
    // navigation is addressed everywhere else.
    const nextPanel = screen.getByRole("button", { name: "SBOM" });
    expect(nextPanel).toHaveAttribute("data-next", "true");
    expect(nextPanel).toHaveAccessibleDescription("Next step");
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

  it("stands every open page in its own window and focuses the one clicked", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onClosePage = vi.fn();

    renderWithShell(
      <CanvasHub
        page={PAGE.METADATA}
        ree={exampleEditorRee}
        evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }}
        badges={{}}
        provisioned
        openPages={[
          { page: PAGE.METADATA, position: { x: 300, y: 160 } },
          { page: PAGE.HBOM, position: { x: 420, y: 320 } },
        ]}
        renderPage={(page) => <div>body of {page}</div>}
        onClosePage={onClosePage}
        onPositionPage={vi.fn()}
        onSizePage={vi.fn()}
        pageTitle={() => undefined}
        onNavigate={onNavigate}
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

    // Both windows are present at once — the point of the canvas.
    const metadata = screen.getByRole("region", { name: "Metadata" });
    const hardware = screen.getByRole("region", { name: "Hardware" });
    expect(screen.getByText("body of metadata")).toBeVisible();
    expect(screen.getByText("body of hbom")).toBeVisible();

    // The focused one is the page prop; the other is open but behind.
    expect(metadata.parentElement).toHaveAttribute("data-focused");
    expect(hardware.parentElement).not.toHaveAttribute("data-focused");

    // Where the windows land is `layOutWindows`, covered in core: jsdom gives
    // the stage no layout, so every placement here clamps to the same corner.

    await user.click(screen.getByText("body of hbom"));
    expect(onNavigate).toHaveBeenCalledWith(PAGE.HBOM);

    const [closeMetadata] = screen.getAllByRole("button", { name: "Close" });
    await user.click(closeMetadata as HTMLElement);
    expect(onClosePage).toHaveBeenCalledWith(PAGE.METADATA);
  });

  it("moves a window across the canvas when its title bar is dragged", () => {
    const onPositionPage = vi.fn();
    const onSizePage = vi.fn();

    renderWithShell(
      <CanvasHub
        page={PAGE.METADATA}
        ree={exampleEditorRee}
        evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }}
        badges={{}}
        provisioned
        openPages={[{ page: PAGE.METADATA, position: { x: 300, y: 160 } }]}
        renderPage={() => <div>body</div>}
        onClosePage={vi.fn()}
        onPositionPage={onPositionPage}
        onSizePage={onSizePage}
        pageTitle={() => undefined}
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

    // The title content is the natural target users grab. It must move the
    // window even though the pointer event originates on a child of the bar.
    fireEvent.pointerDown(screen.getByText("Authoring", { exact: true }), {
      isPrimary: true,
      button: 0,
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });
    fireEvent.pointerMove(window, {
      isPrimary: true,
      pointerId: 1,
      clientX: 160,
      clientY: 130,
    });

    expect(onPositionPage).toHaveBeenCalledWith(PAGE.METADATA, { x: 360, y: 190 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    const bar = screen.getByRole("region", { name: "Metadata" }).firstElementChild as HTMLElement;
    fireEvent.pointerDown(bar, {
      isPrimary: true,
      button: 0,
      pointerId: 4,
      clientX: 100,
      clientY: 100,
    });
    fireEvent.pointerMove(window, {
      isPrimary: true,
      pointerId: 4,
      clientX: 120,
      clientY: 120,
    });
    expect(onPositionPage).toHaveBeenCalledWith(PAGE.METADATA, { x: 320, y: 180 });
    fireEvent.pointerUp(window, { pointerId: 4 });

    const resize = screen.getByRole("button", { name: "Resize Metadata" });
    fireEvent.pointerDown(resize, {
      isPrimary: true,
      button: 0,
      pointerId: 2,
      clientX: 700,
      clientY: 540,
    });
    fireEvent.pointerMove(window, {
      isPrimary: true,
      pointerId: 2,
      clientX: 760,
      clientY: 580,
    });

    expect(onSizePage).toHaveBeenCalledWith(
      PAGE.METADATA,
      expect.objectContaining({ width: expect.any(Number), height: expect.any(Number) }),
    );

    const resizeCalls = onSizePage.mock.calls.length;
    fireEvent.keyDown(resize, { key: "ArrowRight" });
    fireEvent.keyDown(resize, { key: "ArrowLeft" });
    fireEvent.keyDown(resize, { key: "ArrowDown" });
    fireEvent.keyDown(resize, { key: "ArrowUp" });
    fireEvent.keyDown(resize, { key: "ArrowRight", shiftKey: true });
    fireEvent.keyDown(resize, { key: "Enter" });
    expect(onSizePage).toHaveBeenCalledTimes(resizeCalls + 5);
  });

  it("resizes from the west edge and moves the window origin", () => {
    const onPositionPage = vi.fn();
    const onSizePage = vi.fn();

    renderWithShell(
      <CanvasHub
        page={PAGE.METADATA}
        ree={exampleEditorRee}
        evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }}
        badges={{}}
        provisioned
        openPages={[{ page: PAGE.METADATA, position: { x: 300, y: 160 } }]}
        renderPage={() => <div>body</div>}
        onClosePage={vi.fn()}
        onPositionPage={onPositionPage}
        onSizePage={onSizePage}
        pageTitle={() => undefined}
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

    const region = screen.getByRole("region", { name: "Metadata" });
    const west = region.parentElement?.querySelector<HTMLElement>('[data-resize-edge="w"]');
    expect(west).not.toBeNull();
    fireEvent.pointerDown(west as HTMLElement, {
      isPrimary: true,
      button: 0,
      pointerId: 3,
      clientX: 300,
      clientY: 400,
    });
    fireEvent.pointerMove(window, {
      isPrimary: true,
      pointerId: 3,
      clientX: 340,
      clientY: 400,
    });

    expect(onPositionPage).toHaveBeenCalledWith(PAGE.METADATA, { x: 340, y: 160 });
    expect(onSizePage).toHaveBeenCalledWith(PAGE.METADATA, { width: 660, height: 540 });
  });

  it("does not start a drag from a control in the title bar", () => {
    const onPositionPage = vi.fn();

    renderWithShell(
      <CanvasHub
        page={PAGE.METADATA}
        ree={exampleEditorRee}
        evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }}
        badges={{}}
        provisioned
        openPages={[{ page: PAGE.METADATA, position: { x: 300, y: 160 } }]}
        renderPage={() => <div>body</div>}
        onClosePage={vi.fn()}
        onPositionPage={onPositionPage}
        onSizePage={vi.fn()}
        pageTitle={() => undefined}
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

    const close = screen.getByRole("button", { name: "Close" });
    fireEvent.pointerDown(close, { isPrimary: true, button: 0, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(window, { isPrimary: true, clientX: 160, clientY: 130 });

    expect(onPositionPage).not.toHaveBeenCalled();
  });
});
