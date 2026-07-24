import type { SourceUploadCommit } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { createSourceUseCase } from "@core/workspace/acquireSource";
import type { FileTreeNode } from "@core/workspace/FileTree";
import {
  type SourceCommand,
  sourceChangeResetCommands,
  sourceFailureCommands,
} from "@core/workspace/sourceAcquisitionCommands";
import { runSourceWorkspaceAction } from "@core/workspace/sourceAcquisitionLifecycle";
import { serializeWorkspaceResetPayload } from "@core/workspace/WorkspaceReset";
import type { AppShellClock } from "@shell/app/bootstrap/ports";
import { queryKeys } from "@shell/data/queryKeys";
import type { ReeClient } from "@shell/data/ree/client";
import type { ReeRunsClient } from "@shell/data/runs/client";
import { observeReeRun } from "@shell/data/runs/queries";
import type { QueryClient } from "@tanstack/react-query";
import { executeSourceCommands, type ReeEditorDispatch } from "../step-runs/stepActionEffects";
import type { ShowToast } from "../types";

function resetStepsStateOnSourceChange(
  dispatch: ReeEditorDispatch,
  showToast: ShowToast,
  options: { silent?: boolean } = {},
): void {
  executeSourceCommands(sourceChangeResetCommands(options), { dispatch, showToast });
}

interface CreateSourceActionsArgs {
  ree: ReeEditorViewModel;
  reeClient: ReeClient<FileTreeNode>;
  executionRunsClient: ReeRunsClient;
  reeId: string;
  queryClient: QueryClient;
  dispatch: ReeEditorDispatch;
  refreshWorkspaceFiles: (options?: { forceReeHydration?: boolean }) => Promise<FileTreeNode[]>;
  showToast: ShowToast;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
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
}: CreateSourceActionsArgs) {
  const runCommands = (commands: SourceCommand[]) =>
    executeSourceCommands(commands, { dispatch, showToast });

  const resetSourceStepsState = (options: { silent?: boolean } = {}) => {
    resetStepsStateOnSourceChange(dispatch, showToast, options);
  };

  // Source handlers settle backend-owned identity (resolved commit and SWHID)
  // after acquisition. A file-only refresh leaves those fields stranded in the
  // workbench document, so every completed source mutation must rehydrate the
  // editor from that authoritative document as well.
  const refreshSourceWorkspaceFiles = () => refreshWorkspaceFiles({ forceReeHydration: true });

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
        observeReeRun(queryClient, executionRunsClient, {
          reeId: nextReeId,
          runId,
          onUpdate: onUpdateLogs,
          sleep,
        }),
      onRunStarted: (key, runId) => {
        runCommands([{ type: "setActiveRunId", key, runId }]);
      },
      onUpdateLogs: (update) => {
        runCommands([{ type: "setSourceLog", lines: update.lines, ts: update.ts }]);
      },
    });

  const sourceAcquisition = createSourceUseCase({
    ree,
    executeCommands: runCommands,
    sourceChanged: resetSourceStepsState,
    runSourceAction: runRemoteOrLocalSourceAction,
    refreshWorkspaceFiles: refreshSourceWorkspaceFiles,
    clearWorkspace: () => reeClient.resetWorkspaceRequest(reeId, { mode: "clear" }),
    nowIso: clock.nowIso,
  });

  const handleDownloadSourceFiles = async (
    originType: ReeEditorViewModel["sourceType"],
    sourceUrl: string,
    revision?: string,
  ) => sourceAcquisition.downloadSource(originType, sourceUrl, revision);

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

  const handleRemoveWorkspaceSource = async () => {
    const removed = await sourceAcquisition.removeSource();
    if (removed) {
      queryClient.setQueryData(queryKeys.evaluateReport(reeId), null);
    }
  };

  return {
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    resetSourceStepsState,
  };
}

async function fileToBase64(file: File): Promise<string> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Upload reader returned non-text data"));
      }
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read upload archive"));
    reader.readAsDataURL(file);
  });
  const [, base64 = ""] = dataUrl.split(",", 2);
  return base64;
}
