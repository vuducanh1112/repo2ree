import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ReeAssemblyOperationParams, SourceUploadCommit } from "@core/ree/ReeTypes";
import type { GenericReeAssemblyParams } from "@core/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "@core/ree-assembly/assemblyTypes";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import {
  clearToast,
  patch,
  setArtifactStatus,
  setAssemblyOperationParams,
  setEvaluationState,
  setLocked,
  setRepoMode,
  setWorkspaceSourceState,
  updateReeSpec,
} from "@shell/ui/app-shell/state/actions";
import type { AssemblyRunState } from "@shell/ui/app-shell/state/assemblyRunState";
import type { AppShellPage } from "@shell/ui/app-shell/state/pages";
import type { ReeIntentState } from "@shell/ui/app-shell/state/reeIntent";
import type { ReeSessionState } from "@shell/ui/app-shell/state/reeSession";
import { type AppShellAction, resolveUpdater, type Updater } from "@shell/ui/app-shell/state/types";
import type { UiChromeState } from "@shell/ui/app-shell/state/uiChrome";
import type React from "react";

interface CreateReeEditorCommandsArgs {
  reeIntent: ReeIntentState;
  reeSession: ReeSessionState;
  assemblyRun: AssemblyRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
  runAction: (key: string, params?: GenericReeAssemblyParams) => Promise<void>;
  runAssemblyStep: <K extends ReeAssemblyOperationKey>(
    key: K,
    params: ReeAssemblyRunParams<K>,
  ) => Promise<void>;
  cancelAction: (key: string) => Promise<void>;
  persistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  handleDownloadRee: () => void;
  handleSealRee: (inclusionOpts: InclusionOpts) => Promise<void>;
  handleDownloadSourceFiles: (
    originType: ReeIntentState["reeSpec"]["source_type"],
    sourceUrl: string,
  ) => Promise<void>;
  handleWorkspaceUpload: (payload: SourceUploadCommit) => void;
  handleRemoveWorkspaceSource: () => void;
  downloadWorkspaceFile: (path: string, suggestedName?: string) => Promise<void>;
  flushReeIntent: () => Promise<void>;
}

export function createReeEditorCommands({
  reeIntent,
  reeSession,
  assemblyRun,
  uiChrome,
  dispatch,
  runAction,
  runAssemblyStep,
  cancelAction,
  persistWorkspaceFile,
  handleDownloadRee,
  handleSealRee,
  handleDownloadSourceFiles,
  handleWorkspaceUpload,
  handleRemoveWorkspaceSource,
  downloadWorkspaceFile,
  flushReeIntent,
}: CreateReeEditorCommandsArgs) {
  const resolveNext = <T>(previous: T, value: Updater<T>): T => resolveUpdater(previous, value);

  const handleSeal = (inclusionOpts: InclusionOpts) => {
    void handleSealRee(inclusionOpts);
  };

  // Phase 8: keep generic patch only for UI-chrome and low-risk editor toggles
  // (page/nav/focus/review-preview/repo-mode).
  return {
    setPage: (nextPage: AppShellPage) => dispatch(patch("uiChrome", { page: nextPage })),
    setReeSpec: (value: Updater<ReeSpec>) =>
      dispatch(updateReeSpec(() => resolveNext(reeIntent.reeSpec, value))),
    setWorkspaceSourceState: (value: Updater<WorkspaceSourceState>) =>
      dispatch(setWorkspaceSourceState(() => resolveNext(reeSession.workspaceSourceState, value))),
    setArtifactStatus: (value: Updater<ArtifactStatus>) =>
      dispatch(setArtifactStatus(() => resolveNext(reeSession.artifactStatus, value))),
    setEvaluationState: (value: Updater<EvaluationState>) =>
      dispatch(setEvaluationState(() => resolveNext(assemblyRun.evaluationState, value))),
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(setLocked(typeof value === "function" ? value(uiChrome.locked) : value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(setRepoMode(typeof value === "function" ? value(uiChrome.repoMode) : value)),
    setFocusedField: (value: string | null | ((current: string | null) => string | null)) =>
      dispatch(
        patch("uiChrome", {
          focusedField: typeof value === "function" ? value(uiChrome.focusedField) : value,
        }),
      ),
    setAssemblyOperationParams: (
      value:
        | ReeAssemblyOperationParams
        | ((current: ReeAssemblyOperationParams) => ReeAssemblyOperationParams),
    ) =>
      dispatch(
        setAssemblyOperationParams((current) =>
          typeof value === "function" ? value(current) : value,
        ),
      ),
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
    onRunAssemblyStep: <K extends ReeAssemblyOperationKey>(
      key: K,
      params: ReeAssemblyRunParams<K>,
    ) => runAssemblyStep(key, params),
    onPersistWorkspaceFile: persistWorkspaceFile,
    flushReeIntent,
  };
}
