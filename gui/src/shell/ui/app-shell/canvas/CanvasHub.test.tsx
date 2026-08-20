/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { PAGE } from "@core/app-shell/pages";
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import { screen, waitFor } from "@testing-library/react";
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

function services() {
  return fakeApiServices({
    ree: {
      getRee: vi.fn().mockResolvedValue(reeDocument),
      listWorkbenchImages: vi.fn().mockResolvedValue({
        images: [{ id: "python", ref: "bench:python", label: "Python", description: "" }],
        default_id: "python",
      }),
      listAuthorReceipts: vi.fn().mockResolvedValue({ receipts: [] }),
      listReviews: vi.fn().mockResolvedValue({ reviews: [] }),
    },
  });
}

describe("CanvasHub", () => {
  it("navigates lifecycle nodes and operates its ambient consoles", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onFilesConsoleOpenChange = vi.fn();
    renderWithShell(
      <CanvasHub
        page={PAGE.CANVAS}
        ree={{
          ...exampleEditorRee,
          experiments: [
            {
              ...createEmptyReeExperiment(),
              name: "hello",
              runScript: "overlay/experiments/hello.sh",
            },
          ],
        }}
        evaluation={{ dependencyLevel: 2, environmentLevel: 2, machineLevel: 1 }}
        badges={{ build: true, sbom: "succeeded" }}
        provisioned
        dimmed={false}
        onNavigate={onNavigate}
        onAddExperiment={vi.fn()}
        onOpenExperimentsOverview={vi.fn()}
        onOpenExperiment={vi.fn()}
        onOpenRuntime={vi.fn()}
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
        filesConsoleOpen
        onFilesConsoleOpenChange={onFilesConsoleOpenChange}
      />,
      { reeId: "ree-1", services: services() },
    );

    await user.click(screen.getByRole("button", { name: "Build" }));
    expect(onNavigate).toHaveBeenCalledWith(PAGE.BUILD, expect.anything());

    await user.click(screen.getByRole("button", { name: "README.md" }));
    expect(screen.getByRole("region", { name: "Open files" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close README.md" }));

    // The one console browses both inventories, and a workspace file names
    // itself with the `workspace/` prefix the wire format strips.
    await user.click(screen.getByRole("button", { name: "main.py" }));
    expect(screen.getByText("workspace/main.py")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Collapse files" }));
    expect(onFilesConsoleOpenChange).toHaveBeenCalledWith(false);
    await user.click(screen.getByRole("button", { name: "Expand receipts" }));
    expect(await screen.findByText("No author receipts recorded yet.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand workbench console" }));
    expect((await screen.findAllByText("bench:python")).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Expand review controls" }));
    expect(await screen.findByRole("button", { name: "Strongest" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("decomposes the pod and exposes runtime and experiment affordances", async () => {
    const user = userEvent.setup();
    const onAddExperiment = vi.fn();
    const onOpenExperiment = vi.fn();
    const onOpenExperimentsOverview = vi.fn();
    const onOpenRuntime = vi.fn();
    renderWithShell(
      <CanvasHub
        page={PAGE.CANVAS}
        ree={{
          ...exampleEditorRee,
          experiments: [{ ...createEmptyReeExperiment(), name: "hello" }],
        }}
        evaluation={{ dependencyLevel: 1, environmentLevel: 1, machineLevel: 1 }}
        badges={{}}
        provisioned
        dimmed={false}
        onNavigate={vi.fn()}
        onAddExperiment={onAddExperiment}
        onOpenExperimentsOverview={onOpenExperimentsOverview}
        onOpenExperiment={onOpenExperiment}
        onOpenRuntime={onOpenRuntime}
        workspaceFiles={[]}
        reeFiles={[]}
        sourceRepo={undefined}
        filesConsoleOpen={false}
        onFilesConsoleOpenChange={vi.fn()}
      />,
      { reeId: "ree-1", services: services() },
    );
    await user.click(screen.getByRole("button", { name: "Decompose" }));
    await user.click(screen.getByRole("button", { name: "Open build runtime" }));
    await user.click(screen.getByRole("button", { name: "Open experiments" }));
    await user.click(screen.getByRole("button", { name: "hello" }));
    await user.click(screen.getByRole("button", { name: "Add experiment" }));
    expect(onOpenRuntime).toHaveBeenCalledOnce();
    expect(onOpenExperimentsOverview).toHaveBeenCalledOnce();
    expect(onOpenExperiment).toHaveBeenCalledWith(0);
    expect(onAddExperiment).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "Reassemble" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Decompose" })).toBeVisible());
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
        onAddExperiment={vi.fn()}
        onOpenExperimentsOverview={vi.fn()}
        onOpenExperiment={vi.fn()}
        onOpenRuntime={vi.fn()}
        workspaceFiles={[]}
        reeFiles={[]}
        sourceRepo={undefined}
        filesConsoleOpen={false}
        onFilesConsoleOpenChange={vi.fn()}
      />,
      { reeId: "ree-1", services: services() },
    );

    expect(container.querySelector("[data-dimmed]")).toHaveAttribute("inert");
  });
});
