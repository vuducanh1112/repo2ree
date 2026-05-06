import type React from "react";
import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
import { planSealArtifactCommands } from "../../../application/artifact/sealArtifactCommands";
import type { GenericReeAssemblyParams } from "../../../application/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../application/ree-assembly/assemblyTypes";
import type { ReeEditorState } from "../../../application/ree-editor/reeEditorState";
import {
  clearToast,
  patch,
  setArtifactStatus,
  setEvaluationState,
  setLocked,
  setWorkflowParams,
  setWorkspaceSourceState,
  updateReeSpec,
} from "../../../application/state/actions";
import type { AppShellPage } from "../../../application/state/pages";
import type { ReeDraftState } from "../../../application/state/reeDraft";
import {
  type AppShellAction,
  resolveUpdater,
  type Updater,
} from "../../../application/state/types";
import type { UiChromeState } from "../../../application/state/uiChrome";
import type { WorkflowRunState } from "../../../application/state/workflowRun";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeInclusionState } from "../../../domain/ree/ReeInclusionState";
import type { ReeSpec } from "../../../domain/ree/ReeSpec";
import type { SourceUploadCommit, WorkflowParams } from "../../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";
import { executeAssemblyCommands } from "../assembly-runs/assemblyActionEffects";
import type { ShowToast } from "../types";

interface CreateReeEditorCommandsArgs {
  reeDraft: ReeDraftState;
  reeEditorState: ReeEditorState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
  showToast: ShowToast;
  runAction: (key: string, params?: GenericReeAssemblyParams) => Promise<void>;
  runAutomationStep: <K extends ReeAssemblyOperationKey>(
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
  workflowRun,
  uiChrome,
  dispatch,
  showToast,
  runAction,
  runAutomationStep,
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
      dispatch(setEvaluationState(() => resolveNext(workflowRun.evaluationState, value))),
    setInclusionState: (value: Updater<ReeInclusionState>) => {
      const next = resolveNext(reeEditorState.inclusionState, value);
      dispatch(
        patch("reeDraft", {
          workspaceSourceState: {
            ...reeDraft.workspaceSourceState,
            sourceAvailable: next.source !== "unavailable",
            sourceIncluded: next.source === "included",
          },
          artifactStatus: {
            ...reeDraft.artifactStatus,
            runtimeIncluded: next.runtime === "included",
          },
        }),
      );
    },
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(setLocked(typeof value === "function" ? value(reeDraft.locked) : value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(
        patch("reeDraft", {
          repoMode: typeof value === "function" ? value(reeDraft.repoMode) : value,
        }),
      ),
    setFocusedField: (value: string | null | ((current: string | null) => string | null)) =>
      dispatch(
        patch("uiChrome", {
          focusedField: typeof value === "function" ? value(uiChrome.focusedField) : value,
        }),
      ),
    setWorkflowParams: (value: WorkflowParams | ((current: WorkflowParams) => WorkflowParams)) =>
      dispatch(
        setWorkflowParams((current) => (typeof value === "function" ? value(current) : value)),
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
    onRunAutomationStep: <K extends ReeAssemblyOperationKey>(
      key: K,
      params: ReeAssemblyRunParams<K>,
    ) => runAutomationStep(key, params),
    onPersistWorkspaceFile: persistWorkspaceFile,
  };
}
