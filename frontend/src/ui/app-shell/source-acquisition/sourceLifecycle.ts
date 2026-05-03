import type { QueryClient } from "@tanstack/react-query";
import type { AppShellClock } from "../../../application/app-shell/AppShellPorts";
import { serializeWorkspaceResetPayload } from "../../../application/ports/repositoryTypes";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
import type { WorkspaceRepository } from "../../../application/ports/WorkspaceRepository";
import { createSourceUseCase } from "../../../application/workspace/acquireSource";
import {
  type SourceCommand,
  sourceChangeResetCommands,
  sourceFailureCommands,
} from "../../../application/workspace/sourceAcquisitionCommands";
import { runSourceWorkspaceAction } from "../../../application/workspace/sourceAcquisitionLifecycle";
import type { SourceUploadCommit } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
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
  workspaceRepository: WorkspaceRepository<FileTreeNode>;
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
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
  workspaceRepository,
  workflowRunRepository,
  workspaceId,
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
      workspaceRepository,
      workflowRunRepository,
      workspaceId,
      resetPayload: serializeWorkspaceResetPayload(resetRequest),
      runParams,
      pollRun: (workspaceId, runId, onUpdateLogs) =>
        pollWorkflowRun(queryClient, workflowRunRepository, {
          workspaceId,
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
    clearWorkspace: () => workspaceRepository.resetWorkspaceRequest(workspaceId, { mode: "clear" }),
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
