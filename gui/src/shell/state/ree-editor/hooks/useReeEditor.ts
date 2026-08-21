import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import type { ReeFile } from "@core/ree/ReeTypes";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { useReeId } from "@shell/data/apiRuntime";
import { useReeQuery } from "@shell/data/ree/queries";
import { showToast as enqueueToast } from "@shell/state/ree-editor/store/actions";
import type { ReeIntentState } from "@shell/state/ree-editor/store/reeIntent";
import type { ReeSessionState } from "@shell/state/ree-editor/store/reeSession";
import type { StepRunState } from "@shell/state/ree-editor/store/stepRunState";
import type { AppShellAction } from "@shell/state/ree-editor/store/types";
import type { UiChromeState } from "@shell/state/ree-editor/store/uiChrome";
import type React from "react";
import { useCallback, useMemo, useRef } from "react";
import { useReeDownloads } from "../downloads/useReeDownloads";
import { useReeSeal } from "../seal/useReeSeal";
import { useSourceAcquisition } from "../source-acquisition/useSourceAcquisition";
import { useReeStepRuns } from "../step-runs/useReeStepRuns";
import type { ShowToast } from "../types";
import { useWorkspaceFilePersistence } from "../workspace-files/useWorkspaceFilePersistence";
import { createHydrateReeWorkspace } from "../workspace-sync/hydrateReeWorkspace";
import { useReeIntentSync } from "../workspace-sync/useReeIntentSync";
import { createReeEditorCommands } from "./createReeEditorCommands";

interface UseReeEditorArgs {
  reeIntent: ReeIntentState;
  reeSession: ReeSessionState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  dispatch: React.Dispatch<AppShellAction>;
}

export interface WorkspaceRemoteState {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  workspaceSourceState: ReeSessionState["workspaceSourceState"];
  artifactStatus: ReeSessionState["artifactStatus"];
  sourceSnapshotArchiveName: string;
  sourceSnapshotFiles: FileTreeNode[];
  sourceRepo: SourceRepoMetadata | undefined;
}

export function useReeEditor({
  reeIntent,
  reeSession,
  stepRuns,
  uiChrome,
  dispatch,
}: UseReeEditorArgs) {
  const reeId = useReeId();
  const provisioned = reeId !== DEFAULT_REE_ID;
  const reeQuery = useReeQuery({ enabled: provisioned });
  const workspaceFiles = reeQuery.data?.files ?? [];
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? [];
  const authorReceipts = reeQuery.data?.authorReceipts ?? [];
  const sourceRepo = reeQuery.data?.sourceRepo;

  const ree: ReeEditorViewModel = useMemo(
    () =>
      createReeEditorViewModel({
        reeSpec: reeIntent.reeSpec,
        workspaceSourceState: reeSession.workspaceSourceState,
        artifactStatus: reeSession.artifactStatus,
        evaluationState: stepRuns.evaluationState,
      }),
    [
      reeIntent.reeSpec,
      reeSession.artifactStatus,
      reeSession.workspaceSourceState,
      stepRuns.evaluationState,
    ],
  );
  const evaluation = useMemo(
    () => ({
      dependencyLevel: ree.evaluation.dependencyLevel ?? 0,
      environmentLevel: ree.evaluation.environmentLevel ?? 0,
      machineLevel: ree.evaluation.machineLevel ?? 0,
    }),
    [ree.evaluation],
  );

  const showToast = useCallback<ShowToast>(
    (message, type = "info") => dispatch(enqueueToast({ message, type })),
    [dispatch],
  );

  const hydrateWorkspace = useMemo(() => createHydrateReeWorkspace(dispatch), [dispatch]);
  const {
    hydration: workspaceHydration,
    retryHydration: retryWorkspaceHydration,
    refreshWorkspace,
    refreshWorkspaceFiles,
    flush: flushReeIntent,
    syncState: reeIntentSyncState,
    isDirty: isReeIntentDirty,
    retrySync: retryReeIntentSync,
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
  const activeRunIdsRef = useRef(stepRuns.activeRunIds);
  activeRunIdsRef.current = stepRuns.activeRunIds;
  const getActiveRunId = useCallback((key: string) => activeRunIdsRef.current[key], []);

  const { runAction, runStep, cancelAction } = useReeStepRuns({
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
  const getReeName = useCallback(() => ree.spec.name || "", [ree.spec.name]);
  const { downloadWorkspaceFile, handleDownloadRee } = useReeDownloads({
    getReeName,
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
        reeSession,
        sourceSnapshotArchiveName: uiChrome.sourceSnapshotArchiveName,
        sourceRepo,
      }),
    [workspaceFiles, reeArtifactFiles, reeSession, uiChrome.sourceSnapshotArchiveName, sourceRepo],
  );
  const commands = useMemo(
    () =>
      createReeEditorCommands({
        dispatch,
        runAction,
        runStep,
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
      runAction,
      runStep,
    ],
  );

  return {
    model: {
      provisioned,
      reeIntent,
      reeSession,
      ree,
      workspaceRemote,
      stepRuns,
      evaluation,
      currentReeFiles: reeArtifactFiles,
      authorReceipts,
    },
    sync: {
      workspaceHydration,
      retryWorkspaceHydration,
      reeIntentSyncState,
      isReeIntentDirty,
      retryReeIntentSync,
    },
    commands,
    seal: {
      running: sealRunning,
      log: sealLog,
    },
  };
}

function createWorkspaceRemoteState(args: {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  reeSession: ReeSessionState;
  sourceSnapshotArchiveName: string;
  sourceRepo: SourceRepoMetadata | undefined;
}): WorkspaceRemoteState {
  return {
    workspaceFiles: args.workspaceFiles,
    reeArtifactFiles: args.reeArtifactFiles,
    workspaceSourceState: args.reeSession.workspaceSourceState,
    artifactStatus: args.reeSession.artifactStatus,
    sourceSnapshotArchiveName: args.sourceSnapshotArchiveName,
    sourceSnapshotFiles: [] as FileTreeNode[],
    sourceRepo: args.sourceRepo,
  };
}
