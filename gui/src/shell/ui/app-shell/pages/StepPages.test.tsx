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
import { PageBuildExperimentEnvironment } from "./build-experiment-environment/BuildExperimentEnvironmentPage";
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
      <PageBuildExperimentEnvironment
        {...createStepPageProps("build_experiment_environment", {
          onRun,
          onPersistWorkspaceFile,
          onReeSpecChange,
        })}
      />,
      { reeId: "ree-1", services: catalogServices() },
    );

    const run = await screen.findByRole("button", { name: "Run build" });
    await waitFor(() => expect(run).toBeEnabled());
    await user.click(run);
    expect(onRun).toHaveBeenCalledWith("build_experiment_environment", {});

    fireEvent.change(screen.getByLabelText("Experiment environment output path"), {
      target: { value: "new-runtime.tar" },
    });
    const updater = onReeSpecChange.mock.calls[0][0];
    expect(updater(createEmptyReeSpec()).experimentEnvironmentPath).toBe("new-runtime.tar");

    const editor = screen.getByLabelText("Build experiment environment script");
    await user.clear(editor);
    await user.type(editor, "#!/bin/sh\necho rebuilt");
    await user.click(screen.getByRole("button", { name: /Save build script/ }));
    expect(onPersistWorkspaceFile).toHaveBeenCalledWith(
      "overlay/build.sh",
      expect.stringContaining("rebuilt"),
    );
  });

  it.each([
    ["fills an empty experiment environment declaration from the generated script", "", 1],
    ["never overwrites an experiment environment path the author declared", "runtime.tar", 0],
  ] as const)("%s", async (_name, declared, expectedCalls) => {
    const user = userEvent.setup();
    const onReeSpecChange = vi.fn();
    const suggestScripts = vi.fn().mockResolvedValue({
      results: [
        {
          target: { kind: "build_experiment_environment" },
          candidates: [
            {
              body: "#!/usr/bin/env sh\n",
              inference_rule: "single-project-root-dockerfile-v1",
              application: "automatic_allowed",
              dependencies: [
                {
                  kind: "experiment_environment_declaration",
                  path: ".repo2ree/artifacts/runtime.tar",
                  digest: "",
                  role: "experiment_environment",
                },
              ],
            },
          ],
        },
      ],
      dags: [],
    });

    renderWithShell(
      <PageBuildExperimentEnvironment
        {...createStepPageProps("build_experiment_environment", {
          ree: {
            ...exampleEditorRee,
            spec: { ...exampleEditorRee.spec, experimentEnvironmentPath: declared },
          },
          onReeSpecChange,
        })}
      />,
      {
        reeId: "ree-1",
        services: fakeApiServices({
          ree: {
            listScriptTemplates: vi.fn().mockResolvedValue(scriptTemplateCatalog),
            suggestScripts,
          },
        }),
      },
    );

    await user.click(await screen.findByRole("button", { name: /Generate from repository/ }));
    await waitFor(() => expect(suggestScripts).toHaveBeenCalled());
    await waitFor(() => expect(onReeSpecChange).toHaveBeenCalledTimes(expectedCalls));
    if (expectedCalls > 0) {
      const updater = onReeSpecChange.mock.calls[0][0];
      expect(updater(createEmptyReeSpec()).experimentEnvironmentPath).toBe(
        ".repo2ree/artifacts/runtime.tar",
      );
    }
  });

  it("renders a complete SBOM target, submits generation, and gates cross-check on Evaluate", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    const listRuns = vi.fn().mockResolvedValue({ runs: [], next_cursor: null });
    const getReproducibilityReport = vi.fn().mockResolvedValue({});
    renderWithShell(<PageGenerateSbom {...createStepPageProps("generate_sbom", { onRun })} />, {
      reeId: "ree-1",
      services: fakeApiServices({ ree: { getReproducibilityReport }, runs: { listRuns } }),
    });

    expect(screen.getByText("SBOM ready")).toBeInTheDocument();
    expect(screen.getByText("CycloneDX")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generate" }));
    expect(onRun).toHaveBeenCalledWith("generate_sbom", {});
    expect(await screen.findByRole("button", { name: "Cross-check" })).toBeDisabled();
    expect(screen.getByText(/Run Evaluate first/)).toBeInTheDocument();
  });

  it("shows the activate script it runs alone, and runs against the built experiment environment", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    renderWithShell(
      <PageTestActivation {...createStepPageProps("activate_experiment_environment", { onRun })} />,
      {
        reeId: "ree-1",
        services: catalogServices(),
      },
    );

    expect(await screen.findByText("runtime.tar")).toBeInTheDocument();
    expect(await screen.findByText("sh overlay/activate.sh true")).toBeInTheDocument();
    expect(screen.getByLabelText("Activate experiment environment script")).toHaveTextContent(
      'exec "$@"',
    );
    expect(screen.queryByRole("button", { name: /Save/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run activation" }));
    expect(onRun).toHaveBeenCalledWith("activate_experiment_environment", {});
  });

  it("shows activation prerequisite, failed outcome, timestamp, and cancellation states", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderWithShell(
      <PageTestActivation
        {...createStepPageProps("activate_experiment_environment", {
          ree: {
            ...exampleEditorRee,
            spec: { ...exampleEditorRee.spec, experimentEnvironmentPath: "" },
          },
          workspaceFiles: [],
          reeFiles: [],
          running: true,
          runDone: true,
          runFailed: true,
          badge: { step: "activate_experiment_environment", label: "failed" },
          ts: "2026-01-01T00:00:00Z",
          missing: [{ field: "experimentEnvironmentPath", label: "Experiment environment" }],
          onCancel,
        })}
      />,
      { reeId: "ree-1", services: catalogServices() },
    );

    expect(await screen.findByText("Activation pending")).toBeInTheDocument();
    expect(screen.getByText("Experiment environment")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onCancel).toHaveBeenCalledWith("activate_experiment_environment");
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
    expect(onRun).toHaveBeenCalledWith("observe_hardware", {});
  });

  it("shows repository analysis prerequisites and starts Evaluate", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    renderWithShell(
      <PageRepoAnalysis {...createStepPageProps("evaluate_reproducibility", { onRun })} />,
      {
        reeId: "ree-1",
        services: fakeApiServices({
          ree: { getReproducibilityReport: vi.fn().mockResolvedValue({}) },
        }),
      },
    );
    expect(await screen.findByText(/No Evaluate output yet/)).toBeInTheDocument();
    expect(screen.getByText("requirements.txt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run Evaluate" }));
    expect(onRun).toHaveBeenCalledWith("evaluate_reproducibility", { strict: false });
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
