import type { FileTreeNode, Ree } from "../../types";
import {
  planClearedSourceStateResult,
  planDownloadedSourceState,
  planSourceDownloadAction,
  planSourceUploadAction,
  planSourceWorkflowFailure,
  planUploadedSourceState,
} from "./sourceActionPlanning";
import { type SourceCommand, sourceFailureCommands } from "./sourceCommands";

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
  ree: Ree;
}

interface UploadSourceArgs {
  archiveName: string;
  archiveContentBase64?: string;
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
    executeCommands(sourceFailureCommands({ ree, message }));
  };

  const completeDownload = async (args: {
    originType: Ree["source_type"];
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
    async downloadSource(originType: Ree["source_type"], sourceUrl: string): Promise<void> {
      const plan = planSourceDownloadAction(ree, originType, sourceUrl);
      if (!plan.ok) {
        executeCommands([{ type: "toast", message: plan.error, toastType: "error" }]);
        return;
      }

      sourceChanged({ silent: true });
      executeCommands([{ type: "setSourceLoading" }]);
      const result = await runSourceAction(plan.value.resetRequest, plan.value.runParams);
      if (result.status === "failed" || result.status === "canceled") {
        failSourceAction(planSourceWorkflowFailure(result.status).error);
        return;
      }

      await completeDownload({
        originType,
        normalizedSourceUrl: plan.value.normalizedSourceUrl,
      });
    },

    async uploadSource({ archiveName, archiveContentBase64 }: UploadSourceArgs): Promise<void> {
      sourceChanged({ silent: true });
      try {
        executeCommands([{ type: "setSourceLoading" }]);
        const plan = planSourceUploadAction(ree, archiveName, archiveContentBase64);
        if (!plan.ok) {
          failSourceAction(plan.error);
          return;
        }

        const result = await runSourceAction(plan.value.resetRequest, plan.value.runParams);
        if (result.status === "failed" || result.status === "canceled") {
          failSourceAction(planSourceWorkflowFailure(result.status).error);
          return;
        }

        await completeUpload(archiveName);
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
        const clearPlan = planClearedSourceStateResult(ree);
        executeCommands([
          {
            type: "applySourceOutcome",
            outcome: {
              ree: clearPlan.ree,
              immutableSourceSnapshotFiles: clearPlan.snapshotFiles,
              immutableSourceSnapshotArchiveName: clearPlan.snapshotArchiveName,
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
  ree: Ree;
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
        ree: plan.ree,
        immutableSourceSnapshotFiles: plan.snapshotFiles,
        immutableSourceSnapshotArchiveName: plan.snapshotArchiveName,
        actionState: plan.actionState,
        badge: plan.badge,
        timestamp: plan.timestamp,
      },
    },
    { type: "toast", message: plan.successMessage, toastType: "success" },
  ];
}
