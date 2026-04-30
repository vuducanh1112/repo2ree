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
import type { WorkspaceEditorPage } from "./WorkspaceEditorPages";
import type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceEditorState,
  WorkspaceHydrationPayload,
} from "./WorkspaceEditorState";

export type StateUpdater<T> = WorkspaceDraftStateUpdater<T>;

export interface WorkspaceEditorContextState {
  workspaceDraft: WorkspaceDraftState;
  workspaceRemote: WorkspaceRemoteState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
}

export type WorkspaceEditorAction =
  | { type: "workspaceEditor/setRee"; ree: WorkspaceDraftStateUpdater<Ree> }
  | { type: "workspaceEditor/setLocked"; locked: WorkspaceDraftStateUpdater<boolean> }
  | {
      type: "workspaceEditor/setRepoMode";
      repoMode: WorkspaceDraftStateUpdater<"url" | "upload">;
    }
  | {
      type: "workspaceEditor/setActionStates";
      actionStates: WorkflowRunStateUpdater<ActionStates>;
    }
  | { type: "workspaceEditor/setBadges"; badges: WorkflowRunStateUpdater<Badges> }
  | { type: "workspaceEditor/setTimestamps"; timestamps: WorkflowRunStateUpdater<Timestamps> }
  | {
      type: "workspaceEditor/setWorkflowLogs";
      workflowLogs: WorkflowRunStateUpdater<WorkflowLogs>;
    }
  | {
      type: "workspaceEditor/setWorkflowParams";
      workflowParams: WorkflowRunStateUpdater<WorkflowParams>;
    }
  | { type: "workspaceEditor/setToast"; toast: UiChromeStateUpdater<ToastState | null> }
  | {
      type: "workspaceEditor/setPage";
      page: UiChromeStateUpdater<WorkspaceEditorPage>;
    }
  | {
      type: "workspaceEditor/setFocusedField";
      focusedField: UiChromeStateUpdater<string | null>;
    }
  | {
      type: "workspaceEditor/setNavCollapsed";
      navCollapsed: UiChromeStateUpdater<boolean>;
    }
  | {
      type: "workspaceEditor/setWorkspaceFiles";
      workspaceFiles: WorkspaceRemoteStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceEditor/setReeArtifactFiles";
      reeArtifactFiles: WorkspaceRemoteStateUpdater<ReeFile[]>;
    }
  | { type: "workspaceEditor/hydrateWorkspace"; workspace: WorkspaceHydrationPayload }
  | {
      type: "workspaceEditor/setSourceSnapshotFiles";
      sourceSnapshotFiles: WorkspaceRemoteStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceEditor/setSourceSnapshotArchiveName";
      sourceSnapshotArchiveName: WorkspaceRemoteStateUpdater<string>;
    }
  | { type: "workspaceEditor/applySourcePatchOutcome"; outcome: SourceOutcomePayload }
  | {
      type: "workspaceEditor/setShowReviewPreview";
      showReviewPreview: UiChromeStateUpdater<boolean>;
    }
  | { type: "workspaceEditor/completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "workspaceEditor/resetWorkflowOnSourceChange"; workflowParams: WorkflowParams };

export type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceEditorState,
  WorkspaceHydrationPayload,
};
