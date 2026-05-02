import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeDraftViewModel, ReeSpec } from "../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeFile,
  Timestamps,
  WorkflowLogs,
  WorkflowParams,
} from "../../domain/ree/ReeTypes";
import { toReeDraftViewModel } from "../../domain/ree/reeDraftViewModel";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ReeDraftState } from "../ree-draft/ReeDraftState";
import type { UiChromeState } from "../ui-chrome/UiChromeState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { WorkflowRunState } from "../workflow-runs/WorkflowRunState";
import type { WorkspaceRemoteState } from "../workspace-remote/WorkspaceRemoteState";
import { normalizeAppShellPage } from "./AppShellNavigation";
import type { AppShellPage } from "./AppShellPages";

export interface AppShellState {
  /**
   * @deprecated To be deleted in Phase 4 once consumers read from slices and
   * React Query directly instead of the aggregate REE draft view model.
   */
  ree: ReeDraftViewModel;
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  workflowLogs: WorkflowLogs;
  workflowParams: WorkflowParams;
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  navCollapsed: boolean;
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
  showReviewPreview: boolean;
}

export interface WorkspaceHydrationPayload {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  reeSpec?: ReeSpec;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
}

export interface SourceOutcomePayload {
  reeSpecPatch?: Partial<ReeSpec>;
  workspaceSourceState?: WorkspaceSourceState;
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export interface WorkflowRunCompletionPayload {
  key: string;
  workflowLog: WorkflowLogs[string];
  actionState: "done";
  badge: boolean;
  timestamp: string;
}
export function createAppShellState(params: {
  reeDraft: ReeDraftState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
  workspaceRemote: WorkspaceRemoteState;
}): AppShellState {
  const ree = toReeDraftViewModel({
    reeSpec: params.reeDraft.reeSpec,
    workspaceSourceState: params.workspaceRemote.workspaceSourceState,
    artifactStatus: params.workspaceRemote.artifactStatus,
    evaluationState: params.workflowRun.evaluationState,
  });

  return {
    ...params.reeDraft,
    ...params.workflowRun,
    ...params.uiChrome,
    ...params.workspaceRemote,
    ree,
  };
}
export function normalizeUiChromePage(
  candidate: AppShellPage,
  previous: AppShellPage,
): AppShellPage {
  return normalizeAppShellPage(candidate, previous);
}
