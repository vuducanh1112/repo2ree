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
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { UiChromeState, UiChromeStateUpdater } from "../ui-chrome/UiChromeState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { WorkflowRunState, WorkflowRunStateUpdater } from "../workflow-runs/WorkflowRunState";
import type {
  WorkspaceDraftState,
  WorkspaceDraftStateUpdater,
} from "../workspace-draft/WorkspaceDraftState";
import type {
  WorkspaceRemoteState,
  WorkspaceRemoteStateUpdater,
} from "../workspace-remote/WorkspaceRemoteState";
import type { WorkspaceShellPage } from "./WorkspaceShellPages";
import type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceHydrationPayload,
  WorkspaceShellState,
} from "./WorkspaceShellState";

export type StateUpdater<T> = WorkspaceDraftStateUpdater<T>;

export interface WorkspaceShellContextState {
  workspaceDraft: WorkspaceDraftState;
  workspaceRemote: WorkspaceRemoteState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
}

export type WorkspaceShellAction =
  | { type: "workspaceShell/setRee"; ree: WorkspaceDraftStateUpdater<ReeDraftViewModel> }
  | { type: "workspaceShell/setReeSpec"; reeSpec: WorkspaceDraftStateUpdater<ReeSpec> }
  | { type: "workspaceShell/setLocked"; locked: WorkspaceDraftStateUpdater<boolean> }
  | {
      type: "workspaceShell/setRepoMode";
      repoMode: WorkspaceDraftStateUpdater<"url" | "upload">;
    }
  | {
      type: "workspaceShell/setWorkspaceSourceState";
      workspaceSourceState: WorkspaceRemoteStateUpdater<WorkspaceSourceState>;
    }
  | {
      type: "workspaceShell/setArtifactStatus";
      artifactStatus: WorkspaceRemoteStateUpdater<ArtifactStatus>;
    }
  | {
      type: "workspaceShell/setActionStates";
      actionStates: WorkflowRunStateUpdater<ActionStates>;
    }
  | { type: "workspaceShell/setBadges"; badges: WorkflowRunStateUpdater<Badges> }
  | { type: "workspaceShell/setTimestamps"; timestamps: WorkflowRunStateUpdater<Timestamps> }
  | {
      type: "workspaceShell/setWorkflowLogs";
      workflowLogs: WorkflowRunStateUpdater<WorkflowLogs>;
    }
  | {
      type: "workspaceShell/setWorkflowParams";
      workflowParams: WorkflowRunStateUpdater<WorkflowParams>;
    }
  | {
      type: "workspaceShell/setEvaluationState";
      evaluationState: WorkflowRunStateUpdater<EvaluationState>;
    }
  | { type: "workspaceShell/setToast"; toast: UiChromeStateUpdater<ToastState | null> }
  | {
      type: "workspaceShell/setPage";
      page: UiChromeStateUpdater<WorkspaceShellPage>;
    }
  | {
      type: "workspaceShell/setFocusedField";
      focusedField: UiChromeStateUpdater<string | null>;
    }
  | {
      type: "workspaceShell/setNavCollapsed";
      navCollapsed: UiChromeStateUpdater<boolean>;
    }
  | {
      type: "workspaceShell/setWorkspaceFiles";
      workspaceFiles: WorkspaceRemoteStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceShell/setReeArtifactFiles";
      reeArtifactFiles: WorkspaceRemoteStateUpdater<ReeFile[]>;
    }
  | { type: "workspaceShell/hydrateWorkspace"; workspace: WorkspaceHydrationPayload }
  | {
      type: "workspaceShell/setSourceSnapshotFiles";
      sourceSnapshotFiles: WorkspaceRemoteStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceShell/setSourceSnapshotArchiveName";
      sourceSnapshotArchiveName: WorkspaceRemoteStateUpdater<string>;
    }
  | { type: "workspaceShell/applySourceOutcome"; outcome: SourceOutcomePayload }
  | {
      type: "workspaceShell/setShowReviewPreview";
      showReviewPreview: UiChromeStateUpdater<boolean>;
    }
  | { type: "workspaceShell/completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "workspaceShell/resetWorkflowOnSourceChange"; workflowParams: WorkflowParams };

export type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceHydrationPayload,
  WorkspaceShellState,
};
