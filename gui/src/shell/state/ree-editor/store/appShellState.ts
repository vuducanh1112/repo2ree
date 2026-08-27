import type { AppShellPage } from "@core/app-shell/pages";
import { normalizeAppShellPage } from "@core/app-shell/pages";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ToastState } from "@core/ree-steps/stepTypes";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import type { ReeIntentState } from "./reeIntent";
import type { StepRunFormState } from "./stepRunState";
import type { UiChromeState } from "./uiChrome";

interface AppShellState {
  repoMode: "url" | "upload";
  stepParams: import("@core/ree/ReeTypes").ReeStepParams;
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  filesConsoleOpen: boolean;
  receiptsConsoleOpen: boolean;
  benchConsoleOpen: boolean;
  logsConsoleOpen: boolean;
}

export interface SourceOutcomePayload {
  runId?: string;
  reeSpecPatch?: Partial<ReeSpec>;
  workspaceSourceStatePatch?: Partial<WorkspaceSourceState>;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export function createAppShellState(params: {
  reeIntent: ReeIntentState;
  stepRuns: StepRunFormState;
  uiChrome: UiChromeState;
}): AppShellState {
  return {
    ...params.reeIntent,
    ...params.stepRuns,
    ...params.uiChrome,
  };
}
export function normalizeUiChromePage(
  candidate: AppShellPage,
  previous: AppShellPage,
): AppShellPage {
  return normalizeAppShellPage(candidate, previous);
}
