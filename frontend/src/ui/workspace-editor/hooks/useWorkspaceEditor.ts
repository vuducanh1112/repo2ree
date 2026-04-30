import { useMemo } from "react";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import {
  workspaceEditorActions,
  workspaceEditorSelectors,
} from "../../../application/workspace-editor";
import type { WorkspaceEditorPage } from "../../../application/workspace-editor/WorkspaceEditorPages";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { ReeFile, ServiceParams, SourceUploadCommit } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useWorkspaceWorkflowRuns } from "../orchestration/useWorkspaceWorkflowRuns";
import { useWorkspaceEditorContext } from "../providers/WorkspaceEditorProvider";

export function useWorkspaceEditor() {
  const { state, dispatch } = useWorkspaceEditorContext();
  const workspaceEditor = workspaceEditorSelectors.state(state);

  const {
    ree: reeDraft,
    locked,
    actionStates,
    badges,
    timestamps,
    serviceLogs,
    serviceParams,
    toast,
    page,
    repoMode,
    focusedField,
    navCollapsed,
    virtualFiles,
    workspaceReeFiles,
    immutableSourceSnapshotFiles,
    showReviewerPreview,
  } = workspaceEditor;

  const currentReeFiles = useMemo<ReeFile[]>(() => workspaceReeFiles || [], [workspaceReeFiles]);

  const level = reeDraft._evalLevel ?? 0;
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
    virtualFiles,
    serviceParams,
  });

  const commands = {
    setPage: (nextPage: WorkspaceEditorPage) => dispatch(workspaceEditorActions.setPage(nextPage)),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(workspaceEditorActions.setNavCollapsed(value)),
    setRee: (value: Ree | ((current: Ree) => Ree)) =>
      dispatch(workspaceEditorActions.setRee(value)),
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(workspaceEditorActions.setLocked(value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(workspaceEditorActions.setRepoMode(value)),
    setFocusedField: (value: string | null | ((current: string | null) => string | null)) =>
      dispatch(workspaceEditorActions.setFocusedField(value)),
    setVirtualFiles: (value: FileTreeNode[] | ((current: FileTreeNode[]) => FileTreeNode[])) =>
      dispatch(workspaceEditorActions.setVirtualFiles(value)),
    setServiceParams: (value: ServiceParams | ((current: ServiceParams) => ServiceParams)) =>
      dispatch(workspaceEditorActions.setServiceParams(value)),
    openReviewerPreview: () => dispatch(workspaceEditorActions.setShowReviewerPreview(true)),
    closeReviewerPreview: () => dispatch(workspaceEditorActions.setShowReviewerPreview(false)),
    clearToast: () => dispatch(workspaceEditorActions.setToast(null)),
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
    state: {
      ree: reeDraft,
      locked,
      actionStates,
      badges,
      timestamps,
      serviceLogs,
      serviceParams,
      toast,
      page,
      repoMode,
      focusedField,
      navCollapsed,
      virtualFiles,
      workspaceReeFiles,
      immutableSourceSnapshotFiles,
      showReviewerPreview,
      level,
      currentReeFiles,
    },
    commands,
    reviewer: {
      showReviewerPreview,
    },
  };
}
