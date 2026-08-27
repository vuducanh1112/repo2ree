import { emptyEvaluationState } from "@core/evaluate/EvaluationState";
import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import type { ReeFile } from "@core/ree/ReeTypes";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { projectStepRuns } from "@core/runs/stepRunProjection";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { projectCurrentSourceRun } from "@core/workspace/sourceRunProjection";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { useReeId } from "@shell/data/apiRuntime";
import { useReeQuery } from "@shell/data/ree/queries";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import { showToast as enqueueToast } from "@shell/state/ree-editor/store/actions";
import type { ReeIntentState } from "@shell/state/ree-editor/store/reeIntent";
import type { StepRunFormState } from "@shell/state/ree-editor/store/stepRunState";
import type { AppShellAction } from "@shell/state/ree-editor/store/types";
import type React from "react";
import { useCallback, useMemo } from "react";
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
  stepRuns: StepRunFormState;
  dispatch: React.Dispatch<AppShellAction>;
}

export interface WorkspaceRemoteState {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  workspaceSourceState: ReeEditorViewModel["source"];
  artifactStatus: ReeEditorViewModel["artifact"];
  sourceRepo: SourceRepoMetadata | undefined;
}

export function useReeEditor({ reeIntent, stepRuns, dispatch }: UseReeEditorArgs) {
  const reeId = useReeId();
  const provisioned = reeId !== DEFAULT_REE_ID;
  const reeQuery = useReeQuery({ enabled: provisioned });
  const workspaceFiles = reeQuery.data?.files ?? [];
  const reeArtifactFiles = reeQuery.data?.reeFiles ?? [];
  const authorReceipts = reeQuery.data?.authorReceipts ?? [];
  const sourceRepo = reeQuery.data?.sourceRepo;
  const remoteRee = reeQuery.data?.ree;
  const runs = useReeRunsQuery(reeId).data ?? [];
  const sourceRun = useMemo(
    () => projectCurrentSourceRun(remoteRee?.audit ?? {}, runs),
    [remoteRee?.audit, runs],
  );
  const workspaceSourceState = useMemo(
    () => ({
      ...(remoteRee?.workspaceSourceState ?? { sourceAvailable: false }),
      ...sourceRun.sourceState,
    }),
    [remoteRee?.workspaceSourceState, sourceRun.sourceState],
  );
  const backendStepRuns = useMemo(() => projectStepRuns(runs), [runs]);
  const effectiveStepRuns = useMemo(
    () => ({ ...stepRuns, ...backendStepRuns }),
    [stepRuns, backendStepRuns],
  );

  const ree: ReeEditorViewModel = useMemo(
    () =>
      createReeEditorViewModel({
        reeSpec: reeIntent.reeSpec,
        workspaceSourceState,
        artifactStatus: remoteRee?.artifactStatus ?? { runtimeIncluded: false },
        evaluationState: remoteRee?.evaluationState ?? emptyEvaluationState(),
        stepEvidence: remoteRee?.stepEvidence ?? {},
        audit: remoteRee?.audit,
      }),
    [reeIntent.reeSpec, remoteRee, workspaceSourceState],
  );
  const evaluation = useMemo(
    () => ({
      dependencyLevel: ree.evaluation.dependencyLevel ?? 0,
      environmentLevel: ree.evaluation.environmentLevel ?? 0,
      machineLevel: ree.evaluation.machineLevel ?? 0,
      detectedDependencies: ree.evaluation.detectedDependencies,
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

  const { runAction, runStep, cancelAction } = useReeStepRuns({
    dispatch,
    ree,
    workspaceFiles,
    persistWorkspaceFile,
    refreshWorkspace,
    showToast,
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
        remoteRee,
        workspaceSourceState,
        sourceRepo:
          sourceRun.displayName && sourceRepo
            ? { ...sourceRepo, name: sourceRun.displayName }
            : sourceRepo,
      }),
    [
      workspaceFiles,
      reeArtifactFiles,
      remoteRee,
      workspaceSourceState,
      sourceRepo,
      sourceRun.displayName,
    ],
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
      ree,
      workspaceRemote,
      stepRuns: effectiveStepRuns,
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
  remoteRee?: {
    artifactStatus: ReeEditorViewModel["artifact"];
  };
  workspaceSourceState: ReeEditorViewModel["source"];
  sourceRepo: SourceRepoMetadata | undefined;
}): WorkspaceRemoteState {
  return {
    workspaceFiles: args.workspaceFiles,
    reeArtifactFiles: args.reeArtifactFiles,
    workspaceSourceState: args.workspaceSourceState,
    artifactStatus: args.remoteRee?.artifactStatus ?? { runtimeIncluded: false },
    sourceRepo: args.sourceRepo,
  };
}
