import { useMemo } from "react";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import {
  workspaceShellActions,
  workspaceShellSelectors,
} from "../../../application/workspace-shell";
import type { WorkspaceShellPage } from "../../../application/workspace-shell/WorkspaceShellPages";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";
import type { ReeFile, SourceUploadCommit, WorkflowParams } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useWorkspaceShellContext } from "../providers/WorkspaceShellProvider";
import { useWorkspaceWorkflowRuns } from "../workflow-runs/useWorkspaceWorkflowRuns";

export function useWorkspaceShell() {
  const { state, dispatch } = useWorkspaceShellContext();
  const workspaceDraft = workspaceShellSelectors.workspaceDraft(state);
  const workspaceRemote = workspaceShellSelectors.workspaceRemote(state);
  const workflowRun = workspaceShellSelectors.workflowRun(state);
  const uiChrome = workspaceShellSelectors.uiChrome(state);
  const reeDraft = workspaceShellSelectors.reeDraftViewModel(state);

  const { showReviewPreview } = uiChrome;
  const { workspaceFiles, reeArtifactFiles } = workspaceRemote;

  const currentReeFiles = useMemo<ReeFile[]>(() => reeArtifactFiles || [], [reeArtifactFiles]);

  const level = reeDraft.evalLevel ?? 0;
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
    ree: reeDraft,
    level,
    workspaceFiles,
  });

  const commands = {
    setPage: (nextPage: WorkspaceShellPage) => dispatch(workspaceShellActions.setPage(nextPage)),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(workspaceShellActions.setNavCollapsed(value)),
    setRee: (value: ReeDraftViewModel | ((current: ReeDraftViewModel) => ReeDraftViewModel)) =>
      dispatch(workspaceShellActions.setRee(value)),
    setReeSpec: (
      value:
        | typeof workspaceDraft.reeSpec
        | ((current: typeof workspaceDraft.reeSpec) => typeof workspaceDraft.reeSpec),
    ) => dispatch(workspaceShellActions.setReeSpec(value)),
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(workspaceShellActions.setLocked(value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(workspaceShellActions.setRepoMode(value)),
    setFocusedField: (value: string | null | ((current: string | null) => string | null)) =>
      dispatch(workspaceShellActions.setFocusedField(value)),
    setWorkspaceFiles: (value: FileTreeNode[] | ((current: FileTreeNode[]) => FileTreeNode[])) =>
      dispatch(workspaceShellActions.setWorkspaceFiles(value)),
    setWorkflowParams: (value: WorkflowParams | ((current: WorkflowParams) => WorkflowParams)) =>
      dispatch(workspaceShellActions.setWorkflowParams(value)),
    openReviewPreview: () => dispatch(workspaceShellActions.setShowReviewPreview(true)),
    closeReviewPreview: () => dispatch(workspaceShellActions.setShowReviewPreview(false)),
    clearToast: () => dispatch(workspaceShellActions.setToast(null)),
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
    workspaceDraft,
    workspaceRemote,
    workflowRun,
    uiChrome,
    reeDraft,
    level,
    currentReeFiles,
    commands,
    reviewer: {
      showReviewPreview,
    },
  };
}
