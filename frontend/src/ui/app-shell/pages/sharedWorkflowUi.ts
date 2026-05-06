import type React from "react";
import type { ReeEditorViewModel } from "../../../application/ree-editor/reeEditorViewModel";
import type { AppShellPage } from "../../../application/state/pages";
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
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeInclusionState } from "../../../domain/ree/ReeInclusionState";
import type { ReeSpec } from "../../../domain/ree/ReeSpec";
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
  ree: ReeEditorViewModel;
  inclusionState: ReeInclusionState;
  workspaceSourceState: WorkspaceSourceState;
  locked: boolean;
  repoMode: "url" | "upload";
  badges: Badges;
  actionStates: ActionStates;
  log: LogEntry | null;
  running: boolean;
  focusedField: string | null;
  onWorkspaceSourceStateChange: React.Dispatch<React.SetStateAction<WorkspaceSourceState>>;
  onRepoModeChange: React.Dispatch<React.SetStateAction<"url" | "upload">>;
  onGoWorkflow: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onDownloadSource: (originType: ReeEditorViewModel["source_type"], sourceUrl: string) => void;
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
  onGoWorkflow: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
}

export interface PageHardwareBomProps {
  ree: ReeEditorViewModel;
  locked: boolean;
  badges: Badges;
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  ts?: string;
  focusedField: string | null;
  onReeSpecChange: React.Dispatch<React.SetStateAction<ReeSpec>>;
  onLockedChange: React.Dispatch<React.SetStateAction<boolean>>;
  onGoWorkflow: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onRun: (key: AutomationStepKey, params: AutomationStepRunParams) => void;
  onCancel?: (key: AutomationStepKey) => void;
}

export interface WorkflowPageProps {
  workflow: AutomationStepDefinition & { key: AutomationStepKey };
  ree: ReeEditorViewModel;
  inclusionState: ReeInclusionState;
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
  onGo: (key: AppShellPage) => void;
  onGoFields: () => void;
  onReeSpecChange: React.Dispatch<React.SetStateAction<ReeSpec>>;
  onArtifactStatusChange: React.Dispatch<React.SetStateAction<ArtifactStatus>>;
  onWorkspaceSourceStateChange: React.Dispatch<React.SetStateAction<WorkspaceSourceState>>;
  onEvaluationStateChange: React.Dispatch<React.SetStateAction<EvaluationState>>;
  onPersistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  missing: WorkflowRequirement[];
  params: AutomationStepRunParams;
  setParam: (key: string, value: WorkflowParamValue) => void;
}
