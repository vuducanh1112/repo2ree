import { useMemo } from "react";
import { explorerActions, explorerSelectors, useAppContext } from "../../../context";
import type {
  ExplorerPage,
  FileTreeNode,
  Ree,
  ServiceParams,
  SourceUploadCommit,
  WorkflowServiceKey,
  WorkflowServiceRunParams,
} from "../../../types";
import { buildCurrentReeArchiveEntries, reeArchiveEntriesToFiles } from "../../../utils";
import { useExplorerWorkflow } from "./useExplorerWorkflow";

export function useExplorerController() {
  const { state, dispatch } = useAppContext();
  const explorer = explorerSelectors.state(state);

  const {
    ree,
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
    immutableSourceSnapshotFiles,
    immutableSourceSnapshotArchiveName,
    showReviewerPreview,
  } = explorer;

  const currentReeArchiveEntries = useMemo(
    () =>
      buildCurrentReeArchiveEntries(
        ree,
        virtualFiles,
        immutableSourceSnapshotFiles,
        immutableSourceSnapshotArchiveName,
      ),
    [ree, virtualFiles, immutableSourceSnapshotFiles, immutableSourceSnapshotArchiveName],
  );

  const currentReeFiles = useMemo(
    () => reeArchiveEntriesToFiles(currentReeArchiveEntries),
    [currentReeArchiveEntries],
  );

  const level = ree._evalLevel ?? 0;
  const {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    persistWorkspaceFile,
    runAction,
    runWorkflowAction,
    cancelWorkflowAction,
  } = useExplorerWorkflow({
    dispatch,
    ree,
    level,
    virtualFiles,
    serviceParams,
    currentReeArchiveEntries,
  });

  const commands = {
    setPage: (nextPage: ExplorerPage) => dispatch(explorerActions.setPage(nextPage)),
    setNavCollapsed: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(explorerActions.setNavCollapsed(value)),
    setRee: (value: Ree | ((current: Ree) => Ree)) => dispatch(explorerActions.setRee(value)),
    setLocked: (value: boolean | ((current: boolean) => boolean)) =>
      dispatch(explorerActions.setLocked(value)),
    setRepoMode: (value: "url" | "upload" | ((current: "url" | "upload") => "url" | "upload")) =>
      dispatch(explorerActions.setRepoMode(value)),
    setFocusedField: (value: string | null | ((current: string | null) => string | null)) =>
      dispatch(explorerActions.setFocusedField(value)),
    setVirtualFiles: (value: FileTreeNode[] | ((current: FileTreeNode[]) => FileTreeNode[])) =>
      dispatch(explorerActions.setVirtualFiles(value)),
    setServiceParams: (value: ServiceParams | ((current: ServiceParams) => ServiceParams)) =>
      dispatch(explorerActions.setServiceParams(value)),
    openReviewerPreview: () => dispatch(explorerActions.setShowReviewerPreview(true)),
    closeReviewerPreview: () => dispatch(explorerActions.setShowReviewerPreview(false)),
    clearToast: () => dispatch(explorerActions.setToast(null)),
    onSeal: handleSeal,
    onDownloadRee: handleDownloadRee,
    onDownloadSourceFiles: handleDownloadSourceFiles,
    onWorkspaceUpload: (payload: SourceUploadCommit) => handleWorkspaceUpload(payload),
    onRemoveWorkspaceSource: handleRemoveWorkspaceSource,
    onRunAction: runAction,
    onCancelAction: cancelWorkflowAction,
    onRunWorkflowAction: <K extends WorkflowServiceKey>(
      key: K,
      params: WorkflowServiceRunParams<K>,
    ) => runWorkflowAction(key, params),
    onPersistWorkspaceFile: persistWorkspaceFile,
  };

  return {
    state: {
      ree,
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
