import type { WorkspaceBackendGateway } from "../../../application/ports/WorkspaceBackendGateway";
import { serializeWorkspaceResetPayload } from "../../../application/ports/WorkspaceBackendGateway";
import { createSourceUseCase } from "../../../application/workspace/acquireSource";
import {
  type SourceCommand,
  sourceChangeResetCommands,
  sourceFailureCommands,
} from "../../../application/workspace/sourceAcquisitionCommands";
import { runSourceWorkspaceAction } from "../../../application/workspace/sourceAcquisitionLifecycle";
import type { WorkspaceEditorClock } from "../../../application/workspace-editor/WorkspaceEditorPorts";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { SourceUploadCommit } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { executeSourceCommands, type WorkspaceWorkflowDispatch } from "./commandExecutors";
import { pollWorkflowRun } from "./pollWorkflowRun";
import type { ShowToast } from "./types";

export function resetWorkflowOnSourceChange(
  dispatch: WorkspaceWorkflowDispatch,
  showToast: ShowToast,
  options: { silent?: boolean } = {},
): void {
  executeSourceCommands(sourceChangeResetCommands(options), { dispatch, showToast });
}

interface CreateSourceActionsArgs {
  ree: Ree;
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
  dispatch: WorkspaceWorkflowDispatch;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  onSourceChange: (options?: { silent?: boolean }) => void;
  showToast: ShowToast;
  clock: WorkspaceEditorClock;
  sleep: (ms: number) => Promise<void>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceActions({
  ree,
  workspaceService,
  workspaceId,
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
      workspaceService,
      workspaceId,
      resetPayload: serializeWorkspaceResetPayload(resetRequest),
      runParams,
      pollRun: (workspaceId, runId, onUpdateLogs) =>
        pollWorkflowRun(workspaceService, {
          workspaceId,
          runId,
          onUpdate: onUpdateLogs,
          clock,
          sleep,
        }),
      onRunStarted,
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
    clearWorkspace: () =>
      workspaceService.resetWorkspace(
        workspaceId,
        serializeWorkspaceResetPayload({ mode: "clear" }),
      ),
    nowIso: clock.nowIso,
  });

  const handleDownloadSourceFiles = async (originType: Ree["source_type"], sourceUrl: string) =>
    sourceAcquisition.downloadSource(originType, sourceUrl);

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
