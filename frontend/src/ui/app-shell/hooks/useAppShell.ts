import { useMemo } from "react";
import { appShellActions, appShellSelectors } from "../../../application/app-shell";
import type { AppShellPage } from "../../../application/app-shell/AppShellPages";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import { useReeQuery } from "../../../data/ree/queries";
import type { ReeFile, SourceUploadCommit, WorkflowParams } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import { toReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useAppShellContext } from "../providers/AppShellProvider";
import { useWorkspaceWorkflowRuns } from "../workflow-runs/useWorkspaceWorkflowRuns";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeDraft = appShellSelectors.reeDraft(state);
  const workflowRun = appShellSelectors.workflowRun(state);
  const uiChrome = appShellSelectors.uiChrome(state);
  const reeQuery = useReeQuery();

  const { showReviewPreview } = uiChrome;
  const workspaceFiles = reeQuery.data?.files ?? [];
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? [];

  const ree: ReeViewState = useMemo(
    () =>
      toReeViewState({
        reeSpec: reeDraft.reeSpec,
        workspaceSourceState: reeDraft.workspaceSourceState,
        artifactStatus: reeDraft.artifactStatus,
        evaluationState: workflowRun.evaluationState,
      }),
    [
      reeDraft.reeSpec,
      reeDraft.workspaceSourceState,
      reeDraft.artifactStatus,
      workflowRun.evaluationState,
    ],
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

  const commands = {
    setPage: (nextPage: AppShellPage) => dispatch(appShellActions.setPage(nextPage)),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(appShellActions.setNavCollapsed(value)),
    setRee: (value: ReeViewState | ((current: ReeViewState) => ReeViewState)) => {
      // setRee action is removed; dispatch component updates via setReeSpec
      const next = typeof value === "function" ? value(ree) : value;
      dispatch(appShellActions.setReeSpec(next));
    },
    setReeSpec: (
      value:
        | typeof reeDraft.reeSpec
        | ((current: typeof reeDraft.reeSpec) => typeof reeDraft.reeSpec),
    ) => dispatch(appShellActions.setReeSpec(value)),
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(appShellActions.setLocked(value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(appShellActions.setRepoMode(value)),
    setFocusedField: (value: string | null | ((current: string | null) => string | null)) =>
      dispatch(appShellActions.setFocusedField(value)),
    setWorkspaceFiles: (_value: FileTreeNode[] | ((current: FileTreeNode[]) => FileTreeNode[])) => {
      // workspaceFiles now come from React Query; this is a no-op
    },
    setWorkflowParams: (value: WorkflowParams | ((current: WorkflowParams) => WorkflowParams)) =>
      dispatch(appShellActions.setWorkflowParams(value)),
    openReviewPreview: () => dispatch(appShellActions.setShowReviewPreview(true)),
    closeReviewPreview: () => dispatch(appShellActions.setShowReviewPreview(false)),
    clearToast: () => dispatch(appShellActions.setToast(null)),
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
