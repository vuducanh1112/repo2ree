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
import type { WorkspaceShellPage } from "../../../application/workspace-shell/WorkspaceShellPages";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeDraftViewModel, ReeSpec } from "../../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  LogEntry,
  SourceUploadCommit,
} from "../../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";

export interface SourceAcquisitionPageProps {
  ree: ReeDraftViewModel;
  workspaceSourceState: WorkspaceSourceState;
  locked: boolean;
  repoMode: "url" | "upload";
  badges: Badges;
  actionStates: ActionStates;
  log: LogEntry | null;
  running: boolean;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<ReeDraftViewModel>>;
  onRepoModeChange: React.Dispatch<React.SetStateAction<"url" | "upload">>;
  onGoWorkflow: (key: WorkspaceShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onDownloadSource: (originType: ReeDraftViewModel["source_type"], sourceUrl: string) => void;
  onCancelSource: () => void;
  onWorkspaceUpload: (payload: SourceUploadCommit) => void;
  onRemoveWorkspaceSource: () => void;
}

export interface PageMetadataEntryProps {
  reeSpec: ReeSpec;
  locked: boolean;
  badges: Badges;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<ReeSpec>>;
  onLockedChange: React.Dispatch<React.SetStateAction<boolean>>;
  onGoWorkflow: (key: WorkspaceShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
}

export interface PageHardwareBomProps {
  ree: ReeDraftViewModel;
  locked: boolean;
  badges: Badges;
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  ts?: string;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<ReeDraftViewModel>>;
  onLockedChange: React.Dispatch<React.SetStateAction<boolean>>;
  onGoWorkflow: (key: WorkspaceShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onRun: (key: AutomationStepKey, params: AutomationStepRunParams) => void;
  onCancel?: (key: AutomationStepKey) => void;
}

export interface WorkflowPageProps {
  workflow: AutomationStepDefinition & { key: AutomationStepKey };
  ree: ReeDraftViewModel;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  badges: Badges;
  workspaceFiles: FileTreeNode[];
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  badge: WorkflowBadge | null;
  ts: string | undefined;
  onRun: <K extends AutomationStepKey>(key: K, params: AutomationStepRunParams<K>) => void;
  onCancel?: (key: AutomationStepKey) => void;
  onGo: (key: WorkspaceShellPage) => void;
  onGoFields: () => void;
  onReeChange: React.Dispatch<React.SetStateAction<ReeDraftViewModel>>;
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
