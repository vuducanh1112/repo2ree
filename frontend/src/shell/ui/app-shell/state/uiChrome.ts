import type { ToastState } from "@core/ree-assembly/assemblyStepTypes";
import type { AppShellPage } from "./pages";
import { PAGE } from "./pages";

export interface UiChromeState {
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  locked: boolean;
  repoMode: "url" | "upload";
  sourceSnapshotArchiveName: string;
  filesConsoleOpen: boolean;
}

export function createInitialUiChromeState(): UiChromeState {
  return {
    toast: null,
    // The hub canvas is home. Provisioning lands here (not a docked page); the
    // user picks a node to dive in. Pre-provision the WorkbenchLab is shown
    // regardless, so this only governs where the live editor opens.
    page: PAGE.OVERVIEW,
    focusedField: null,
    locked: false,
    repoMode: "url",
    sourceSnapshotArchiveName: "",
    filesConsoleOpen: false,
  };
}
