import type {
  ActionStates,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Ree,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
} from "../types";
import { ACTION_TYPES } from "./actionTypes";
import type { AppAction, StateUpdater } from "./types";

export const explorerActions = {
  setRee: (ree: StateUpdater<Ree>): AppAction => ({ type: ACTION_TYPES.explorer.setRee, ree }),
  setLocked: (locked: StateUpdater<boolean>): AppAction => ({
    type: ACTION_TYPES.explorer.setLocked,
    locked,
  }),
  setRepoMode: (repoMode: StateUpdater<"url" | "upload">): AppAction => ({
    type: ACTION_TYPES.explorer.setRepoMode,
    repoMode,
  }),
  setActionStates: (actionStates: StateUpdater<ActionStates>): AppAction => ({
    type: ACTION_TYPES.explorer.setActionStates,
    actionStates,
  }),
  setBadges: (badges: StateUpdater<Badges>): AppAction => ({
    type: ACTION_TYPES.explorer.setBadges,
    badges,
  }),
  setTimestamps: (timestamps: StateUpdater<Timestamps>): AppAction => ({
    type: ACTION_TYPES.explorer.setTimestamps,
    timestamps,
  }),
  setServiceLogs: (serviceLogs: StateUpdater<ServiceLogs>): AppAction => ({
    type: ACTION_TYPES.explorer.setServiceLogs,
    serviceLogs,
  }),
  setServiceParams: (serviceParams: StateUpdater<ServiceParams>): AppAction => ({
    type: ACTION_TYPES.explorer.setServiceParams,
    serviceParams,
  }),
  setToast: (toast: StateUpdater<ToastState | null>): AppAction => ({
    type: ACTION_TYPES.explorer.setToast,
    toast,
  }),
  setPage: (page: StateUpdater<ExplorerPage>): AppAction => ({
    type: ACTION_TYPES.explorer.setPage,
    page,
  }),
  setFocusedField: (focusedField: StateUpdater<string | null>): AppAction => ({
    type: ACTION_TYPES.explorer.setFocusedField,
    focusedField,
  }),
  setNavCollapsed: (navCollapsed: StateUpdater<boolean>): AppAction => ({
    type: ACTION_TYPES.explorer.setNavCollapsed,
    navCollapsed,
  }),
  setVirtualFiles: (virtualFiles: StateUpdater<FileTreeNode[]>): AppAction => ({
    type: ACTION_TYPES.explorer.setVirtualFiles,
    virtualFiles,
  }),
  setImmutableSourceSnapshotFiles: (
    immutableSourceSnapshotFiles: StateUpdater<FileTreeNode[]>,
  ): AppAction => ({
    type: ACTION_TYPES.explorer.setImmutableSourceSnapshotFiles,
    immutableSourceSnapshotFiles,
  }),
  setImmutableSourceSnapshotArchiveName: (
    immutableSourceSnapshotArchiveName: StateUpdater<string>,
  ): AppAction => ({
    type: ACTION_TYPES.explorer.setImmutableSourceSnapshotArchiveName,
    immutableSourceSnapshotArchiveName,
  }),
  setShowReviewerPreview: (showReviewerPreview: StateUpdater<boolean>): AppAction => ({
    type: ACTION_TYPES.explorer.setShowReviewerPreview,
    showReviewerPreview,
  }),
  resetWorkflowOnSourceChange: (serviceParams: ServiceParams): AppAction => ({
    type: ACTION_TYPES.explorer.resetWorkflowOnSourceChange,
    serviceParams,
  }),
};
