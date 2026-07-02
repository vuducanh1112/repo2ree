import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import type { ReeFile } from "@core/ree/ReeTypes";
import {
  createReeEditorStateFromModel,
  type ReeEditorState,
} from "@core/ree-editor/reeEditorState";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { DraftManifest, SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useReeQuery } from "@shell/data/ree/queries";
import { showToast as enqueueToast } from "@shell/ui/app-shell/state/actions";
import type { AssemblyRunState } from "@shell/ui/app-shell/state/assemblyRunState";
import type { ReeIntentState } from "@shell/ui/app-shell/state/reeIntent";
import type { ReeSessionState } from "@shell/ui/app-shell/state/reeSession";
import type { AppShellAction } from "@shell/ui/app-shell/state/types";
import type { UiChromeState } from "@shell/ui/app-shell/state/uiChrome";
import type React from "react";
import { useCallback, useMemo, useRef } from "react";
import { useReeAssemblyRuns } from "../assembly-runs/useReeAssemblyRuns";
import { useReeDownloads } from "../downloads/useReeDownloads";
import { useReeSeal } from "../seal/useReeSeal";
import { useSourceAcquisition } from "../source-acquisition/useSourceAcquisition";
import type { ShowToast } from "../types";
import { useWorkspaceFilePersistence } from "../workspace-files/useWorkspaceFilePersistence";
import { createHydrateReeWorkspace } from "../workspace-sync/hydrateReeWorkspace";
import { useReeIntentSync } from "../workspace-sync/useReeIntentSync";
import { createReeEditorCommands } from "./createReeEditorCommands";

interface UseReeEditorArgs {
  reeIntent: ReeIntentState;
  reeSession: ReeSessionState;
  assemblyRun: AssemblyRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
}

export function useReeEditor({
  reeIntent,
  reeSession,
  assemblyRun,
  uiChrome,
  dispatch,
}: UseReeEditorArgs) {
  const { reeId } = useApiRuntime();
  const provisioned = reeId !== DEFAULT_REE_ID;
  const reeQuery = useReeQuery({ enabled: provisioned });
  const workspaceFiles = reeQuery.data?.files ?? [];
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? [];
  const draftManifest = reeQuery.data?.draftManifest;
  const sourceRepo = reeQuery.data?.sourceRepo;

  const reeEditorState: ReeEditorState = useMemo(
    () => createReeEditorStateFromModel({ reeIntent, reeSession, uiChrome, assemblyRun }),
    [reeIntent, reeSession, uiChrome, assemblyRun],
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
  const {
    refreshWorkspace,
    refreshWorkspaceFiles,
    flush: flushReeIntent,
  } = useReeIntentSync({
    ree,
    reeId,
    provisioned,
    hydrateWorkspace,
  });
  const { persistWorkspaceFile } = useWorkspaceFilePersistence({
    refreshWorkspaceFiles,
    showToast,
  });

  // Imperative shell adapter: mirror the reducer's active run ids into a ref so
  // the cancel handler (an event callback) reads the current run id without a
  // stale closure. The reducer stays the single source of truth; this is only a
  // live read handle, matching the ref pattern used elsewhere in the shell.
  const activeRunIdsRef = useRef(assemblyRun.activeRunIds);
  activeRunIdsRef.current = assemblyRun.activeRunIds;
  const getActiveRunId = useCallback((key: string) => activeRunIdsRef.current[key], []);

  const { runAction, runAssemblyStep, cancelAction } = useReeAssemblyRuns({
    dispatch,
    ree,
    workspaceFiles,
    persistWorkspaceFile,
    refreshWorkspace,
    showToast,
    getActiveRunId,
  });
  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    useSourceAcquisition({
      dispatch,
      ree,
      refreshWorkspaceFiles,
      showToast,
    });
  const { downloadWorkspaceFile, handleDownloadRee } = useReeDownloads({
    getReeName: () => ree.name || "",
    showToast,
    reeId,
  });
  const { handleSealRee, sealRunning, sealLog } = useReeSeal({
    reeId,
    showToast,
    hydrateWorkspace,
    flushReeIntent,
  });

  const workspaceRemote = useMemo(
    () =>
      createWorkspaceRemoteState({
        workspaceFiles,
        reeArtifactFiles,
        draftManifest,
        reeSession,
        uiChrome,
        sourceRepo,
      }),
    [workspaceFiles, reeArtifactFiles, draftManifest, reeSession, uiChrome, sourceRepo],
  );
  const commands = useMemo(
    () =>
      createReeEditorCommands({
        reeIntent,
        reeSession,
        assemblyRun,
        uiChrome,
        dispatch,
        runAction,
        runAssemblyStep,
        cancelAction,
        persistWorkspaceFile,
        handleDownloadRee,
        handleSealRee,
        handleDownloadSourceFiles,
        handleWorkspaceUpload,
        handleRemoveWorkspaceSource,
        downloadWorkspaceFile,
        flushReeIntent,
      }),
    [
      assemblyRun,
      cancelAction,
      dispatch,
      downloadWorkspaceFile,
      flushReeIntent,
      handleDownloadRee,
      handleSealRee,
      handleDownloadSourceFiles,
      handleRemoveWorkspaceSource,
      handleWorkspaceUpload,
      persistWorkspaceFile,
      reeIntent,
      reeSession,
      runAction,
      runAssemblyStep,
      uiChrome,
    ],
  );

  return {
    provisioned,
    reeIntent,
    reeSession,
    ree,
    workspaceRemote,
    assemblyRun,
    evaluation: {
      dependencyLevel: ree.dependencyLevel ?? 0,
      environmentLevel: ree.environmentLevel ?? 0,
      machineLevel: ree.machineLevel ?? 0,
    },
    currentReeFiles: reeArtifactFiles,
    commands,
    sealRunning,
    sealLog,
  };
}

function createWorkspaceRemoteState(args: {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  draftManifest: DraftManifest | undefined;
  reeSession: ReeSessionState;
  uiChrome: UiChromeState;
  sourceRepo: SourceRepoMetadata | undefined;
}) {
  return {
    workspaceFiles: args.workspaceFiles,
    reeArtifactFiles: args.reeArtifactFiles,
    draftManifest: args.draftManifest,
    workspaceSourceState: args.reeSession.workspaceSourceState,
    artifactStatus: args.reeSession.artifactStatus,
    sourceSnapshotArchiveName: args.uiChrome.sourceSnapshotArchiveName,
    sourceSnapshotFiles: [] as FileTreeNode[],
    sourceRepo: args.sourceRepo,
  };
}
