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
import type { ToastState } from "../workflow/WorkflowStepTypes";
import { ACTION_TYPES } from "./WorkspaceEditorActionTypes";
import type { WorkspaceEditorPage } from "./WorkspaceEditorPages";
import type {
  SourceOutcomePayload,
  StateUpdater,
  WorkflowRunCompletionPayload,
  WorkspaceEditorAction,
  WorkspaceHydrationPayload,
} from "./WorkspaceEditorTypes";

export const workspaceEditorActions = {
  setRee: (ree: StateUpdater<Ree>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setRee,
    ree,
  }),
  setLocked: (locked: StateUpdater<boolean>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setLocked,
    locked,
  }),
  setRepoMode: (repoMode: StateUpdater<"url" | "upload">): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setRepoMode,
    repoMode,
  }),
  setActionStates: (actionStates: StateUpdater<ActionStates>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setActionStates,
    actionStates,
  }),
  setBadges: (badges: StateUpdater<Badges>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setBadges,
    badges,
  }),
  setTimestamps: (timestamps: StateUpdater<Timestamps>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setTimestamps,
    timestamps,
  }),
  setWorkflowLogs: (workflowLogs: StateUpdater<WorkflowLogs>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setWorkflowLogs,
    workflowLogs,
  }),
  setWorkflowParams: (workflowParams: StateUpdater<WorkflowParams>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setWorkflowParams,
    workflowParams,
  }),
  setToast: (toast: StateUpdater<ToastState | null>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setToast,
    toast,
  }),
  setPage: (page: StateUpdater<WorkspaceEditorPage>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setPage,
    page,
  }),
  setFocusedField: (focusedField: StateUpdater<string | null>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setFocusedField,
    focusedField,
  }),
  setNavCollapsed: (navCollapsed: StateUpdater<boolean>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setNavCollapsed,
    navCollapsed,
  }),
  setWorkspaceFiles: (workspaceFiles: StateUpdater<FileTreeNode[]>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setWorkspaceFiles,
    workspaceFiles,
  }),
  setReeArtifactFiles: (reeArtifactFiles: StateUpdater<ReeFile[]>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setReeArtifactFiles,
    reeArtifactFiles,
  }),
  hydrateWorkspace: (workspace: WorkspaceHydrationPayload): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.hydrateWorkspace,
    workspace,
  }),
  setSourceSnapshotFiles: (
    sourceSnapshotFiles: StateUpdater<FileTreeNode[]>,
  ): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setSourceSnapshotFiles,
    sourceSnapshotFiles,
  }),
  setSourceSnapshotArchiveName: (
    sourceSnapshotArchiveName: StateUpdater<string>,
  ): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setSourceSnapshotArchiveName,
    sourceSnapshotArchiveName,
  }),
  applySourcePatchOutcome: (outcome: SourceOutcomePayload): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.applySourcePatchOutcome,
    outcome,
  }),
  setShowReviewPreview: (showReviewPreview: StateUpdater<boolean>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setShowReviewPreview,
    showReviewPreview,
  }),
  completeWorkflowRun: (completion: WorkflowRunCompletionPayload): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.completeWorkflowRun,
    completion,
  }),
  resetWorkflowOnSourceChange: (workflowParams: WorkflowParams): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.resetWorkflowOnSourceChange,
    workflowParams,
  }),
};
