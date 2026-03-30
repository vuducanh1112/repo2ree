import type {
  ActionStates,
  AppPage,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Ree,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
} from "../types";
import type { ACTION_TYPES } from "./actionTypes";

export type StateUpdater<T> = T | ((previous: T) => T);

export interface ExplorerState {
  ree: Ree;
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  serviceLogs: ServiceLogs;
  serviceParams: ServiceParams;
  toast: ToastState | null;
  page: ExplorerPage;
  focusedField: string | null;
  navCollapsed: boolean;
  virtualFiles: FileTreeNode[];
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
  showReviewerPreview: boolean;
}

export interface AppContextState {
  appPage: AppPage;
  explorer: ExplorerState;
}

export type AppAction =
  | { type: typeof ACTION_TYPES.app.setPage; page: StateUpdater<AppPage> }
  | { type: typeof ACTION_TYPES.explorer.setRee; ree: StateUpdater<Ree> }
  | { type: typeof ACTION_TYPES.explorer.setLocked; locked: StateUpdater<boolean> }
  | { type: typeof ACTION_TYPES.explorer.setRepoMode; repoMode: StateUpdater<"url" | "upload"> }
  | { type: typeof ACTION_TYPES.explorer.setActionStates; actionStates: StateUpdater<ActionStates> }
  | { type: typeof ACTION_TYPES.explorer.setBadges; badges: StateUpdater<Badges> }
  | { type: typeof ACTION_TYPES.explorer.setTimestamps; timestamps: StateUpdater<Timestamps> }
  | { type: typeof ACTION_TYPES.explorer.setServiceLogs; serviceLogs: StateUpdater<ServiceLogs> }
  | {
      type: typeof ACTION_TYPES.explorer.setServiceParams;
      serviceParams: StateUpdater<ServiceParams>;
    }
  | { type: typeof ACTION_TYPES.explorer.setToast; toast: StateUpdater<ToastState | null> }
  | { type: typeof ACTION_TYPES.explorer.setPage; page: StateUpdater<ExplorerPage> }
  | {
      type: typeof ACTION_TYPES.explorer.setFocusedField;
      focusedField: StateUpdater<string | null>;
    }
  | { type: typeof ACTION_TYPES.explorer.setNavCollapsed; navCollapsed: StateUpdater<boolean> }
  | {
      type: typeof ACTION_TYPES.explorer.setVirtualFiles;
      virtualFiles: StateUpdater<FileTreeNode[]>;
    }
  | {
      type: typeof ACTION_TYPES.explorer.setImmutableSourceSnapshotFiles;
      immutableSourceSnapshotFiles: StateUpdater<FileTreeNode[]>;
    }
  | {
      type: typeof ACTION_TYPES.explorer.setImmutableSourceSnapshotArchiveName;
      immutableSourceSnapshotArchiveName: StateUpdater<string>;
    }
  | {
      type: typeof ACTION_TYPES.explorer.setShowReviewerPreview;
      showReviewerPreview: StateUpdater<boolean>;
    }
  | {
      type: typeof ACTION_TYPES.explorer.resetWorkflowOnSourceChange;
      serviceParams: ServiceParams;
    };
