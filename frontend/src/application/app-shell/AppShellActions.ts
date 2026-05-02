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
import { ACTION_TYPES } from "./AppShellActionTypes";
import type { AppShellPage } from "./AppShellPages";
import type {
  AppShellAction,
  SourceOutcomePayload,
  StateUpdater,
  WorkflowRunCompletionPayload,
  WorkspaceHydrationPayload,
} from "./AppShellTypes";

export const appShellActions = {
  setRee: (ree: StateUpdater<ReeDraftViewModel>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setRee,
    ree,
  }),
  setReeSpec: (reeSpec: StateUpdater<ReeSpec>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setReeSpec,
    reeSpec,
  }),
  setLocked: (locked: StateUpdater<boolean>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setLocked,
    locked,
  }),
  setRepoMode: (repoMode: StateUpdater<"url" | "upload">): AppShellAction => ({
    type: ACTION_TYPES.appShell.setRepoMode,
    repoMode,
  }),
  setWorkspaceSourceState: (
    workspaceSourceState: StateUpdater<WorkspaceSourceState>,
  ): AppShellAction => ({
    type: ACTION_TYPES.appShell.setWorkspaceSourceState,
    workspaceSourceState,
  }),
  setArtifactStatus: (artifactStatus: StateUpdater<ArtifactStatus>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setArtifactStatus,
    artifactStatus,
  }),
  setActionStates: (actionStates: StateUpdater<ActionStates>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setActionStates,
    actionStates,
  }),
  setBadges: (badges: StateUpdater<Badges>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setBadges,
    badges,
  }),
  setTimestamps: (timestamps: StateUpdater<Timestamps>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setTimestamps,
    timestamps,
  }),
  setWorkflowLogs: (workflowLogs: StateUpdater<WorkflowLogs>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setWorkflowLogs,
    workflowLogs,
  }),
  setWorkflowParams: (workflowParams: StateUpdater<WorkflowParams>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setWorkflowParams,
    workflowParams,
  }),
  setEvaluationState: (evaluationState: StateUpdater<EvaluationState>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setEvaluationState,
    evaluationState,
  }),
  setToast: (toast: StateUpdater<ToastState | null>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setToast,
    toast,
  }),
  setPage: (page: StateUpdater<AppShellPage>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setPage,
    page,
  }),
  setFocusedField: (focusedField: StateUpdater<string | null>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setFocusedField,
    focusedField,
  }),
  setNavCollapsed: (navCollapsed: StateUpdater<boolean>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setNavCollapsed,
    navCollapsed,
  }),
  setWorkspaceFiles: (workspaceFiles: StateUpdater<FileTreeNode[]>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setWorkspaceFiles,
    workspaceFiles,
  }),
  setReeArtifactFiles: (reeArtifactFiles: StateUpdater<ReeFile[]>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setReeArtifactFiles,
    reeArtifactFiles,
  }),
  hydrateWorkspace: (workspace: WorkspaceHydrationPayload): AppShellAction => ({
    type: ACTION_TYPES.appShell.hydrateWorkspace,
    workspace,
  }),
  setSourceSnapshotFiles: (sourceSnapshotFiles: StateUpdater<FileTreeNode[]>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setSourceSnapshotFiles,
    sourceSnapshotFiles,
  }),
  setSourceSnapshotArchiveName: (
    sourceSnapshotArchiveName: StateUpdater<string>,
  ): AppShellAction => ({
    type: ACTION_TYPES.appShell.setSourceSnapshotArchiveName,
    sourceSnapshotArchiveName,
  }),
  applySourceOutcome: (outcome: SourceOutcomePayload): AppShellAction => ({
    type: ACTION_TYPES.appShell.applySourceOutcome,
    outcome,
  }),
  setShowReviewPreview: (showReviewPreview: StateUpdater<boolean>): AppShellAction => ({
    type: ACTION_TYPES.appShell.setShowReviewPreview,
    showReviewPreview,
  }),
  completeWorkflowRun: (completion: WorkflowRunCompletionPayload): AppShellAction => ({
    type: ACTION_TYPES.appShell.completeWorkflowRun,
    completion,
  }),
  resetWorkflowOnSourceChange: (workflowParams: WorkflowParams): AppShellAction => ({
    type: ACTION_TYPES.appShell.resetWorkflowOnSourceChange,
    workflowParams,
  }),
};
