import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import { splitReePatch } from "../../domain/ree/reeDraftViewModel";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { type SourceCommand, sourceFailureCommands } from "./sourceAcquisitionCommands";
import {
  planClearedSourceStateResult,
  planDownloadedSourceState,
  planSourceDownloadAction,
  planSourceUploadAction,
  planSourceWorkflowFailure,
  planUploadedSourceState,
} from "./sourceAcquisitionPlanning";

type SourceWorkflowStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

type SourceWorkflowRequest = Record<string, string | boolean | number | null | undefined>;

interface SourceWorkflowResult {
  status: SourceWorkflowStatus;
}

interface SourceUseCaseEffects {
  executeCommands: (commands: SourceCommand[]) => void;
  sourceChanged: (options?: { silent?: boolean }) => void;
  runSourceAction: (
    resetRequest: SourceWorkflowRequest,
    runParams: SourceWorkflowRequest,
  ) => Promise<SourceWorkflowResult>;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  clearWorkspace: () => Promise<void>;
  nowIso: () => string;
}

interface SourceUseCaseArgs extends SourceUseCaseEffects {
  ree: ReeDraftViewModel;
}

interface UploadSourceArgs {
  archiveName: string;
  archiveContentBase64?: string;
}

function isTerminalSourceWorkflowFailure(
  status: SourceWorkflowStatus,
): status is Extract<SourceWorkflowStatus, "failed" | "canceled"> {
  return status === "failed" || status === "canceled";
}

export function createSourceUseCase({
  ree,
  executeCommands,
  sourceChanged,
  runSourceAction,
  refreshWorkspaceFiles,
  clearWorkspace,
  nowIso,
}: SourceUseCaseArgs) {
  const failSourceAction = (message: string) => {
    executeCommands(sourceFailureCommands({ message }));
  };

  const runSourceWorkflowAndHandleFailure = async (
    resetRequest: SourceWorkflowRequest,
    runParams: SourceWorkflowRequest,
  ): Promise<boolean> => {
    sourceChanged({ silent: true });
    executeCommands([{ type: "setSourceLoading" }]);
    const result = await runSourceAction(resetRequest, runParams);
    if (isTerminalSourceWorkflowFailure(result.status)) {
      failSourceAction(planSourceWorkflowFailure(result.status).error);
      return false;
    }
    return true;
  };

  const runSourceMutationAction = async (args: {
    resetRequest: SourceWorkflowRequest;
    runParams: SourceWorkflowRequest;
    onSuccess: () => Promise<void>;
  }) => {
    if (!(await runSourceWorkflowAndHandleFailure(args.resetRequest, args.runParams))) {
      return;
    }
    await args.onSuccess();
  };

  const completeDownload = async (args: {
    originType: ReeDraftViewModel["source_type"];
    normalizedSourceUrl: string;
  }) => {
    const workspaceFiles = await refreshWorkspaceFiles();
    const successPlan = planDownloadedSourceState({
      ree,
      originType: args.originType,
      normalizedSourceUrl: args.normalizedSourceUrl,
      workspaceFiles,
      timestamp: nowIso(),
    });
    executeCommands(sourceSuccessCommands(successPlan));
  };

  const completeUpload = async (archiveName: string) => {
    const workspaceFiles = await refreshWorkspaceFiles();
    const successPlan = planUploadedSourceState({
      ree,
      archiveName,
      workspaceFiles,
      timestamp: nowIso(),
    });
    executeCommands(sourceSuccessCommands(successPlan));
  };

  return {
    async downloadSource(
      originType: ReeDraftViewModel["source_type"],
      sourceUrl: string,
    ): Promise<void> {
      const plan = planSourceDownloadAction(ree, originType, sourceUrl);
      if (!plan.ok) {
        executeCommands([{ type: "toast", message: plan.error, toastType: "error" }]);
        return;
      }

      await runSourceMutationAction({
        resetRequest: plan.value.resetRequest,
        runParams: plan.value.runParams,
        onSuccess: async () =>
          completeDownload({
            originType,
            normalizedSourceUrl: plan.value.normalizedSourceUrl,
          }),
      });
    },

    async uploadSource({ archiveName, archiveContentBase64 }: UploadSourceArgs): Promise<void> {
      try {
        const plan = planSourceUploadAction(ree, archiveName, archiveContentBase64);
        if (!plan.ok) {
          failSourceAction(plan.error);
          return;
        }

        await runSourceMutationAction({
          resetRequest: plan.value.resetRequest,
          runParams: plan.value.runParams,
          onSuccess: async () => completeUpload(archiveName),
        });
      } catch (error) {
        failSourceAction(
          error instanceof Error
            ? `Failed to extract archive: ${error.message}`
            : "Failed to extract archive",
        );
      }
    },

    async removeSource(): Promise<void> {
      sourceChanged({ silent: true });
      try {
        await clearWorkspace();
        await refreshWorkspaceFiles();
        const clearPlan = planClearedSourceStateResult();
        executeCommands([
          {
            type: "applySourceOutcome",
            outcome: {
              ...splitReePatch(clearPlan.reePatch),
              sourceSnapshotFiles: clearPlan.snapshotFiles,
              sourceSnapshotArchiveName: clearPlan.snapshotArchiveName,
            },
          },
          { type: "toast", message: clearPlan.infoMessage, toastType: "info" },
        ]);
      } catch (error) {
        executeCommands([
          {
            type: "toast",
            message:
              error instanceof Error
                ? `Failed to clear source: ${error.message}`
                : "Failed to clear source",
            toastType: "error",
          },
        ]);
      }
    },
  };
}

function sourceSuccessCommands(plan: {
  reePatch: Partial<ReeDraftViewModel>;
  snapshotFiles: FileTreeNode[];
  snapshotArchiveName: string;
  actionState: "done";
  badge: true;
  timestamp: string;
  successMessage: string;
}): SourceCommand[] {
  return [
    {
      type: "applySourceOutcome",
      outcome: {
        ...splitReePatch(plan.reePatch),
        sourceSnapshotFiles: plan.snapshotFiles,
        sourceSnapshotArchiveName: plan.snapshotArchiveName,
        actionState: plan.actionState,
        badge: plan.badge,
        timestamp: plan.timestamp,
      },
    },
    { type: "toast", message: plan.successMessage, toastType: "success" },
  ];
}
