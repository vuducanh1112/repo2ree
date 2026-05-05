import { useMemo } from "react";
import {
  createReeEditorStateFromAppShell,
  type ReeEditorState,
} from "../../../application/ree-editor/reeEditorState";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "../../../application/ree-editor/reeEditorViewModel";
import { patch } from "../../../application/state/actions";
import type { AppShellPage } from "../../../application/state/pages";
import { resolveUpdater, type Updater } from "../../../application/state/types";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import { useReeQuery } from "../../../data/ree/queries";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeInclusionState } from "../../../domain/ree/ReeInclusionState";
import type { ReeSpec } from "../../../domain/ree/ReeSpec";
import type { ReeFile, SourceUploadCommit, WorkflowParams } from "../../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";
import { useAppShellContext } from "../providers/AppShellProvider";
import { useWorkspaceWorkflowRuns } from "../workflow-runs/useWorkspaceWorkflowRuns";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeDraft = state.reeDraft;
  const workflowRun = state.workflowRun;
  const uiChrome = state.uiChrome;
  const reeQuery = useReeQuery();

  const { showReviewPreview } = uiChrome;
  const workspaceFiles = reeQuery.data?.files ?? [];
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? [];
  const reeEditorState: ReeEditorState = useMemo(
    () => createReeEditorStateFromAppShell({ reeDraft, workflowRun }),
    [reeDraft, workflowRun],
  );

  const ree: ReeEditorViewModel = useMemo(
    () => createReeEditorViewModel(reeEditorState),
    [reeEditorState],
  );

  const workspaceRemote = useMemo(
    () => ({
      workspaceFiles,
      reeArtifactFiles,
      workspaceSourceState: reeDraft.workspaceSourceState,
      artifactStatus: reeDraft.artifactStatus,
      sourceSnapshotArchiveName: reeDraft.sourceSnapshotArchiveName,
      sourceSnapshotFiles: [] as FileTreeNode[],
    }),
    [
      reeArtifactFiles,
      workspaceFiles,
      reeDraft.workspaceSourceState,
      reeDraft.artifactStatus,
      reeDraft.sourceSnapshotArchiveName,
    ],
  );

  const currentReeFiles = useMemo<ReeFile[]>(() => reeArtifactFiles || [], [reeArtifactFiles]);

  const level = ree.evalLevel ?? 0;
  const {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    downloadWorkspaceFile,
    persistWorkspaceFile,
    runWorkflowStep,
    runAutomationStep,
    cancelAutomationStep,
  } = useWorkspaceWorkflowRuns({
    dispatch,
    ree,
    level,
    workspaceFiles,
  });

  const resolveNext = <T>(previous: T, value: Updater<T>): T => resolveUpdater(previous, value);

  const commands = {
    setPage: (nextPage: AppShellPage) => dispatch(patch("uiChrome", { page: nextPage })),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(
        patch("uiChrome", {
          navCollapsed: typeof value === "function" ? value(uiChrome.navCollapsed) : value,
        }),
      ),
    setReeSpec: (value: Updater<ReeSpec>) =>
      dispatch(
        patch("reeDraft", {
          reeSpec: resolveNext(reeDraft.reeSpec, value),
        }),
      ),
    setWorkspaceSourceState: (value: Updater<WorkspaceSourceState>) =>
      dispatch(
        patch("reeDraft", {
          workspaceSourceState: resolveNext(reeDraft.workspaceSourceState, value),
        }),
      ),
    setArtifactStatus: (value: Updater<ArtifactStatus>) =>
      dispatch(
        patch("reeDraft", {
          artifactStatus: resolveNext(reeDraft.artifactStatus, value),
        }),
      ),
    setEvaluationState: (value: Updater<EvaluationState>) =>
      dispatch(
        patch("workflowRun", {
          evaluationState: resolveNext(workflowRun.evaluationState, value),
        }),
      ),
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
      dispatch(
        patch("reeDraft", {
          locked: typeof value === "function" ? value(reeDraft.locked) : value,
        }),
      ),
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
        patch("workflowRun", {
          workflowParams: typeof value === "function" ? value(workflowRun.workflowParams) : value,
        }),
      ),
    openReviewPreview: () => dispatch(patch("uiChrome", { showReviewPreview: true })),
    closeReviewPreview: () => dispatch(patch("uiChrome", { showReviewPreview: false })),
    clearToast: () => dispatch(patch("uiChrome", { toast: null })),
    onSeal: handleSeal,
    onDownloadRee: handleDownloadRee,
    onDownloadSourceFiles: handleDownloadSourceFiles,
    onWorkspaceUpload: (payload: SourceUploadCommit) => handleWorkspaceUpload(payload),
    onRemoveWorkspaceSource: handleRemoveWorkspaceSource,
    onDownloadWorkspaceFile: downloadWorkspaceFile,
    onRunWorkflowStep: runWorkflowStep,
    onCancelAction: cancelAutomationStep,
    onRunAutomationStep: <K extends AutomationStepKey>(
      key: K,
      params: AutomationStepRunParams<K>,
    ) => runAutomationStep(key, params),
    onPersistWorkspaceFile: persistWorkspaceFile,
  };

  return {
    reeDraft,
    ree,
    workspaceRemote,
    workflowRun,
    uiChrome,
    level,
    currentReeFiles,
    commands,
    reviewer: {
      showReviewPreview,
    },
  };
}
