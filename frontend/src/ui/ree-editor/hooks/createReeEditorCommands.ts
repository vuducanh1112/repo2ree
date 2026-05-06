import type React from "react";
import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
import type { ArtifactStatus } from "../../../core/artifact/ArtifactStatus";
import { planSealArtifactCommands } from "../../../core/artifact/sealArtifactCommands";
import type { ReeInclusionState } from "../../../core/ree/ReeInclusionState";
import type { ReeSpec } from "../../../core/ree/ReeSpec";
import type { ReeAssemblyOperationParams, SourceUploadCommit } from "../../../core/ree/ReeTypes";
import type { GenericReeAssemblyParams } from "../../../core/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../core/ree-assembly/assemblyTypes";
import type { ReeEditorState } from "../../../core/ree-editor/reeEditorState";
import type { EvaluationState } from "../../../core/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../core/workspace/WorkspaceSourceState";
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
} from "../../../shell/ui/app-shell/state/actions";
import type { AssemblyRunState } from "../../../shell/ui/app-shell/state/assemblyRunState";
import type { AppShellPage } from "../../../shell/ui/app-shell/state/pages";
import type { ReeDraftState } from "../../../shell/ui/app-shell/state/reeDraft";
import {
  type AppShellAction,
  resolveUpdater,
  type Updater,
} from "../../../shell/ui/app-shell/state/types";
import type { UiChromeState } from "../../../shell/ui/app-shell/state/uiChrome";
import { executeAssemblyCommands } from "../assembly-runs/assemblyActionEffects";
import type { ShowToast } from "../types";

interface CreateReeEditorCommandsArgs {
  reeDraft: ReeDraftState;
  reeEditorState: ReeEditorState;
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
  handleDownloadRee: () => void;
  handleDownloadSourceFiles: (
    originType: ReeDraftState["reeSpec"]["source_type"],
    sourceUrl: string,
  ) => Promise<void>;
  handleWorkspaceUpload: (payload: SourceUploadCommit) => void;
  handleRemoveWorkspaceSource: () => void;
  downloadWorkspaceFile: (path: string, suggestedName?: string) => Promise<void>;
}

export function createReeEditorCommands({
  reeDraft,
  reeEditorState,
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
}: CreateReeEditorCommandsArgs) {
  const resolveNext = <T>(previous: T, value: Updater<T>): T => resolveUpdater(previous, value);

  const handleSeal = () => {
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
  };

  // Phase 8: keep generic patch only for UI-chrome and low-risk editor toggles
  // (page/nav/focus/review-preview/repo-mode and composite inclusion mapping).
  return {
    setPage: (nextPage: AppShellPage) => dispatch(patch("uiChrome", { page: nextPage })),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(
        patch("uiChrome", {
          navCollapsed: typeof value === "function" ? value(uiChrome.navCollapsed) : value,
        }),
      ),
    setReeSpec: (value: Updater<ReeSpec>) =>
      dispatch(updateReeSpec(() => resolveNext(reeDraft.reeSpec, value))),
    setWorkspaceSourceState: (value: Updater<WorkspaceSourceState>) =>
      dispatch(setWorkspaceSourceState(() => resolveNext(reeDraft.workspaceSourceState, value))),
    setArtifactStatus: (value: Updater<ArtifactStatus>) =>
      dispatch(setArtifactStatus(() => resolveNext(reeDraft.artifactStatus, value))),
    setEvaluationState: (value: Updater<EvaluationState>) =>
      dispatch(setEvaluationState(() => resolveNext(assemblyRun.evaluationState, value))),
    setInclusionState: (value: Updater<ReeInclusionState>) => {
      const next = resolveNext(reeEditorState.inclusionState, value);
      dispatch(
        setWorkspaceSourceState((prev) => ({
          ...prev,
          sourceAvailable: next.source !== "unavailable",
          sourceIncluded: next.source === "included",
        })),
      );
      dispatch(
        setArtifactStatus((prev) => ({
          ...prev,
          runtimeIncluded: next.runtime === "included",
        })),
      );
    },
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(setLocked(typeof value === "function" ? value(reeDraft.locked) : value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(setRepoMode(typeof value === "function" ? value(reeDraft.repoMode) : value)),
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
  };
}
