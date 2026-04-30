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
import type { ToastState } from "../workflow/WorkflowStepTypes";
import { ACTION_TYPES } from "./WorkspaceShellActionTypes";
import type { WorkspaceShellPage } from "./WorkspaceShellPages";
import type {
  SourceOutcomePayload,
  StateUpdater,
  WorkflowRunCompletionPayload,
  WorkspaceHydrationPayload,
  WorkspaceShellAction,
} from "./WorkspaceShellTypes";

export const workspaceShellActions = {
  setRee: (ree: StateUpdater<ReeDraftViewModel>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setRee,
    ree,
  }),
  setReeSpec: (reeSpec: StateUpdater<ReeSpec>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setReeSpec,
    reeSpec,
  }),
  setLocked: (locked: StateUpdater<boolean>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setLocked,
    locked,
  }),
  setRepoMode: (repoMode: StateUpdater<"url" | "upload">): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setRepoMode,
    repoMode,
  }),
  setWorkspaceSourceState: (
    workspaceSourceState: StateUpdater<WorkspaceSourceState>,
  ): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setWorkspaceSourceState,
    workspaceSourceState,
  }),
  setArtifactStatus: (artifactStatus: StateUpdater<ArtifactStatus>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setArtifactStatus,
    artifactStatus,
  }),
  setActionStates: (actionStates: StateUpdater<ActionStates>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setActionStates,
    actionStates,
  }),
  setBadges: (badges: StateUpdater<Badges>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setBadges,
    badges,
  }),
  setTimestamps: (timestamps: StateUpdater<Timestamps>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setTimestamps,
    timestamps,
  }),
  setWorkflowLogs: (workflowLogs: StateUpdater<WorkflowLogs>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setWorkflowLogs,
    workflowLogs,
  }),
  setWorkflowParams: (workflowParams: StateUpdater<WorkflowParams>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setWorkflowParams,
    workflowParams,
  }),
  setEvaluationState: (evaluationState: StateUpdater<EvaluationState>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setEvaluationState,
    evaluationState,
  }),
  setToast: (toast: StateUpdater<ToastState | null>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setToast,
    toast,
  }),
  setPage: (page: StateUpdater<WorkspaceShellPage>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setPage,
    page,
  }),
  setFocusedField: (focusedField: StateUpdater<string | null>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setFocusedField,
    focusedField,
  }),
  setNavCollapsed: (navCollapsed: StateUpdater<boolean>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setNavCollapsed,
    navCollapsed,
  }),
  setWorkspaceFiles: (workspaceFiles: StateUpdater<FileTreeNode[]>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setWorkspaceFiles,
    workspaceFiles,
  }),
  setReeArtifactFiles: (reeArtifactFiles: StateUpdater<ReeFile[]>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setReeArtifactFiles,
    reeArtifactFiles,
  }),
  hydrateWorkspace: (workspace: WorkspaceHydrationPayload): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.hydrateWorkspace,
    workspace,
  }),
  setSourceSnapshotFiles: (
    sourceSnapshotFiles: StateUpdater<FileTreeNode[]>,
  ): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setSourceSnapshotFiles,
    sourceSnapshotFiles,
  }),
  setSourceSnapshotArchiveName: (
    sourceSnapshotArchiveName: StateUpdater<string>,
  ): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setSourceSnapshotArchiveName,
    sourceSnapshotArchiveName,
  }),
  applySourceOutcome: (outcome: SourceOutcomePayload): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.applySourceOutcome,
    outcome,
  }),
  setShowReviewPreview: (showReviewPreview: StateUpdater<boolean>): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.setShowReviewPreview,
    showReviewPreview,
  }),
  completeWorkflowRun: (completion: WorkflowRunCompletionPayload): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.completeWorkflowRun,
    completion,
  }),
  resetWorkflowOnSourceChange: (workflowParams: WorkflowParams): WorkspaceShellAction => ({
    type: ACTION_TYPES.workspaceShell.resetWorkflowOnSourceChange,
    workflowParams,
  }),
};
