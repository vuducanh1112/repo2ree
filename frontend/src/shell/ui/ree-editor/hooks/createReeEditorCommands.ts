import type React from "react";
import type { ArtifactStatus } from "../../../../core/artifact/ArtifactStatus";
import { planSealArtifactCommands } from "../../../../core/artifact/sealArtifactCommands";
import type { InclusionOpts } from "../../../../core/ree/InclusionOpts";
import type { ReeSpec } from "../../../../core/ree/ReeSpec";
import type { ReeAssemblyOperationParams, SourceUploadCommit } from "../../../../core/ree/ReeTypes";
import type { GenericReeAssemblyParams } from "../../../../core/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../../core/ree-assembly/assemblyTypes";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../../core/workspace/WorkspaceSourceState";
import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
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
} from "../../app-shell/state/actions";
import type { AssemblyRunState } from "../../app-shell/state/assemblyRunState";
import type { AppShellPage } from "../../app-shell/state/pages";
import type { ReeIntentState } from "../../app-shell/state/reeIntent";
import type { ReeSessionState } from "../../app-shell/state/reeSession";
import { type AppShellAction, resolveUpdater, type Updater } from "../../app-shell/state/types";
import type { UiChromeState } from "../../app-shell/state/uiChrome";
import { executeAssemblyCommands } from "../assembly-runs/assemblyActionEffects";
import type { ShowToast } from "../types";

interface CreateReeEditorCommandsArgs {
  reeIntent: ReeIntentState;
  reeSession: ReeSessionState;
  assemblyRun: AssemblyRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
  showToast: ShowToast;
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
  handleDownloadRee: (inclusionOpts: InclusionOpts) => void;
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
  showToast,
  runAction,
  runAssemblyStep,
  cancelAction,
  persistWorkspaceFile,
  handleDownloadRee,
  handleDownloadSourceFiles,
  handleWorkspaceUpload,
  handleRemoveWorkspaceSource,
  downloadWorkspaceFile,
  flushReeIntent,
}: CreateReeEditorCommandsArgs) {
  const resolveNext = <T>(previous: T, value: Updater<T>): T => resolveUpdater(previous, value);

  // Inclusion is a seal-time choice, not authoring state. On seal we record the
  // settled packaging facts into the session (matching the backend's bundle-time
  // `with_packaging`) and build the archive with the same parameters.
  const settledInclusion = (): InclusionOpts => ({
    includeSource: !!reeSession.workspaceSourceState.sourceIncluded,
    includeRuntime: !!reeSession.artifactStatus.runtimeIncluded,
  });

  const handleSeal = (inclusionOpts: InclusionOpts) => {
    dispatch(
      setWorkspaceSourceState((prev) => ({
        ...prev,
        sourceIncluded: inclusionOpts.includeSource,
      })),
    );
    dispatch(
      setArtifactStatus((prev) => ({
        ...prev,
        runtimeIncluded: inclusionOpts.includeRuntime,
      })),
    );
    executeAssemblyCommands(
      planSealArtifactCommands({
        sealedAt: appShellPorts.clock.nowIso(),
        sealHash: `sha256:${appShellPorts.random.hex(64)}`,
      }),
      {
        dispatch,
        persistWorkspaceFile: () => {},
        showToast,
      },
    );
    handleDownloadRee(inclusionOpts);
  };

  // Phase 8: keep generic patch only for UI-chrome and low-risk editor toggles
  // (page/nav/focus/review-preview/repo-mode).
  return {
    setPage: (nextPage: AppShellPage) => dispatch(patch("uiChrome", { page: nextPage })),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(
        patch("uiChrome", {
          navCollapsed: typeof value === "function" ? value(uiChrome.navCollapsed) : value,
        }),
      ),
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
    openReviewPreview: () => dispatch(patch("uiChrome", { showReviewPreview: true })),
    closeReviewPreview: () => dispatch(patch("uiChrome", { showReviewPreview: false })),
    clearToast: () => dispatch(clearToast()),
    onSeal: handleSeal,
    onDownloadRee: () => handleDownloadRee(settledInclusion()),
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
