import type { ReeSpec } from "../../core/ree/ReeSpec";
import type { FileTreeNode } from "../../core/workspace/FileTree";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
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
  ree: ReeEditorViewModel;
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
  const failSourceAction = (message: string) => {
    executeCommands(sourceFailureCommands({ message }));
  };

  const runSourceExecutionAndHandleFailure = async (
    resetRequest: SourceExecutionRequest,
    runParams: SourceExecutionRequest,
  ): Promise<boolean> => {
    sourceChanged({ silent: true });
    executeCommands([{ type: "setSourceLoading" }]);
    const result = await runSourceAction(resetRequest, runParams);
    if (isTerminalSourceExecutionFailure(result.status)) {
      failSourceAction(planSourceExecutionFailure(result.status).error);
      return false;
    }
    return true;
  };

  const runSourceMutationAction = async (args: {
    resetRequest: SourceExecutionRequest;
    runParams: SourceExecutionRequest;
    onSuccess: () => Promise<void>;
  }) => {
    if (!(await runSourceExecutionAndHandleFailure(args.resetRequest, args.runParams))) {
      return;
    }
    await args.onSuccess();
  };

  const completeDownload = async (args: {
    originType: ReeEditorViewModel["source_type"];
    normalizedSourceUrl: string;
  }) => {
    const workspaceFiles = await refreshWorkspaceFiles();
    const successPlan = planDownloadedSourceState({
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
      archiveName,
      workspaceFiles,
      timestamp: nowIso(),
    });
    executeCommands(sourceSuccessCommands(successPlan));
  };

  return {
    async downloadSource(
      originType: ReeEditorViewModel["source_type"],
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
              reeSpecPatch: clearPlan.reeSpecPatch,
              workspaceSourceStatePatch: clearPlan.workspaceSourceStatePatch,
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
  reeSpecPatch: Partial<ReeSpec>;
  workspaceSourceStatePatch: Partial<WorkspaceSourceState>;
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
