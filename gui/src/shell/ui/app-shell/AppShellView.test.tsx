import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShellView } from "./AppShellView";

const shell = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("./hooks/useAppShell", () => ({ useAppShell: () => shell.value }));
vi.mock("@shell/state/ree-editor/workspace-sync/useWorkspaceNavigationGuard", () => ({
  useWorkspaceNavigationGuard: vi.fn(),
}));
vi.mock("./providers/AppShellProvider", () => ({
  AppShellProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("./AppShellContent", () => ({ AppShellContent: () => <div>Dock content</div> }));
vi.mock("./components/WorkspaceStatusBar", () => ({
  WorkspaceStatusBar: (props: {
    onNavigate: (page: AppShellPage) => void;
    onFilesOpenChange: (open: boolean) => void;
    onReceiptsOpenChange: (open: boolean) => void;
  }) => (
    <div>
      <button type="button" onClick={() => props.onNavigate(PAGE.BUILD)}>
        Status build
      </button>
      <button type="button" onClick={() => props.onFilesOpenChange(true)}>
        Status files
      </button>
      <button type="button" onClick={() => props.onReceiptsOpenChange(true)}>
        Status receipts
      </button>
    </div>
  ),
}));
vi.mock("./canvas/WorkbenchLab", () => ({ WorkbenchLab: () => <div>Workbench</div> }));
vi.mock("./canvas/RunHud", () => ({ RunHud: () => <div>Run HUD</div> }));
vi.mock("./canvas/WorkspaceDrawer", () => ({
  WorkspaceDrawer: ({ children, onClose }: { children: React.ReactNode; onClose: () => void }) => (
    <div>
      {children}
      <button type="button" onClick={onClose}>
        Close drawer
      </button>
    </div>
  ),
}));
vi.mock("./canvas/SourceAcquisitionContent", () => ({
  SourceAcquisitionContent: () => <div>Source acquisition</div>,
}));
vi.mock("./canvas/SealContent", () => ({
  SealContent: ({ onSeal }: { onSeal: () => void }) => (
    <button type="button" onClick={onSeal}>
      Seal
    </button>
  ),
}));
vi.mock("./canvas/CanvasHub", () => ({
  CanvasHub: (props: {
    onNavigate: (page: string, rect?: DOMRect) => void;
    onFilesConsoleOpenChange: (open: boolean) => void;
  }) => (
    <div>
      <button type="button" onClick={() => props.onNavigate(PAGE.METADATA)}>
        Navigate plain
      </button>
      <button type="button" onClick={() => props.onNavigate(PAGE.BUILD, new DOMRect(1, 2, 3, 4))}>
        Navigate from node
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
    setReceiptsConsoleOpen: vi.fn(),
    onDownloadRee: vi.fn(),
    onSeal: vi.fn(),
    clearToast: vi.fn(),
    flushReeIntent: vi.fn().mockResolvedValue(undefined),
  };
  shell.value = {
    model: {
      provisioned,
      reeIntent: {},
      ree: { spec: { name: "Example" } },
      workspaceRemote: {
        artifactStatus: { sealedAt: undefined },
        workspaceFiles: [],
        sourceRepo: undefined,
      },
      stepRuns: { badges: {} },
      evaluation: {},
      currentReeFiles: [],
      authorReceipts: [],
    },
    chrome: {
      page,
      toast: null,
      locked: false,
      filesConsoleOpen: false,
      receiptsConsoleOpen: false,
    },
    sync: {
      workspaceHydration: { status: "ready", error: null },
      retryWorkspaceHydration: vi.fn(),
      reeIntentSyncState: { phase: "clean" },
      isReeIntentDirty: false,
      retryReeIntentSync: vi.fn().mockResolvedValue(undefined),
    },
    commands,
    seal: { running: false, log: null },
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
    expect(screen.getByRole("main")).toContainElement(screen.getByText("Workbench"));
    expect(screen.queryByText("Run HUD")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /back/ }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("gates a provisioned workspace while its remote definition is loading", () => {
    const onBack = vi.fn();
    shell.value = {
      ...shell.value,
      sync: {
        ...(shell.value.sync as object),
        workspaceHydration: { status: "loading", error: null },
      },
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
      sync: {
        ...(shell.value.sync as object),
        workspaceHydration: { status: "error", error: new Error("control plane offline") },
        retryWorkspaceHydration,
      },
    };
    render(<AppShellView onBack={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("control plane offline");
    expect(screen.queryByText("Run HUD")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retryWorkspaceHydration).toHaveBeenCalledOnce();
  });

  it("wires canvas navigation and console actions", () => {
    const commands = controller();
    render(<AppShellView onBack={vi.fn()} />);

    for (const name of [
      "Navigate plain",
      "Navigate from node",
      "Files",
      "Status build",
      "Status files",
      "Status receipts",
    ]) {
      fireEvent.click(screen.getByRole("button", { name }));
    }

    expect(commands.setPage).toHaveBeenCalledWith(PAGE.METADATA);
    expect(commands.setPage).toHaveBeenCalledWith(PAGE.BUILD);
    expect(commands.setFilesConsoleOpen).toHaveBeenCalledWith(true);
    expect(commands.setReceiptsConsoleOpen).toHaveBeenCalledWith(true);
  });

  it.each([
    [PAGE.METADATA, "Close drawer"],
    [PAGE.BUILD, "Close drawer"],
    [PAGE.SOURCE, "Close drawer"],
    [PAGE.SEAL, "Close drawer"],
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
      model: {
        ...(shell.value.model as object),
        workspaceRemote: { artifactStatus: { sealedAt: "now" }, workspaceFiles: [] },
      },
      chrome: {
        page: PAGE.SEAL,
        toast: { message: "Saved", type: "info" },
        locked: false,
        filesConsoleOpen: false,
        receiptsConsoleOpen: false,
      },
    };
    render(<AppShellView onBack={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Seal" }));
    fireEvent.click(screen.getByRole("button", { name: "Download REE" }));
    fireEvent.click(screen.getByRole("button", { name: "Saved" }));
    expect(commands.onSeal).toHaveBeenCalledOnce();
    expect(commands.onDownloadRee).toHaveBeenCalledOnce();
    expect(commands.clearToast).toHaveBeenCalledOnce();
  });

  it("shows persistent save state and retries a failed autosave", () => {
    const retryReeIntentSync = vi.fn().mockResolvedValue(undefined);
    controller();
    shell.value = {
      ...shell.value,
      sync: {
        ...(shell.value.sync as object),
        reeIntentSyncState: { phase: "error", error: new Error("offline") },
        isReeIntentDirty: true,
        retryReeIntentSync,
      },
    };
    render(<AppShellView onBack={vi.fn()} />);

    const retry = screen.getByRole("button", { name: "Save failed · Retry" });
    expect(retry).toHaveAttribute("title", "offline");
    fireEvent.click(retry);
    expect(retryReeIntentSync).toHaveBeenCalledOnce();
  });
});
