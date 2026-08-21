import type { AppShellPage } from "@core/app-shell/pages";
import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ReeStepParams, SourceUploadCommit } from "@core/ree/ReeTypes";
import type { ReeStepKey, ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import {
  clearToast,
  patch,
  setArtifactStatus,
  setEvaluationState,
  setFocusedField,
  setLocked,
  setRepoMode,
  setStepParams,
  setWorkspaceSourceState,
  updateReeSpec,
} from "@shell/state/ree-editor/store/actions";
import type { AppShellAction, Updater } from "@shell/state/ree-editor/store/types";
import type React from "react";

interface CreateReeEditorCommandsArgs {
  dispatch: React.Dispatch<AppShellAction>;
  runAction: (key: string, params?: GenericReeStepParams) => Promise<void>;
  runStep: <K extends ReeStepKey>(key: K, params: ReeStepRunParams<K>) => Promise<void>;
  cancelAction: (key: string) => Promise<void>;
  persistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  handleDownloadRee: () => void;
  handleSealRee: (inclusionOpts: InclusionOpts) => Promise<void>;
  handleDownloadSourceFiles: (
    originType: ReeSpec["sourceType"],
    sourceUrl: string,
    revision?: string,
  ) => Promise<void>;
  handleWorkspaceUpload: (payload: SourceUploadCommit) => void;
  handleRemoveWorkspaceSource: () => void;
  downloadWorkspaceFile: (path: string, suggestedName?: string) => Promise<void>;
  flushReeIntent: () => Promise<void>;
}

export interface EditorStateCommands {
  setReeSpec(value: Updater<ReeSpec>): void;
  setWorkspaceSourceState(value: Updater<WorkspaceSourceState>): void;
  setArtifactStatus(value: Updater<ArtifactStatus>): void;
  setEvaluationState(value: Updater<EvaluationState>): void;
  setStepParams(value: Updater<ReeStepParams>): void;
}

export interface EditorChromeCommands {
  setPage(nextPage: AppShellPage): void;
  setLocked(value: Updater<boolean>): void;
  setRepoMode(value: Updater<"url" | "upload">): void;
  setFocusedField(value: Updater<string | null>): void;
  setFilesConsoleOpen(open: boolean): void;
  clearToast(): void;
}

export interface EditorWorkflowCommands {
  onSeal(inclusionOpts: InclusionOpts): void;
  onDownloadRee(): void;
  onDownloadSourceFiles(
    originType: ReeSpec["sourceType"],
    sourceUrl: string,
    revision?: string,
  ): Promise<void>;
  onWorkspaceUpload(payload: SourceUploadCommit): void;
  onRemoveWorkspaceSource(): void;
  onDownloadWorkspaceFile(path: string, suggestedName?: string): Promise<void>;
  onRunAction(key: string, params?: GenericReeStepParams): Promise<void>;
  onCancelAction(key: string): Promise<void>;
  onRunStep<K extends ReeStepKey>(key: K, params: ReeStepRunParams<K>): Promise<void>;
  onPersistWorkspaceFile(
    previousPath: string | undefined,
    path: string,
    content: string,
  ): Promise<void>;
  flushReeIntent(): Promise<void>;
}

export interface ReeEditorCommands
  extends EditorStateCommands,
    EditorChromeCommands,
    EditorWorkflowCommands {}

export function createReeEditorCommands({
  dispatch,
  runAction,
  runStep,
  cancelAction,
  persistWorkspaceFile,
  handleDownloadRee,
  handleSealRee,
  handleDownloadSourceFiles,
  handleWorkspaceUpload,
  handleRemoveWorkspaceSource,
  downloadWorkspaceFile,
  flushReeIntent,
}: CreateReeEditorCommandsArgs): ReeEditorCommands {
  const handleSeal = (inclusionOpts: InclusionOpts) => {
    void handleSealRee(inclusionOpts);
  };

  // Generic patch is reserved for UI-chrome and low-risk editor toggles
  // (page/nav/focus/repo-mode); everything else goes through typed actions.
  return {
    setPage: (nextPage: AppShellPage) => dispatch(patch("uiChrome", { page: nextPage })),
    setReeSpec: (value: Updater<ReeSpec>) => dispatch(updateReeSpec(value)),
    setWorkspaceSourceState: (value: Updater<WorkspaceSourceState>) =>
      dispatch(setWorkspaceSourceState(value)),
    setArtifactStatus: (value: Updater<ArtifactStatus>) => dispatch(setArtifactStatus(value)),
    setEvaluationState: (value: Updater<EvaluationState>) => dispatch(setEvaluationState(value)),
    setLocked: (value: Updater<boolean>) => dispatch(setLocked(value)),
    setRepoMode: (value: Updater<"url" | "upload">) => dispatch(setRepoMode(value)),
    setFocusedField: (value: Updater<string | null>) => dispatch(setFocusedField(value)),
    setStepParams: (value: ReeStepParams | ((current: ReeStepParams) => ReeStepParams)) =>
      dispatch(setStepParams((current) => (typeof value === "function" ? value(current) : value))),
    setFilesConsoleOpen: (open: boolean) => dispatch(patch("uiChrome", { filesConsoleOpen: open })),
    clearToast: () => dispatch(clearToast()),
    onSeal: handleSeal,
    onDownloadRee: handleDownloadRee,
    onDownloadSourceFiles: handleDownloadSourceFiles,
    onWorkspaceUpload: (payload: SourceUploadCommit) => handleWorkspaceUpload(payload),
    onRemoveWorkspaceSource: handleRemoveWorkspaceSource,
    onDownloadWorkspaceFile: downloadWorkspaceFile,
    onRunAction: runAction,
    onCancelAction: cancelAction,
    onRunStep: <K extends ReeStepKey>(key: K, params: ReeStepRunParams<K>) => runStep(key, params),
    onPersistWorkspaceFile: persistWorkspaceFile,
    flushReeIntent,
  };
}
