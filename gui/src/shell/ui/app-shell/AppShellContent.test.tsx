/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import { createInitialState } from "@shell/ui/app-shell/state/appShellReducer";
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
import type { AppShellPageContainerProps } from "./pages/pageContainers/shared";

vi.mock("@shell/data/runs/queries", async (importOriginal) => {
  const original = await importOriginal<typeof import("@shell/data/runs/queries")>();
  return {
    ...original,
    useReeRunQuery: () => ({ data: undefined }),
    useReeRunLogsQuery: () => ({ data: undefined }),
  };
});

const services = fakeApiServices({
  ree: {
    listScriptTemplates: vi.fn().mockResolvedValue(scriptTemplateCatalog),
    getEvaluateReport: vi.fn().mockResolvedValue({}),
  },
  runs: { listRuns: vi.fn().mockResolvedValue({ runs: [], next_cursor: null }) },
});

function contentProps(page: AppShellPage): AppShellPageContainerProps {
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
    ree: { ...exampleEditorRee, name: "Example REE" },
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
    evaluation: { dependencyLevel: 2, environmentLevel: 2, machineLevel: 1 },
    currentReeFiles: [],
    commands,
    sealRunning: false,
    sealLog: null,
  } as unknown as AppShellPageContainerProps;
}

describe("AppShellContent", () => {
  afterEach(cleanup);

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
    expect(container.querySelector("main")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });
});
