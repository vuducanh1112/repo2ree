import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { ActionStates, Badges, Timestamps, WorkflowParams } from "../../domain/ree/ReeTypes";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { AppShellPage } from "./pages";
import { normalizeAppShellPage } from "./pages";
import type { ReeDraftState } from "./reeDraft";
import type { UiChromeState } from "./uiChrome";
import type { WorkflowRunState } from "./workflowRun";

interface AppShellState {
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  workflowParams: WorkflowParams;
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

export interface WorkflowRunCompletionPayload {
  key: string;
  actionState: "done";
  badge: boolean;
  timestamp: string;
}
export function createAppShellState(params: {
  reeDraft: ReeDraftState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
}): AppShellState {
  return {
    ...params.reeDraft,
    ...params.workflowRun,
    ...params.uiChrome,
  };
}
export function normalizeUiChromePage(
  candidate: AppShellPage,
  previous: AppShellPage,
): AppShellPage {
  return normalizeAppShellPage(candidate, previous);
}
