import type { Ree } from "../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeFile,
  ServiceLogs,
  ServiceParams,
  Timestamps,
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
  setServiceLogs: (serviceLogs: StateUpdater<ServiceLogs>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setServiceLogs,
    serviceLogs,
  }),
  setServiceParams: (serviceParams: StateUpdater<ServiceParams>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setServiceParams,
    serviceParams,
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
  setVirtualFiles: (virtualFiles: StateUpdater<FileTreeNode[]>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setVirtualFiles,
    virtualFiles,
  }),
  setWorkspaceReeFiles: (workspaceReeFiles: StateUpdater<ReeFile[]>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setWorkspaceReeFiles,
    workspaceReeFiles,
  }),
  hydrateWorkspace: (workspace: WorkspaceHydrationPayload): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.hydrateWorkspace,
    workspace,
  }),
  setImmutableSourceSnapshotFiles: (
    immutableSourceSnapshotFiles: StateUpdater<FileTreeNode[]>,
  ): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setImmutableSourceSnapshotFiles,
    immutableSourceSnapshotFiles,
  }),
  setImmutableSourceSnapshotArchiveName: (
    immutableSourceSnapshotArchiveName: StateUpdater<string>,
  ): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setImmutableSourceSnapshotArchiveName,
    immutableSourceSnapshotArchiveName,
  }),
  applySourcePatchOutcome: (outcome: SourceOutcomePayload): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.applySourcePatchOutcome,
    outcome,
  }),
  setShowReviewerPreview: (showReviewerPreview: StateUpdater<boolean>): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.setShowReviewerPreview,
    showReviewerPreview,
  }),
  completeWorkflowRun: (completion: WorkflowRunCompletionPayload): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.completeWorkflowRun,
    completion,
  }),
  resetWorkflowOnSourceChange: (serviceParams: ServiceParams): WorkspaceEditorAction => ({
    type: ACTION_TYPES.workspaceEditor.resetWorkflowOnSourceChange,
    serviceParams,
  }),
};
