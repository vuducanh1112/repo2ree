import type {
  ActionStates,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Ree,
  ReeFile,
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
  workspaceReeFiles: ReeFile[];
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
  showReviewerPreview: boolean;
}

export interface AppContextState {
  explorer: ExplorerState;
}

export interface WorkspaceHydrationPayload {
  virtualFiles: FileTreeNode[];
  workspaceReeFiles: ReeFile[];
  ree?: Ree;
}

export interface SourceOutcomePayload {
  ree: Ree;
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export interface ServiceRunCompletionPayload {
  key: string;
  serviceLog: ServiceLogs[string];
  actionState: "done";
  badge: boolean;
  timestamp: string;
}

export type AppAction =
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
      type: typeof ACTION_TYPES.explorer.setWorkspaceReeFiles;
      workspaceReeFiles: StateUpdater<ReeFile[]>;
    }
  | {
      type: typeof ACTION_TYPES.explorer.hydrateWorkspace;
      workspace: WorkspaceHydrationPayload;
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
      type: typeof ACTION_TYPES.explorer.applySourceOutcome;
      outcome: SourceOutcomePayload;
    }
  | {
      type: typeof ACTION_TYPES.explorer.setShowReviewerPreview;
      showReviewerPreview: StateUpdater<boolean>;
    }
  | {
      type: typeof ACTION_TYPES.explorer.completeServiceRun;
      completion: ServiceRunCompletionPayload;
    }
  | {
      type: typeof ACTION_TYPES.explorer.resetWorkflowOnSourceChange;
      serviceParams: ServiceParams;
    };
