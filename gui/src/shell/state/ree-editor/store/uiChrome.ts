import type { OpenPageWindow } from "@core/app-shell/openPages";
import type { AppShellPage } from "@core/app-shell/pages";
import { PAGE } from "@core/app-shell/pages";
import type { ToastState } from "@core/ree-steps/stepTypes";

export interface UiChromeState {
  toast: ToastState | null;
  /**
   * The focused page — the window on top, and the one every "go to this page"
   * command targets. Unchanged in meaning from when only one page could be
   * open, so every reader of it (the node highlight, jump-to-field, the
   * authoring bar) keeps working.
   */
  page: AppShellPage;
  /** Every page with a window on the canvas, oldest first, and where it stands. */
  openPages: OpenPageWindow[];
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
    openPages: [],
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
