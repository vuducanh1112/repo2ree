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
