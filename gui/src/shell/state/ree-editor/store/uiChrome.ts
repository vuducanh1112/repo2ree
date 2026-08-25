import type { AppShellPage } from "@core/app-shell/pages";
import { PAGE } from "@core/app-shell/pages";
import type { ToastState } from "@core/ree-steps/stepTypes";

export interface UiChromeState {
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  locked: boolean;
  repoMode: "url" | "upload";
  sourceSnapshotArchiveName: string;
  filesConsoleOpen: boolean;
  receiptsConsoleOpen: boolean;
  benchConsoleOpen: boolean;
  logsConsoleOpen: boolean;
}

export function createInitialUiChromeState(): UiChromeState {
  return {
    toast: null,
    // The hub canvas is home. Provisioning lands here (not a docked page); the
    // user picks a node to dive in. Pre-provision the WorkbenchLab is shown
    // regardless, so this only governs where the live editor opens.
    page: PAGE.CANVAS,
    focusedField: null,
    locked: false,
    repoMode: "url",
    sourceSnapshotArchiveName: "",
    filesConsoleOpen: false,
    receiptsConsoleOpen: false,
    benchConsoleOpen: false,
    logsConsoleOpen: false,
  };
}
