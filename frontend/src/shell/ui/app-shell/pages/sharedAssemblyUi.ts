import type React from "react";
import type { ArtifactStatus } from "../../../../core/artifact/ArtifactStatus";
import type { ReeInclusionState } from "../../../../core/ree/ReeInclusionState";
import type { ReeSpec } from "../../../../core/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  LogEntry,
  SourceUploadCommit,
} from "../../../../core/ree/ReeTypes";
import type {
  ReeAssemblyBadge,
  ReeAssemblyDefinition,
  ReeAssemblyParamValue,
  ReeAssemblyRequirement,
} from "../../../../core/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../../core/ree-assembly/assemblyTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import type { WorkspaceSourceState } from "../../../../core/workspace/WorkspaceSourceState";
import type { AppShellPage } from "../state/pages";

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
  onGoAssemblyPage: (key: AppShellPage) => void;
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
  onGoAssemblyPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
}

export interface PageExperimentsProps {
  reeId: string;
  reeSpec: ReeSpec;
  locked: boolean;
  badges: Badges;
  focusedField: string | null;
  onReeChange: React.Dispatch<React.SetStateAction<ReeSpec>>;
  onGoAssemblyPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onSnapshotComplete: () => Promise<void>;
  // Persist pending draft edits before an experiment run, so the backend
  // validates against the just-typed command rather than a stale draft.
  onBeforeRun: () => Promise<void>;
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
  onGoAssemblyPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onRun: (key: ReeAssemblyOperationKey, params: ReeAssemblyRunParams) => void;
  onCancel?: (key: ReeAssemblyOperationKey) => void;
}

export interface AssemblyPageProps {
  assemblyStep: ReeAssemblyDefinition & { key: ReeAssemblyOperationKey };
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
  badge: ReeAssemblyBadge | null;
  ts: string | undefined;
  onRun: <K extends ReeAssemblyOperationKey>(key: K, params: ReeAssemblyRunParams<K>) => void;
  onCancel?: (key: ReeAssemblyOperationKey) => void;
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
  missing: ReeAssemblyRequirement[];
  params: ReeAssemblyRunParams;
  setParam: (key: string, value: ReeAssemblyParamValue) => void;
}
