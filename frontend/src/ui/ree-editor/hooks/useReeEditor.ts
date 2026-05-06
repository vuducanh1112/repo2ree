import type React from "react";
import { useCallback, useMemo, useRef } from "react";
import { createAssemblyRunSession } from "../../../application/ree-assembly/assemblyRunSession";
import {
  createReeEditorStateFromAppShell,
  type ReeEditorState,
} from "../../../application/ree-editor/reeEditorState";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "../../../application/ree-editor/reeEditorViewModel";
import { showToast as enqueueToast } from "../../../application/state/actions";
import type { ReeDraftState } from "../../../application/state/reeDraft";
import type { AppShellAction } from "../../../application/state/types";
import type { UiChromeState } from "../../../application/state/uiChrome";
import type { WorkflowRunState } from "../../../application/state/workflowRun";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useReeQuery } from "../../../data/ree/queries";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useReeAssemblyRuns } from "../assembly-runs/useReeAssemblyRuns";
import { useReeDownloads } from "../downloads/useReeDownloads";
import { useSourceAcquisition } from "../source-acquisition/useSourceAcquisition";
import type { ShowToast } from "../types";
import { useWorkspaceFilePersistence } from "../workspace-files/useWorkspaceFilePersistence";
import { createHydrateReeWorkspace } from "../workspace-sync/hydrateReeWorkspace";
import { useReeDraftSync } from "../workspace-sync/useReeDraftSync";
import { createReeEditorCommands } from "./createReeEditorCommands";

interface UseReeEditorArgs {
  reeDraft: ReeDraftState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
}

export function useReeEditor({ reeDraft, workflowRun, uiChrome, dispatch }: UseReeEditorArgs) {
  const { reeId } = useApiRuntime();
  const reeQuery = useReeQuery();
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

  const showToast = useCallback<ShowToast>(
    (message, type = "info") => dispatch(enqueueToast({ message, type })),
    [dispatch],
  );

  const hydrateWorkspace = useMemo(() => createHydrateReeWorkspace(dispatch), [dispatch]);
  const { buildReePatch, refreshWorkspace, refreshWorkspaceFiles } = useReeDraftSync({
    ree,
    reeId,
    hydrateWorkspace,
  });
  const { persistWorkspaceFile } = useWorkspaceFilePersistence({
    refreshWorkspaceFiles,
    showToast,
  });

  const runSessionRef = useRef(createAssemblyRunSession());
  const runSession = runSessionRef.current;
  const { runAction, runAutomationStep, cancelAction } = useReeAssemblyRuns({
    dispatch,
    ree,
    level: ree.evalLevel ?? 0,
    workspaceFiles,
    persistWorkspaceFile,
    refreshWorkspace,
    showToast,
    runSession,
  });
  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    useSourceAcquisition({
      dispatch,
      ree,
      refreshWorkspaceFiles,
      showToast,
      onRunStarted: runSession.noteRunStarted,
      onRunFinished: runSession.noteRunFinished,
    });
  const { downloadWorkspaceFile, handleDownloadRee } = useReeDownloads({
    buildReePatch,
    getReeName: () => ree.name || "",
    showToast,
  });

  const workspaceRemote = useMemo(
    () => createWorkspaceRemoteState({ workspaceFiles, reeArtifactFiles, reeDraft }),
    [workspaceFiles, reeArtifactFiles, reeDraft],
  );
  const commands = useMemo(
    () =>
      createReeEditorCommands({
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
      }),
    [
      cancelAction,
      dispatch,
      downloadWorkspaceFile,
      handleDownloadRee,
      handleDownloadSourceFiles,
      handleRemoveWorkspaceSource,
      handleWorkspaceUpload,
      persistWorkspaceFile,
      reeDraft,
      reeEditorState,
      runAction,
      runAutomationStep,
      showToast,
      uiChrome,
      workflowRun,
    ],
  );

  return {
    reeDraft,
    ree,
    inclusionState: reeEditorState.inclusionState,
    workspaceRemote,
    workflowRun,
    level: ree.evalLevel ?? 0,
    currentReeFiles: reeArtifactFiles,
    commands,
    reviewer: {
      showReviewPreview: uiChrome.showReviewPreview,
    },
  };
}

function createWorkspaceRemoteState(args: {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  reeDraft: ReeDraftState;
}) {
  return {
    workspaceFiles: args.workspaceFiles,
    reeArtifactFiles: args.reeArtifactFiles,
    workspaceSourceState: args.reeDraft.workspaceSourceState,
    artifactStatus: args.reeDraft.artifactStatus,
    sourceSnapshotArchiveName: args.reeDraft.sourceSnapshotArchiveName,
    sourceSnapshotFiles: [] as FileTreeNode[],
  };
}
