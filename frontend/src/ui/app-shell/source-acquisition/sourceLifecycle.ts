import type { QueryClient } from "@tanstack/react-query";
import type { AppShellClock } from "../../../app/bootstrap/ports";
import { createSourceUseCase } from "../../../application/workspace/acquireSource";
import {
  type SourceCommand,
  sourceChangeResetCommands,
  sourceFailureCommands,
} from "../../../application/workspace/sourceAcquisitionCommands";
import { runSourceWorkspaceAction } from "../../../application/workspace/sourceAcquisitionLifecycle";
import type { ReeClient } from "../../../data/ree/client";
import type { WorkflowRunsClient } from "../../../data/workflow-runs/client";
import type { SourceUploadCommit } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { serializeWorkspaceResetPayload } from "../../../domain/workspace/WorkspaceReset";
import {
  executeSourceCommands,
  type WorkspaceWorkflowDispatch,
} from "../workflow-runs/commandExecutors";
import { pollWorkflowRun } from "../workflow-runs/pollWorkflowRun";
import type { ShowToast } from "../workflow-runs/types";

export function resetWorkflowOnSourceChange(
  dispatch: WorkspaceWorkflowDispatch,
  showToast: ShowToast,
  options: { silent?: boolean } = {},
): void {
  executeSourceCommands(sourceChangeResetCommands(options), { dispatch, showToast });
}

interface CreateSourceActionsArgs {
  ree: ReeViewState;
  reeClient: ReeClient<FileTreeNode>;
  workflowRunsClient: WorkflowRunsClient;
  reeId: string;
  queryClient: QueryClient;
  dispatch: WorkspaceWorkflowDispatch;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  onSourceChange: (options?: { silent?: boolean }) => void;
  showToast: ShowToast;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceActions({
  ree,
  reeClient,
  workflowRunsClient,
  reeId,
  queryClient,
  dispatch,
  refreshWorkspaceFiles,
  onSourceChange,
  showToast,
  clock,
  sleep,
  onRunStarted,
  onRunFinished,
}: CreateSourceActionsArgs) {
  const runCommands = (commands: SourceCommand[]) =>
    executeSourceCommands(commands, { dispatch, showToast });

  const runRemoteOrLocalSourceAction = async (
    resetRequest: Record<string, string | boolean | number | null | undefined>,
    runParams: Record<string, string | boolean | number | null | undefined>,
  ) =>
    runSourceWorkspaceAction({
      reeClient,
      workflowRunClient: workflowRunsClient,
      reeId,
      resetPayload: serializeWorkspaceResetPayload(resetRequest),
      runParams,
      pollRun: (reeId, runId, onUpdateLogs) =>
        pollWorkflowRun(queryClient, workflowRunsClient, {
          reeId,
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
    sourceChanged: onSourceChange,
    runSourceAction: runRemoteOrLocalSourceAction,
    refreshWorkspaceFiles,
    clearWorkspace: () => reeClient.resetWorkspaceRequest(reeId, { mode: "clear" }),
    nowIso: clock.nowIso,
  });

  const handleDownloadSourceFiles = async (
    originType: ReeViewState["source_type"],
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
