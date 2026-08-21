import type { AppShellPage } from "@core/app-shell/pages";
import { normalizeAppShellPage } from "@core/app-shell/pages";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeStepParams,
  StepRunOutcome,
  Timestamps,
} from "@core/ree/ReeTypes";
import type { ToastState } from "@core/ree-steps/stepTypes";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import type { ReeIntentState } from "./reeIntent";
import type { ReeSessionState } from "./reeSession";
import type { StepRunState } from "./stepRunState";
import type { UiChromeState } from "./uiChrome";

interface AppShellState {
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  stepParams: ReeStepParams;
  activeRunIds: Record<string, string>;
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  sourceSnapshotArchiveName: string;
  filesConsoleOpen: boolean;
}

export interface SourceOutcomePayload {
  runId?: string;
  reeSpecPatch?: Partial<ReeSpec>;
  workspaceSourceStatePatch?: Partial<WorkspaceSourceState>;
  sourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export interface StepRunCompletionPayload {
  key: string;
  runId?: string;
  actionState: "done";
  badge: StepRunOutcome;
  timestamp: string;
}
export function createAppShellState(params: {
  reeIntent: ReeIntentState;
  reeSession: ReeSessionState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
}): AppShellState {
  return {
    ...params.reeIntent,
    ...params.reeSession,
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
