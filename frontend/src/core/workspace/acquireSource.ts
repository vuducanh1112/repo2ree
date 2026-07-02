import type { ReeSpec } from "../../core/ree/ReeSpec";
import type { FileTreeNode } from "../../core/workspace/FileTree";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import { type SourceCommand, sourceFailureCommands } from "./sourceAcquisitionCommands";
import {
  planClearedSourceStateResult,
  planDownloadedSourceState,
  planSourceDownloadAction,
  planSourceExecutionFailure,
  planSourceUploadAction,
  planUploadedSourceState,
} from "./sourceAcquisitionPlanning";

type SourceExecutionStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

type SourceExecutionRequest = Record<string, string | boolean | number | null | undefined>;

interface SourceExecutionResult {
  runId?: string;
  status: SourceExecutionStatus;
}

interface SourceUseCaseEffects {
  executeCommands: (commands: SourceCommand[]) => void;
  sourceChanged: (options?: { silent?: boolean }) => void;
  runSourceAction: (
    resetRequest: SourceExecutionRequest,
    runParams: SourceExecutionRequest,
  ) => Promise<SourceExecutionResult>;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  clearWorkspace: () => Promise<void>;
  nowIso: () => string;
}

interface SourceUseCaseArgs extends SourceUseCaseEffects {
  ree: WorkspaceSourceState;
}

interface UploadSourceArgs {
  archiveName: string;
  archiveContentBase64?: string;
}

function isTerminalSourceExecutionFailure(
  status: SourceExecutionStatus,
): status is Extract<SourceExecutionStatus, "failed" | "canceled"> {
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
  const failSourceAction = (message: string, runId?: string) => {
    executeCommands(sourceFailureCommands({ message, runId }));
  };

  const runSourceExecutionAndHandleFailure = async (
    resetRequest: SourceExecutionRequest,
    runParams: SourceExecutionRequest,
  ): Promise<{ ok: boolean; runId?: string }> => {
    sourceChanged({ silent: true });
    executeCommands([{ type: "setSourceLoading" }]);
    const result = await runSourceAction(resetRequest, runParams);
    if (isTerminalSourceExecutionFailure(result.status)) {
      failSourceAction(planSourceExecutionFailure(result.status).error, result.runId);
      return { ok: false, runId: result.runId };
    }
    return { ok: true, runId: result.runId };
  };

  const runSourceMutationAction = async (args: {
    resetRequest: SourceExecutionRequest;
    runParams: SourceExecutionRequest;
    onSuccess: (runId?: string) => Promise<void>;
  }) => {
    const result = await runSourceExecutionAndHandleFailure(args.resetRequest, args.runParams);
    if (!result.ok) {
      return;
    }
    await args.onSuccess(result.runId);
  };

  const completeDownload = async (args: {
    originType: ReeSpec["source_type"];
    normalizedSourceUrl: string;
    runId?: string;
  }) => {
    const workspaceFiles = await refreshWorkspaceFiles();
    const successPlan = planDownloadedSourceState({
      originType: args.originType,
      normalizedSourceUrl: args.normalizedSourceUrl,
      workspaceFiles,
      timestamp: nowIso(),
    });
    executeCommands(sourceSuccessCommands(successPlan, args.runId));
  };

  const completeUpload = async (archiveName: string, runId?: string) => {
    const workspaceFiles = await refreshWorkspaceFiles();
    const successPlan = planUploadedSourceState({
      archiveName,
      workspaceFiles,
      timestamp: nowIso(),
    });
    executeCommands(sourceSuccessCommands(successPlan, runId));
  };

  return {
    async downloadSource(
      originType: ReeSpec["source_type"],
      sourceUrl: string,
      revision?: string,
    ): Promise<void> {
      const plan = planSourceDownloadAction(ree, originType, sourceUrl, revision);
      if (!plan.ok) {
        executeCommands([{ type: "toast", message: plan.error, toastType: "error" }]);
        return;
      }

      await runSourceMutationAction({
        resetRequest: plan.value.resetRequest,
        runParams: plan.value.runParams,
        onSuccess: async (runId) =>
          completeDownload({
            originType,
            normalizedSourceUrl: plan.value.normalizedSourceUrl,
            runId,
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
          onSuccess: async (runId) => completeUpload(archiveName, runId),
        });
      } catch (error) {
        failSourceAction(
          error instanceof Error
            ? `Failed to extract archive: ${error.message}`
            : "Failed to extract archive",
        );
      }
    },

    async removeSource(): Promise<boolean> {
      sourceChanged({ silent: true });
      try {
        await clearWorkspace();
        await refreshWorkspaceFiles();
        const clearPlan = planClearedSourceStateResult();
        executeCommands([
          {
            type: "applySourceOutcome",
            outcome: {
              reeSpecPatch: clearPlan.reeSpecPatch,
              workspaceSourceStatePatch: clearPlan.workspaceSourceStatePatch,
              sourceSnapshotArchiveName: clearPlan.snapshotArchiveName,
            },
          },
          { type: "toast", message: clearPlan.infoMessage, toastType: "info" },
        ]);
        return true;
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
        return false;
      }
    },
  };
}

function sourceSuccessCommands(
  plan: {
    reeSpecPatch: Partial<ReeSpec>;
    workspaceSourceStatePatch: Partial<WorkspaceSourceState>;
    snapshotFiles: FileTreeNode[];
    snapshotArchiveName: string;
    actionState: "done";
    badge: true;
    timestamp: string;
    successMessage: string;
  },
  runId?: string,
): SourceCommand[] {
  return [
    {
      type: "applySourceOutcome",
      outcome: {
        runId,
        reeSpecPatch: plan.reeSpecPatch,
        workspaceSourceStatePatch: plan.workspaceSourceStatePatch,
        sourceSnapshotArchiveName: plan.snapshotArchiveName,
        actionState: plan.actionState,
        badge: plan.badge,
        timestamp: plan.timestamp,
      },
    },
    { type: "toast", message: plan.successMessage, toastType: "success" },
  ];
}
