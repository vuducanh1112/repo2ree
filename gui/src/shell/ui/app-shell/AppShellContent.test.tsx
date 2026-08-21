/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import { createInitialState } from "@shell/state/ree-editor/store/appShellReducer";
import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../tests/support/renderApp";
import {
  exampleEditorRee,
  exampleWorkspaceFiles,
  scriptTemplateCatalog,
} from "../../../../tests/support/stepPageFixture";
import { AppShellContent } from "./AppShellContent";
import type { AppShellContentProps } from "./pages/pageContainers/controllerContracts";

const runQueries = vi.hoisted(() => ({
  run: vi.fn(() => ({ data: undefined })),
  logs: vi.fn(() => ({ data: undefined })),
}));

vi.mock("@shell/data/runs/queries", async (importOriginal) => {
  const original = await importOriginal<typeof import("@shell/data/runs/queries")>();
  return {
    ...original,
    useReeRunQuery: runQueries.run,
    useReeRunLogsQuery: runQueries.logs,
  };
});

const services = fakeApiServices({
  ree: {
    listScriptTemplates: vi.fn().mockResolvedValue(scriptTemplateCatalog),
    getEvaluateReport: vi.fn().mockResolvedValue({}),
  },
  runs: { listRuns: vi.fn().mockResolvedValue({ runs: [], next_cursor: null }) },
});

function contentProps(page: AppShellPage): AppShellContentProps {
  const reeSpec = {
    ...createEmptyReeSpec(),
    name: "Example REE",
    runtime: "runtime.tar",
  };
  const state = createInitialState({
    reeSpec,
    workspaceSourceState: { sourceAvailable: true, sourceIncluded: true },
    artifactStatus: { runtimeIncluded: true },
  });
  const commands = {
    setReeSpec: vi.fn(),
    setLocked: vi.fn(),
    setPage: vi.fn(),
    setFocusedField: vi.fn(),
    flushReeIntent: vi.fn().mockResolvedValue(undefined),
    onPersistWorkspaceFile: vi.fn().mockResolvedValue(undefined),
    onRunStep: vi.fn(),
    onCancelAction: vi.fn(),
    setArtifactStatus: vi.fn(),
    setWorkspaceSourceState: vi.fn(),
    setEvaluationState: vi.fn(),
    setStepParams: vi.fn(),
    onRunAction: vi.fn(),
  };

  return {
    ree: {
      ...exampleEditorRee,
      spec: { ...exampleEditorRee.spec, name: "Example REE" },
    },
    reeIntent: state.reeIntent,
    workspaceRemote: {
      workspaceFiles: exampleWorkspaceFiles,
      reeArtifactFiles: [],
      workspaceSourceState: { sourceAvailable: true, sourceIncluded: true },
      artifactStatus: { runtimeIncluded: true },
      sourceSnapshotArchiveName: "",
      sourceSnapshotFiles: [],
      sourceRepo: undefined,
    },
    stepRuns: state.stepRuns,
    uiChrome: { ...state.uiChrome, page },
    currentReeFiles: [],
    commands,
  } as unknown as AppShellContentProps;
}

describe("AppShellContent", () => {
  afterEach(() => {
    cleanup();
    runQueries.run.mockClear();
    runQueries.logs.mockClear();
  });

  it("announces a lazy workspace page while its chunk loads", () => {
    renderWithShell(<AppShellContent {...contentProps(PAGE.METADATA)} />, {
      reeId: "ree-1",
      services,
    });

    expect(screen.getByRole("status")).toHaveTextContent("Loading workspace page…");
  });

  it.each([
    [PAGE.METADATA, "Metadata"],
    [PAGE.EXPERIMENTS, "Experiments"],
    [PAGE.HBOM, "Hardware BOM"],
    [PAGE.EVALUATE, "Reproducibility Readiness"],
    [PAGE.BUILD, "Build Runtime"],
    [PAGE.SBOM, "Generate SBOM"],
    [PAGE.ACTIVATION, "Test Activation"],
    [PAGE.ARCHIVE, "Deposit & Share"],
  ] as const)("renders the %s page through its container", async (page, title) => {
    renderWithShell(<AppShellContent {...contentProps(page)} />, {
      reeId: "ree-1",
      services,
    });

    expect(await screen.findByText(title, { exact: true })).toBeInTheDocument();
  });

  it("renders no docked page on the canvas", () => {
    const { container } = renderWithShell(<AppShellContent {...contentProps(PAGE.CANVAS)} />, {
      reeId: "ree-1",
      services,
    });
    expect(container.firstElementChild).toBeInstanceOf(HTMLDivElement);
    expect(container.querySelector("main")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("does not mount inactive page query hooks", () => {
    renderWithShell(<AppShellContent {...contentProps(PAGE.METADATA)} />, {
      reeId: "ree-1",
      services,
    });

    expect(runQueries.run).not.toHaveBeenCalled();
    expect(runQueries.logs).not.toHaveBeenCalled();
  });
});
