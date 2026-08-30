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
  focusedField: string | null;
  repoMode: "url" | "upload";
  filesConsoleOpen: boolean;
  receiptsConsoleOpen: boolean;
  benchConsoleOpen: boolean;
  logsConsoleOpen: boolean;
}

/** UI controls plus backend-derived immutability for rendered editor surfaces. */
export type UiChromeViewState = UiChromeState & { locked: boolean };

export function createInitialUiChromeState(): UiChromeState {
  return {
    toast: null,
    // The hub canvas is home. Provisioning lands here (not a docked page); the
    // user picks a node to dive in.
    page: PAGE.CANVAS,
    focusedField: null,
    repoMode: "url",
    filesConsoleOpen: false,
    receiptsConsoleOpen: false,
    benchConsoleOpen: false,
    logsConsoleOpen: false,
  };
}
