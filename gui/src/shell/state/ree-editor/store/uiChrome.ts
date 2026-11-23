import type { AppShellPage } from "@core/app-shell/pages";
import { PAGE } from "@core/app-shell/pages";
import type { ToastState } from "@core/ree-steps/stepTypes";

export interface UiChromeState {
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  repoMode: "url" | "upload";
  filesConsoleOpen: boolean;
  receiptsConsoleOpen: boolean;
  benchConsoleOpen: boolean;
  logsConsoleOpen: boolean;
}

export type UiChromeViewState = UiChromeState & { locked: boolean };

export function createInitialUiChromeState(): UiChromeState {
  return {
    toast: null,
    page: PAGE.CANVAS,
    focusedField: null,
    repoMode: "url",
    filesConsoleOpen: false,
    receiptsConsoleOpen: false,
    benchConsoleOpen: false,
    logsConsoleOpen: false,
  };
}
