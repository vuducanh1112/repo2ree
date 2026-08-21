/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { createEmptyReeExperiment, createEmptyReeSpec, type ReeSpec } from "@core/ree/ReeSpec";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import {
  createStepPageProps,
  exampleEditorRee,
  exampleWorkspaceFiles,
  scriptTemplateCatalog,
} from "../../../../../tests/support/stepPageFixture";
import { PageBuildRuntime } from "./build-runtime/BuildRuntimePage";
import { PageExperiments } from "./experiments/ExperimentsPage";
import { PageGenerateSbom } from "./generate-sbom/GenerateSbomPage";
import { PageHardwareBom } from "./hardware-bom/HardwareBomPage";
import { PageMetadataEntry } from "./metadata/MetadataPage";
import { PageRepoAnalysis } from "./repo-analysis/RepoAnalysisPage";
import { PageTestActivation } from "./test-activation/ActivationTestPage";

const catalogServices = () =>
  fakeApiServices({
    ree: { listScriptTemplates: vi.fn().mockResolvedValue(scriptTemplateCatalog) },
  });

describe("major step page workflows", () => {
  it("runs a ready build and persists edits to its reserved script", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    const onPersistWorkspaceFile = vi.fn().mockResolvedValue(undefined);
    const onReeSpecChange = vi.fn();
    renderWithShell(
      <PageBuildRuntime
        {...createStepPageProps("build", { onRun, onPersistWorkspaceFile, onReeSpecChange })}
      />,
      { reeId: "ree-1", services: catalogServices() },
    );

    const run = await screen.findByRole("button", { name: "Run build" });
    await waitFor(() => expect(run).toBeEnabled());
    await user.click(run);
    expect(onRun).toHaveBeenCalledWith("build", {});

    fireEvent.change(screen.getByLabelText("Runtime output path"), {
      target: { value: "new-runtime.tar" },
    });
    const updater = onReeSpecChange.mock.calls[0][0];
    expect(updater(createEmptyReeSpec()).runtime).toBe("new-runtime.tar");

    const editor = screen.getByLabelText("Build script");
    await user.clear(editor);
    await user.type(editor, "#!/bin/sh\necho rebuilt");
    await user.click(screen.getByRole("button", { name: /Save build script/ }));
    expect(onPersistWorkspaceFile).toHaveBeenCalledWith(
      undefined,
      "overlay/build.sh",
      expect.stringContaining("rebuilt"),
    );
  });

  it("renders a complete SBOM target, submits generation, and gates cross-check on Evaluate", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    const listRuns = vi.fn().mockResolvedValue({ runs: [], next_cursor: null });
    const getEvaluateReport = vi.fn().mockResolvedValue({});
    renderWithShell(<PageGenerateSbom {...createStepPageProps("sbom", { onRun })} />, {
      reeId: "ree-1",
      services: fakeApiServices({ ree: { getEvaluateReport }, runs: { listRuns } }),
    });

    expect(screen.getByText("SBOM ready")).toBeInTheDocument();
    expect(screen.getByText("CycloneDX")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generate" }));
    expect(onRun).toHaveBeenCalledWith("sbom", {});
    expect(await screen.findByRole("button", { name: "Cross-check" })).toBeDisabled();
    expect(screen.getByText(/Run Evaluate first/)).toBeInTheDocument();
  });

  it("saves activation scripts and runs against the built runtime", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    const onPersistWorkspaceFile = vi.fn().mockResolvedValue(undefined);
    renderWithShell(
      <PageTestActivation
        {...createStepPageProps("activation", { onRun, onPersistWorkspaceFile })}
      />,
      { reeId: "ree-1", services: catalogServices() },
    );

    expect(await screen.findByText("runtime.tar")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run activation" }));
    expect(onRun).toHaveBeenCalledWith("activation", {});
    const verifyEditor = screen.getByLabelText("Activation verify script (optional)");
    await user.clear(verifyEditor);
    await user.type(verifyEditor, "#!/bin/sh\necho verified");
    await user.click(screen.getByRole("button", { name: "Save verify script" }));
    expect(onPersistWorkspaceFile).toHaveBeenCalledWith(
      undefined,
      "overlay/verify.sh",
      expect.stringContaining("verified"),
    );
  });

  it("shows activation prerequisite, failed outcome, timestamp, and cancellation states", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderWithShell(
      <PageTestActivation
        {...createStepPageProps("activation", {
          ree: {
            ...exampleEditorRee,
            spec: {
              ...exampleEditorRee.spec,
              runtime: "",
              activation: createEmptyReeSpec().activation,
            },
          },
          workspaceFiles: [],
          reeFiles: [],
          running: true,
          runDone: true,
          runFailed: true,
          badge: { step: "activation", label: "failed" },
          ts: "2026-01-01T00:00:00Z",
          missing: [{ field: "runtime", label: "Runtime" }],
          onCancel,
        })}
      />,
      { reeId: "ree-1", services: catalogServices() },
    );

    expect(await screen.findByText("Activation pending")).toBeInTheDocument();
    expect(screen.getByText("Runtime")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onCancel).toHaveBeenCalledWith("activation");
  });

  it("declares catalog fallback activation paths when their scripts are first saved", async () => {
    const user = userEvent.setup();
    const onReeSpecChange = vi.fn();
    const onPersistWorkspaceFile = vi.fn().mockResolvedValue(undefined);
    renderWithShell(
      <PageTestActivation
        {...createStepPageProps("activation", {
          ree: {
            ...exampleEditorRee,
            spec: { ...exampleEditorRee.spec, activation: createEmptyReeSpec().activation },
          },
          onReeSpecChange,
          onPersistWorkspaceFile,
        })}
      />,
      { reeId: "ree-1", services: catalogServices() },
    );

    const runEditor = await screen.findByLabelText("Activation run script");
    await waitFor(() => expect(runEditor).toBeEnabled());
    await user.clear(runEditor);
    await user.type(runEditor, "echo activate");
    await user.click(screen.getByRole("button", { name: "Save run script" }));
    const runUpdate = onReeSpecChange.mock.calls[0][0];
    expect(runUpdate(createEmptyReeSpec()).activation.runScript).toBe("overlay/activate.sh");

    const verifyEditor = screen.getByLabelText("Activation verify script (optional)");
    await user.clear(verifyEditor);
    await user.type(verifyEditor, "echo verify");
    await user.click(screen.getByRole("button", { name: "Save verify script" }));
    const verifyUpdate = onReeSpecChange.mock.calls[1][0];
    expect(verifyUpdate(createEmptyReeSpec()).activation.verifyScript).toBe("overlay/verify.sh");
  });

  it("adds hardware rows across categories and invokes profiling", async () => {
    const user = userEvent.setup();
    const onReeSpecChange = vi.fn();
    const onRun = vi.fn();
    renderWithShell(
      <PageHardwareBom
        ree={exampleEditorRee}
        locked={false}
        badges={{}}
        log={null}
        running={false}
        runDone={false}
        focusedField={null}
        onReeSpecChange={onReeSpecChange}
        onLockedChange={vi.fn()}
        onGoPage={vi.fn()}
        onFocusedFieldChange={vi.fn()}
        onRun={onRun}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Add CPU/ }));
    await user.click(screen.getByRole("button", { name: /GPUs/ }));
    await user.click(screen.getByRole("button", { name: /Add GPU/ }));
    await user.click(screen.getByRole("button", { name: /Memory/ }));
    await user.click(screen.getByRole("button", { name: /Add memory/ }));
    await user.click(screen.getByRole("button", { name: /Storage/ }));
    await user.click(screen.getByRole("button", { name: /Add storage/ }));
    await user.click(screen.getByRole("button", { name: /Network/ }));
    await user.click(screen.getByRole("button", { name: /Add network/ }));
    await user.click(screen.getByRole("button", { name: "Profile machine" }));
    expect(onReeSpecChange).toHaveBeenCalledTimes(5);
    expect(onRun).toHaveBeenCalledWith("hbom", {});
  });

  it("shows repository analysis prerequisites and starts Evaluate", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    renderWithShell(<PageRepoAnalysis {...createStepPageProps("evaluate", { onRun })} />, {
      reeId: "ree-1",
      services: fakeApiServices({ ree: { getEvaluateReport: vi.fn().mockResolvedValue({}) } }),
    });
    expect(await screen.findByText(/No Evaluate output yet/)).toBeInTheDocument();
    expect(screen.getByText("requirements.txt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run Evaluate" }));
    expect(onRun).toHaveBeenCalledWith("evaluate", { strict: false });
  });

  it("adds, edits and removes an experiment in a controlled editor", async () => {
    const user = userEvent.setup();
    const onPersistWorkspaceFile = vi.fn().mockResolvedValue(undefined);

    function Harness() {
      const [reeSpec, setReeSpec] = useState<ReeSpec>({
        ...createEmptyReeSpec(),
        experiments: [
          {
            ...createEmptyReeExperiment(),
            name: "hello",
            description: "Runs hello world",
            runScript: "overlay/experiments/hello.sh",
          },
        ],
      });
      return (
        <PageExperiments
          reeId="ree-1"
          reeSpec={reeSpec}
          locked={false}
          badges={{}}
          focusedField={null}
          workspaceFiles={exampleWorkspaceFiles}
          onReeChange={setReeSpec}
          onGoPage={vi.fn()}
          onFocusedFieldChange={vi.fn()}
          onBeforeRun={async () => {}}
          onPersistWorkspaceFile={onPersistWorkspaceFile}
        />
      );
    }

    renderWithShell(<Harness />, {
      reeId: "ree-1",
      services: fakeApiServices({
        ree: { listScriptTemplates: vi.fn().mockResolvedValue(scriptTemplateCatalog) },
      }),
    });
    expect(screen.getByText("1 experiment")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /hello/ }));
    expect(screen.getByText("Runs hello world")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Delete/ }));
    expect(screen.getByText("No experiments yet")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Add experiment" })[0]);
    expect(screen.getAllByRole("textbox")[0]).toHaveValue("");
  });

  it("edits catalog metadata, keywords, and contributor entities", async () => {
    const user = userEvent.setup();
    const onFocusedFieldChange = vi.fn();

    function Harness() {
      const [reeSpec, setReeSpec] = useState<ReeSpec>({
        ...createEmptyReeSpec(),
        name: "Python hello world",
        catalogMetadata: {
          ...createEmptyReeSpec().catalogMetadata,
          version: "1.0.0",
          keywords: ["python"],
          contributors: [
            {
              identifier: "https://orcid.org/0000-0001",
              name: "Ada Example",
              affiliationName: "Example Lab",
              affiliationIdentifier: "https://ror.org/example",
            },
          ],
        },
      });
      return (
        <PageMetadataEntry
          reeSpec={reeSpec}
          locked={false}
          focusedField={null}
          badges={{}}
          onReeChange={setReeSpec}
          onLockedChange={vi.fn()}
          onGoPage={vi.fn()}
          onFocusedFieldChange={onFocusedFieldChange}
        />
      );
    }

    renderWithShell(<Harness />);
    const name = screen.getByPlaceholderText("deepfold-protein-structure-prediction");
    await user.clear(name);
    await user.type(name, "Updated REE");
    expect(onFocusedFieldChange).toHaveBeenCalledWith("name");

    await user.click(screen.getByRole("button", { name: "+ reproducibility" }));
    expect(screen.getByText("reproducibility")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove keyword python" }));
    expect(screen.queryByText("python")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Designate Ada Example as corresponding author" }),
    );
    expect(screen.getByText("Corresponding")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit contributor Ada Example" }));
    const contributorName = screen.getByPlaceholderText("Name");
    await user.clear(contributorName);
    await user.type(contributorName, "Ada Lovelace");
    await user.click(screen.getByRole("button", { name: "Save contributor Ada Example" }));
    expect(screen.getAllByText("Ada Lovelace")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Remove contributor Ada Lovelace" }));
    expect(screen.getByText("No contributors yet.")).toBeInTheDocument();
  });
});
