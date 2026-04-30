import type { Ree } from "../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeFile,
  Timestamps,
  WorkflowLogs,
  WorkflowParams,
} from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { UiChromeState } from "../ui-chrome/UiChromeState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { WorkflowRunState } from "../workflow-runs/WorkflowRunState";
import type { WorkspaceDraftState } from "../workspace-draft/WorkspaceDraftState";
import type { WorkspaceRemoteState } from "../workspace-remote/WorkspaceRemoteState";
import { normalizeWorkspaceShellPage } from "./WorkspaceShellNavigation";
import type { WorkspaceShellPage } from "./WorkspaceShellPages";

// Transitional compatibility shape while consumers migrate to dedicated slices.
export interface WorkspaceShellState {
  ree: Ree;
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  workflowLogs: WorkflowLogs;
  workflowParams: WorkflowParams;
  toast: ToastState | null;
  page: WorkspaceShellPage;
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
  ree?: Ree;
}

export interface SourceOutcomePayload {
  reePatch: Partial<Ree>;
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
export function createWorkspaceShellState(params: {
  workspaceDraft: WorkspaceDraftState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
  workspaceRemote: WorkspaceRemoteState;
}): WorkspaceShellState {
  return {
    ...params.workspaceDraft,
    ...params.workflowRun,
    ...params.uiChrome,
    ...params.workspaceRemote,
  };
}
export function normalizeUiChromePage(
  candidate: WorkspaceShellPage,
  previous: WorkspaceShellPage,
): WorkspaceShellPage {
  return normalizeWorkspaceShellPage(candidate, previous);
}
