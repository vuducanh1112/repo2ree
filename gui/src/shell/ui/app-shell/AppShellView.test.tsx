import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShellView } from "./AppShellView";

const shell = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("./hooks/useAppShell", () => ({ useAppShell: () => shell.value }));
vi.mock("./providers/AppShellProvider", () => ({
  AppShellProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("./AppShellContent", () => ({ AppShellContent: () => <div>Dock content</div> }));
vi.mock("./canvas/WorkbenchLab", () => ({ WorkbenchLab: () => <div>Workbench</div> }));
vi.mock("./canvas/RunHud", () => ({ RunHud: () => <div>Run HUD</div> }));
vi.mock("./canvas/FocusDock", () => ({
  FocusDock: ({ children, onClose }: { children: React.ReactNode; onClose: () => void }) => (
    <div>
      {children}
      <button type="button" onClick={onClose}>
        Close dock
      </button>
    </div>
  ),
}));
vi.mock("./canvas/SourceHubPanel", () => ({
  SourceHubPanel: ({ onClose }: { onClose: () => void }) => (
    <button type="button" onClick={onClose}>
      Close source
    </button>
  ),
}));
vi.mock("./canvas/SealHubPanel", () => ({
  SealHubPanel: ({ onSeal, onClose }: { onSeal: () => void; onClose: () => void }) => (
    <div>
      <button type="button" onClick={onSeal}>
        Seal
      </button>
      <button type="button" onClick={onClose}>
        Close seal
      </button>
    </div>
  ),
}));
vi.mock("./canvas/CanvasHub", () => ({
  CanvasHub: (props: {
    onNavigate: (page: string, rect?: DOMRect) => void;
    onAddExperiment: () => void;
    onOpenExperimentsOverview: () => void;
    onOpenExperiment: (index: number) => void;
    onOpenRuntime: () => void;
    onFilesConsoleOpenChange: (open: boolean) => void;
  }) => (
    <div>
      <button type="button" onClick={() => props.onNavigate(PAGE.METADATA)}>
        Navigate plain
      </button>
      <button type="button" onClick={() => props.onNavigate(PAGE.BUILD, new DOMRect(1, 2, 3, 4))}>
        Navigate from node
      </button>
      <button type="button" onClick={props.onAddExperiment}>
        Add experiment
      </button>
      <button type="button" onClick={props.onOpenExperimentsOverview}>
        Experiments overview
      </button>
      <button type="button" onClick={() => props.onOpenExperiment(2)}>
        Open experiment
      </button>
      <button type="button" onClick={props.onOpenRuntime}>
        Open runtime
      </button>
      <button type="button" onClick={() => props.onFilesConsoleOpenChange(true)}>
        Files
      </button>
    </div>
  ),
}));
vi.mock("../shared/components/Toast", () => ({
  Toast: ({ message, onClose }: { message: string; onClose: () => void }) => (
    <button type="button" onClick={onClose}>
      {message}
    </button>
  ),
}));

function controller(page: AppShellPage = PAGE.CANVAS, provisioned = true) {
  const commands = {
    setPage: vi.fn(),
    setReeSpec: vi.fn(),
    setFocusedField: vi.fn(),
    setFilesConsoleOpen: vi.fn(),
    onDownloadRee: vi.fn(),
    onSeal: vi.fn(),
    clearToast: vi.fn(),
  };
  shell.value = {
    provisioned,
    workspaceHydration: { status: "ready", error: null },
    retryWorkspaceHydration: vi.fn(),
    reeIntent: {},
    ree: { name: "Example" },
    workspaceRemote: {
      artifactStatus: { sealedAt: undefined },
      workspaceFiles: [],
      sourceRepo: undefined,
    },
    stepRuns: { badges: {} },
    uiChrome: { page, toast: null, locked: false, filesConsoleOpen: false },
    evaluation: {},
    currentReeFiles: [],
    commands,
    sealRunning: false,
    sealLog: null,
  };
  return commands;
}

describe("AppShellView", () => {
  beforeEach(() => controller());

  it("shows the unprovisioned workbench and handles back navigation", () => {
    controller(PAGE.CANVAS, false);
    const onBack = vi.fn();
    render(<AppShellView onBack={onBack} />);

    expect(screen.getByText("Workbench")).toBeInTheDocument();
    expect(screen.queryByText("Run HUD")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /back/ }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("gates a provisioned workspace while its remote definition is loading", () => {
    const onBack = vi.fn();
    shell.value = {
      ...shell.value,
      workspaceHydration: { status: "loading", error: null },
    };
    render(<AppShellView onBack={onBack} />);

    expect(screen.getByRole("status", { name: "Loading workspace" })).toBeInTheDocument();
    expect(screen.queryByText("Run HUD")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download REE" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Return home" }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("shows a retryable load error without rendering editable workspace content", () => {
    const retryWorkspaceHydration = vi.fn();
    shell.value = {
      ...shell.value,
      workspaceHydration: { status: "error", error: new Error("control plane offline") },
      retryWorkspaceHydration,
    };
    render(<AppShellView onBack={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("control plane offline");
    expect(screen.queryByText("Run HUD")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retryWorkspaceHydration).toHaveBeenCalledOnce();
  });

  it("wires every canvas navigation action", () => {
    const commands = controller();
    render(<AppShellView onBack={vi.fn()} />);

    for (const name of [
      "Navigate plain",
      "Navigate from node",
      "Add experiment",
      "Experiments overview",
      "Open experiment",
      "Open runtime",
      "Files",
    ]) {
      fireEvent.click(screen.getByRole("button", { name }));
    }

    expect(commands.setReeSpec).toHaveBeenCalledOnce();
    expect(commands.setFocusedField).toHaveBeenCalledWith(null);
    expect(commands.setFocusedField).toHaveBeenCalledWith("experiments[2].name");
    expect(commands.setPage).toHaveBeenCalledWith(PAGE.METADATA);
    expect(commands.setPage).toHaveBeenCalledWith(PAGE.EXPERIMENTS);
    expect(commands.setPage).toHaveBeenCalledWith(PAGE.BUILD);
    expect(commands.setFilesConsoleOpen).toHaveBeenCalledWith(true);
  });

  it.each([
    [PAGE.METADATA, "Close dock"],
    [PAGE.SOURCE, "Close source"],
    [PAGE.SEAL, "Close seal"],
  ] as const)("closes the %s surface back to the canvas", (page, closeName) => {
    const commands = controller(page);
    render(<AppShellView onBack={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: closeName }));
    expect(commands.setPage).toHaveBeenCalledWith(PAGE.CANVAS);
  });

  it("runs seal and enabled download actions and clears a toast", () => {
    const commands = controller(PAGE.SEAL);
    shell.value = {
      ...shell.value,
      workspaceRemote: { artifactStatus: { sealedAt: "now" }, workspaceFiles: [] },
      uiChrome: { page: PAGE.SEAL, toast: { message: "Saved", type: "info" }, locked: false },
    };
    render(<AppShellView onBack={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Seal" }));
    fireEvent.click(screen.getByRole("button", { name: "Download REE" }));
    fireEvent.click(screen.getByRole("button", { name: "Saved" }));
    expect(commands.onSeal).toHaveBeenCalledOnce();
    expect(commands.onDownloadRee).toHaveBeenCalledOnce();
    expect(commands.clearToast).toHaveBeenCalledOnce();
  });
});
