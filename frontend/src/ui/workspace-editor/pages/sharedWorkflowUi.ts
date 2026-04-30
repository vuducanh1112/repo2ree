import type React from "react";
import type {
  AutomationStepDefinition,
  WorkflowBadge,
  WorkflowParamValue,
  WorkflowRequirement,
} from "../../../application/workflow/WorkflowStepTypes";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import type { WorkspaceEditorPage } from "../../../application/workspace-editor/WorkspaceEditorPages";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  LogEntry,
  SourceUploadCommit,
} from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";

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
  onGoWorkflow: (key: WorkspaceEditorPage) => void;
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
  onGoWorkflow: (key: WorkspaceEditorPage) => void;
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
  onGoWorkflow: (key: WorkspaceEditorPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onRun: (key: AutomationStepKey, params: AutomationStepRunParams) => void;
  onCancel?: (key: AutomationStepKey) => void;
}

export interface WorkflowPageProps {
  workflow: AutomationStepDefinition & { key: AutomationStepKey };
  ree: Ree;
  badges: Badges;
  workspaceFiles: FileTreeNode[];
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  badge: WorkflowBadge | null;
  ts: string | undefined;
  onRun: <K extends AutomationStepKey>(key: K, params: AutomationStepRunParams<K>) => void;
  onCancel?: (key: AutomationStepKey) => void;
  onGo: (key: WorkspaceEditorPage) => void;
  onGoFields: () => void;
  onReeChange: React.Dispatch<React.SetStateAction<Ree>>;
  onFilesChange: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  onPersistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  missing: WorkflowRequirement[];
  params: AutomationStepRunParams;
  setParam: (key: string, value: WorkflowParamValue) => void;
}
