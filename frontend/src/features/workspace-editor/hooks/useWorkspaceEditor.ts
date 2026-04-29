import { useMemo } from "react";
import {
  explorerSelectors,
  useWorkspaceEditorContext,
  workspaceEditorActions,
} from "../../../context";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
  FileTreeNode,
  Ree,
  ReeFile,
  ServiceParams,
  SourceUploadCommit,
  WorkspaceEditorPage,
} from "../../../types";
import { useWorkspaceWorkflowRuns } from "./useWorkspaceWorkflowRuns";

export function useWorkspaceEditor() {
  const { state, dispatch } = useWorkspaceEditorContext();
  const explorer = explorerSelectors.state(state);

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
  } = explorer;

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
