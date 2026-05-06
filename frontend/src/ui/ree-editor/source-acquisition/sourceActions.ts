import type { QueryClient } from "@tanstack/react-query";
import type { AppShellClock } from "../../../app/bootstrap/ports";
import type { ReeEditorViewModel } from "../../../application/ree-editor/reeEditorViewModel";
import { createSourceUseCase } from "../../../application/workspace/acquireSource";
import {
  type SourceCommand,
  sourceChangeResetCommands,
  sourceFailureCommands,
} from "../../../application/workspace/sourceAcquisitionCommands";
import { runSourceWorkspaceAction } from "../../../application/workspace/sourceAcquisitionLifecycle";
import type { SourceUploadCommit } from "../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import { serializeWorkspaceResetPayload } from "../../../core/workspace/WorkspaceReset";
import type { ExecutionRunsClient } from "../../../data/execution-runs/client";
import type { ReeClient } from "../../../data/ree/client";
import {
  executeSourceCommands,
  type ReeEditorDispatch,
} from "../assembly-runs/assemblyActionEffects";
import { pollExecutionRun } from "../assembly-runs/pollExecutionRun";
import type { ShowToast } from "../types";

function resetAssemblyStateOnSourceChange(
  dispatch: ReeEditorDispatch,
  showToast: ShowToast,
  options: { silent?: boolean } = {},
): void {
  executeSourceCommands(sourceChangeResetCommands(options), { dispatch, showToast });
}

interface CreateSourceActionsArgs {
  ree: ReeEditorViewModel;
  reeClient: ReeClient<FileTreeNode>;
  executionRunsClient: ExecutionRunsClient;
  reeId: string;
  queryClient: QueryClient;
  dispatch: ReeEditorDispatch;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceActions({
  ree,
  reeClient,
  executionRunsClient,
  reeId,
  queryClient,
  dispatch,
  refreshWorkspaceFiles,
  showToast,
  clock,
  sleep,
  onRunStarted,
  onRunFinished,
}: CreateSourceActionsArgs) {
  const runCommands = (commands: SourceCommand[]) =>
    executeSourceCommands(commands, { dispatch, showToast });

  const resetSourceAssemblyState = (options: { silent?: boolean } = {}) => {
    resetAssemblyStateOnSourceChange(dispatch, showToast, options);
  };

  const runRemoteOrLocalSourceAction = async (
    resetRequest: Record<string, string | boolean | number | null | undefined>,
    runParams: Record<string, string | boolean | number | null | undefined>,
  ) =>
    runSourceWorkspaceAction({
      reeClient,
      executionRunClient: executionRunsClient,
      reeId,
      resetPayload: serializeWorkspaceResetPayload(resetRequest),
      runParams,
      pollRun: (nextReeId, runId, onUpdateLogs) =>
        pollExecutionRun(queryClient, executionRunsClient, {
          reeId: nextReeId,
          runId,
          onUpdate: onUpdateLogs,
          clock,
          sleep,
        }),
      onRunStarted: (key, runId) => {
        runCommands([{ type: "setActiveRunId", key, runId }]);
        onRunStarted?.(key, runId);
      },
      onRunFinished,
      onUpdateLogs: (update) => {
        runCommands([{ type: "setSourceLog", lines: update.lines, ts: update.ts }]);
      },
    });

  const sourceAcquisition = createSourceUseCase({
    ree,
    executeCommands: runCommands,
    sourceChanged: resetSourceAssemblyState,
    runSourceAction: runRemoteOrLocalSourceAction,
    refreshWorkspaceFiles,
    clearWorkspace: () => reeClient.resetWorkspaceRequest(reeId, { mode: "clear" }),
    nowIso: clock.nowIso,
  });

  const handleDownloadSourceFiles = async (
    originType: ReeEditorViewModel["source_type"],
    sourceUrl: string,
  ) => sourceAcquisition.downloadSource(originType, sourceUrl);

  const handleWorkspaceUpload = (payload: SourceUploadCommit) => {
    const archiveName = payload.archiveName || "source.tar.gz";
    const runUpload = async () => {
      try {
        let archiveContentBase64: string | undefined;
        if (payload.archiveFile) {
          archiveContentBase64 = await fileToBase64(payload.archiveFile);
        }
        await sourceAcquisition.uploadSource({ archiveName, archiveContentBase64 });
      } catch (error) {
        runCommands(
          sourceFailureCommands({
            message:
              error instanceof Error
                ? `Failed to extract archive: ${error.message}`
                : "Failed to extract archive",
          }),
        );
      }
    };
    void runUpload();
  };

  const handleRemoveWorkspaceSource = () => {
    void sourceAcquisition.removeSource();
  };

  return {
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    resetSourceAssemblyState,
  };
}

async function fileToBase64(file: File): Promise<string> {
  const rawBuffer = await file.arrayBuffer();
  const bytes = new Uint8Array(rawBuffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
