import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeAssemblyOperationParams,
  Timestamps,
} from "../../domain/ree/ReeTypes";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ToastState } from "../ree-assembly/assemblyStepTypes";
import type { AssemblyRunState } from "./assemblyRunState";
import type { AppShellPage } from "./pages";
import { normalizeAppShellPage } from "./pages";
import type { ReeDraftState } from "./reeDraft";
import type { UiChromeState } from "./uiChrome";

interface AppShellState {
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  assemblyOperationParams: ReeAssemblyOperationParams;
  activeRunIds: Record<string, string>;
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  navCollapsed: boolean;
  sourceSnapshotArchiveName: string;
  showReviewPreview: boolean;
}

export interface SourceOutcomePayload {
  reeSpecPatch?: Partial<ReeSpec>;
  workspaceSourceState?: WorkspaceSourceState;
  sourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export interface AssemblyRunCompletionPayload {
  key: string;
  actionState: "done";
  badge: boolean;
  timestamp: string;
}
export function createAppShellState(params: {
  reeDraft: ReeDraftState;
  assemblyRun: AssemblyRunState;
  uiChrome: UiChromeState;
}): AppShellState {
  return {
    ...params.reeDraft,
    ...params.assemblyRun,
    ...params.uiChrome,
  };
}
export function normalizeUiChromePage(
  candidate: AppShellPage,
  previous: AppShellPage,
): AppShellPage {
  return normalizeAppShellPage(candidate, previous);
}
