import type React from "react";
import type { FieldMeta } from "../../../constants/fieldMeta";
import type {
  Badges,
  FileTreeNode,
  LogEntry,
  Ree,
  Service,
  ServiceBadge,
  ServiceRequire,
  SourceUploadCommit,
} from "../../../types";

export interface PageSourceRepoEntryProps {
  ree: Ree;
  onChange: (ree: Ree) => void;
  locked: boolean;
  repoMode: string;
  onRepoModeChange: (mode: string) => void;
  onSourceChange: () => void;
  badges: Badges;
  onDownloadSource: (originType: Ree["source_type"]) => void;
  onWorkspaceUpload: (payload: SourceUploadCommit) => void;
  onRemoveWorkspaceSource: () => void;
  downloadRunning: boolean;
  downloadDone: boolean;
  onGoService: (key: string) => void;
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
  ui: ExplorerScreensUi;
}

export interface PageMetadataEntryProps {
  ree: Ree;
  onChange: (ree: Ree) => void;
  locked: boolean;
  setLocked: (locked: boolean) => void;
  badges: Badges;
  onGoService: (key: string) => void;
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
  ui: ExplorerScreensUi;
}

export interface ServicePageProps {
  svc: Service;
  ree: Ree;
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  badge: ServiceBadge | null;
  ts: string | undefined;
  onRun: (key: string, params: Record<string, unknown>) => void;
  onGoFields: () => void;
  badges: Badges;
  onGo: (key: string) => void;
  files: FileTreeNode[];
  onFilesChange?: (files: FileTreeNode[]) => void;
  onReeChange?: (ree: Ree) => void;
  missing: ServiceRequire[];
  params: Record<string, unknown>;
  setParam: (key: string, value: unknown) => void;
  ui: ExplorerScreensUi;
}

// biome-ignore lint/suspicious/noExplicitAny: registry stores components with different prop signatures.
type UiComponent = React.ComponentType<any>;

export interface ExplorerScreensUi {
  WorkflowPageHeader: UiComponent;
  FieldSection: UiComponent;
  FieldRow: UiComponent;
  FieldTipsSidebar: UiComponent;
  NextStepNudge: UiComponent;
  SourceUrlField: UiComponent;
  SourceUploadField: UiComponent;
  RequirementsBanner: UiComponent;
  ServiceActionSection: UiComponent;
  LevelBadge: UiComponent;
  DependencyPanel: UiComponent;
  FilePicker: UiComponent;
  RuntimeField: UiComponent;
  RuntimeOutputNode: UiComponent;
  ScriptPanel: UiComponent;
  LogPanel: UiComponent;
  descToTwoTierTips: (desc: string) => string[];
  findFileByPath: (nodes: FileTreeNode[], pathStr: string) => FileTreeNode | null;
  SVC_SCRIPT_FIELDS: Record<
    string,
    Array<{ label: string; fieldKey: keyof Ree; scriptKind: "build" | "validate" }>
  >;
  FIELD_META: Record<string, FieldMeta>;
  actionBtn: (extra?: React.CSSProperties) => React.CSSProperties;
  inp: (locked?: boolean, extra?: React.CSSProperties) => React.CSSProperties;
  hoverBg: (to: string, from?: string) => Record<string, unknown>;
  hoverBorderColor: (to: string, from?: string) => Record<string, unknown>;
  hoverColor: (to: string, from?: string) => Record<string, unknown>;
}
