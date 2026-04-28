import type React from "react";
import type {
  ActionStates,
  Badges,
  ExplorerPage,
  FileTreeNode,
  LogEntry,
  Ree,
  Service,
  ServiceBadge,
  ServiceParamValue,
  ServiceRequire,
  SourceUploadCommit,
  WorkflowServiceKey,
  WorkflowServiceRunParams,
} from "../../../types";

export interface PageSourceRepoEntryProps {
  ree: Ree;
  locked: boolean;
  repoMode: "url" | "upload";
  badges: Badges;
  actionStates: ActionStates;
  log: LogEntry | null;
  running: boolean;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<Ree>>;
  onRepoModeChange: React.Dispatch<React.SetStateAction<"url" | "upload">>;
  onGoService: (key: ExplorerPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onDownloadSource: (originType: Ree["source_type"], sourceUrl: string) => void;
  onCancelSource: () => void;
  onWorkspaceUpload: (payload: SourceUploadCommit) => void;
  onRemoveWorkspaceSource: () => void;
}

export interface PageMetadataEntryProps {
  ree: Ree;
  locked: boolean;
  badges: Badges;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<Ree>>;
  onLockedChange: React.Dispatch<React.SetStateAction<boolean>>;
  onGoService: (key: ExplorerPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
}

export interface PageHardwareBomProps {
  ree: Ree;
  locked: boolean;
  badges: Badges;
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  ts?: string;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<Ree>>;
  onLockedChange: React.Dispatch<React.SetStateAction<boolean>>;
  onGoService: (key: ExplorerPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onRun: (key: WorkflowServiceKey, params: WorkflowServiceRunParams) => void;
  onCancel?: (key: WorkflowServiceKey) => void;
}

export interface ServicePageProps {
  svc: Service & { key: WorkflowServiceKey };
  ree: Ree;
  badges: Badges;
  virtualFiles: FileTreeNode[];
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  badge: ServiceBadge | null;
  ts: string | undefined;
  onRun: <K extends WorkflowServiceKey>(key: K, params: WorkflowServiceRunParams<K>) => void;
  onCancel?: (key: WorkflowServiceKey) => void;
  onGo: (key: ExplorerPage) => void;
  onGoFields: () => void;
  onReeChange: React.Dispatch<React.SetStateAction<Ree>>;
  onFilesChange: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  onPersistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  missing: ServiceRequire[];
  params: WorkflowServiceRunParams;
  setParam: (key: string, value: ServiceParamValue) => void;
}
