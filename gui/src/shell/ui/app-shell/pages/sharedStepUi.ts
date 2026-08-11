import type { AppShellPage } from "@core/app-shell/pages";
import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  LogEntry,
  ReeFile,
  SourceUploadCommit,
} from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { ReeStepKey, ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type {
  ReeStepDefinition,
  ReeStepParamValue,
  ReeStepRequirement,
} from "@core/ree-steps/stepTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import type React from "react";
import type { StepOutcome } from "../components/OutcomeBadge";

export interface SourceAcquisitionPageProps {
  ree: ReeEditorViewModel;
  workspaceSourceState: WorkspaceSourceState;
  sourceRepo: SourceRepoMetadata | undefined;
  locked: boolean;
  repoMode: "url" | "upload";
  badges: Badges;
  actionStates: ActionStates;
  log: LogEntry | null;
  running: boolean;
  focusedField: string | null;
  onWorkspaceSourceStateChange: React.Dispatch<React.SetStateAction<WorkspaceSourceState>>;
  onRepoModeChange: React.Dispatch<React.SetStateAction<"url" | "upload">>;
  onGoPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onDownloadSource: (originType: ReeEditorViewModel["sourceType"], sourceUrl: string) => void;
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
  onGoPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
}

export interface PageExperimentsProps {
  reeId: string;
  reeSpec: ReeSpec;
  locked: boolean;
  badges: Badges;
  focusedField: string | null;
  workspaceFiles: FileTreeNode[];
  onReeChange: React.Dispatch<React.SetStateAction<ReeSpec>>;
  onGoPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  // Persist pending draft edits before an experiment run, so the backend
  // validates against the just-typed script rather than a stale draft.
  onBeforeRun: () => Promise<void>;
  // Each experiment owns a run script stored in the workspace overlay.
  onPersistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
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
  onGoPage: (key: AppShellPage) => void;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onRun: (key: ReeStepKey, params: ReeStepRunParams) => void;
  onCancel?: (key: ReeStepKey) => void;
}

export interface StepPageProps {
  step: ReeStepDefinition & { key: ReeStepKey };
  ree: ReeEditorViewModel;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  badges: Badges;
  workspaceFiles: FileTreeNode[];
  /** The REE's own files (artifacts/, overlay/, …), not the materialized tree. */
  reeFiles: ReeFile[];
  log: LogEntry | null;
  running: boolean;
  runDone: boolean;
  /** The last run finished without succeeding (failed or canceled). */
  runFailed: boolean;
  badge: StepOutcome | null;
  ts: string | undefined;
  onRun: <K extends ReeStepKey>(key: K, params: ReeStepRunParams<K>) => void;
  onCancel?: (key: ReeStepKey) => void;
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
  missing: ReeStepRequirement[];
  params: ReeStepRunParams;
  setParam: (key: string, value: ReeStepParamValue) => void;
}
