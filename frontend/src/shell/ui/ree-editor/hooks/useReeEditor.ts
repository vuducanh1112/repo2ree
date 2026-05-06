import type React from "react";
import { useCallback, useMemo, useRef } from "react";
import type { ReeFile } from "../../../../core/ree/ReeTypes";
import { createAssemblyRunSession } from "../../../../core/ree-assembly/assemblyRunSession";
import {
  createReeEditorStateFromModel,
  type ReeEditorState,
} from "../../../../core/ree-editor/reeEditorState";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useReeQuery } from "../../../data/ree/queries";
import { showToast as enqueueToast } from "../../app-shell/state/actions";
import type { AssemblyRunState } from "../../app-shell/state/assemblyRunState";
import type { ReeDraftState } from "../../app-shell/state/reeDraft";
import type { AppShellAction } from "../../app-shell/state/types";
import type { UiChromeState } from "../../app-shell/state/uiChrome";
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
  assemblyRun: AssemblyRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
}

export function useReeEditor({ reeDraft, assemblyRun, uiChrome, dispatch }: UseReeEditorArgs) {
  const { reeId } = useApiRuntime();
  const reeQuery = useReeQuery();
  const workspaceFiles = reeQuery.data?.files ?? [];
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? [];

  const reeEditorState: ReeEditorState = useMemo(
    () => createReeEditorStateFromModel({ reeDraft, assemblyRun }),
    [reeDraft, assemblyRun],
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
  const { runAction, runAssemblyStep, cancelAction } = useReeAssemblyRuns({
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
      runAssemblyStep,
      showToast,
      uiChrome,
      assemblyRun,
    ],
  );

  return {
    reeDraft,
    ree,
    inclusionState: reeEditorState.inclusionState,
    workspaceRemote,
    assemblyRun,
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
