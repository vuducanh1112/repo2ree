import { useMemo } from "react";
import { appShellActions, appShellSelectors } from "../../../application/app-shell";
import type { AppShellPage } from "../../../application/app-shell/AppShellPages";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import { useReeQuery } from "../../../data/ree/queries";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";
import type { ReeFile, SourceUploadCommit, WorkflowParams } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useAppShellContext } from "../providers/AppShellProvider";
import { useWorkspaceWorkflowRuns } from "../workflow-runs/useWorkspaceWorkflowRuns";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeDraft = appShellSelectors.reeDraft(state);
  const workspaceRemote = appShellSelectors.workspaceRemote(state);
  const workflowRun = appShellSelectors.workflowRun(state);
  const uiChrome = appShellSelectors.uiChrome(state);
  const ree = appShellSelectors.reeDraftViewModel(state);
  const reeQuery = useReeQuery();

  const { showReviewPreview } = uiChrome;
  const workspaceFiles = reeQuery.data?.files ?? workspaceRemote.workspaceFiles;
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? workspaceRemote.reeArtifactFiles;
  const resolvedWorkspaceRemote = useMemo(
    () => ({
      ...workspaceRemote,
      workspaceFiles,
      reeArtifactFiles,
    }),
    [reeArtifactFiles, workspaceFiles, workspaceRemote],
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
    setRee: (value: ReeDraftViewModel | ((current: ReeDraftViewModel) => ReeDraftViewModel)) =>
      dispatch(appShellActions.setRee(value)),
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
    setWorkspaceFiles: (value: FileTreeNode[] | ((current: FileTreeNode[]) => FileTreeNode[])) =>
      dispatch(appShellActions.setWorkspaceFiles(value)),
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
    workspaceRemote: resolvedWorkspaceRemote,
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
