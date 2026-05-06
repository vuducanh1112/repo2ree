import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
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

function mapReePatchToSourceOutcome(patch: Partial<ReeEditorViewModel>): {
  reeSpec?: Partial<ReeSpec>;
  workspaceSourceState?: Partial<WorkspaceSourceState>;
  artifactStatus?: Partial<ArtifactStatus>;
  evaluationState?: EvaluationState;
} {
  const reeSpec: Partial<ReeSpec> = {};
  const workspaceSourceState: Partial<WorkspaceSourceState> = {};
  const artifactStatus: Partial<ArtifactStatus> = {};
  let evaluationState: EvaluationState | undefined;
  if (Object.hasOwn(patch, "name")) reeSpec.name = patch.name;
  if (Object.hasOwn(patch, "origin_url")) reeSpec.origin_url = patch.origin_url;
  if (Object.hasOwn(patch, "source_type")) reeSpec.source_type = patch.source_type;
  if (Object.hasOwn(patch, "runtime")) reeSpec.runtime = patch.runtime;
  if (Object.hasOwn(patch, "build_runtime_script"))
    reeSpec.build_runtime_script = patch.build_runtime_script;
  if (Object.hasOwn(patch, "activation_script"))
    reeSpec.activation_script = patch.activation_script;
  if (Object.hasOwn(patch, "sbom")) reeSpec.sbom = patch.sbom;
  if (Object.hasOwn(patch, "swhid")) reeSpec.swhid = patch.swhid;
  if (Object.hasOwn(patch, "zenodo_doi")) reeSpec.zenodo_doi = patch.zenodo_doi;
  if (Object.hasOwn(patch, "dataverse_doi")) reeSpec.dataverse_doi = patch.dataverse_doi;
  if (Object.hasOwn(patch, "repro_level")) reeSpec.repro_level = patch.repro_level;
  if (Object.hasOwn(patch, "detected_dependencies"))
    reeSpec.detected_dependencies = patch.detected_dependencies;
  if (Object.hasOwn(patch, "hardware_description"))
    reeSpec.hardware_description = patch.hardware_description;
  if (Object.hasOwn(patch, "sourceAvailable"))
    workspaceSourceState.sourceAvailable = patch.sourceAvailable;
  if (Object.hasOwn(patch, "sourceIncluded"))
    workspaceSourceState.sourceIncluded = patch.sourceIncluded;
  if (Object.hasOwn(patch, "sourceAcquiredBy"))
    workspaceSourceState.sourceAcquiredBy = patch.sourceAcquiredBy;
  if (Object.hasOwn(patch, "uploadedArchive"))
    workspaceSourceState.uploadedArchive = patch.uploadedArchive;
  if (Object.hasOwn(patch, "sourceSnapshotArchive"))
    workspaceSourceState.sourceSnapshotArchive = patch.sourceSnapshotArchive;
  if (Object.hasOwn(patch, "sourceSnapshotCapturedAt"))
    workspaceSourceState.sourceSnapshotCapturedAt = patch.sourceSnapshotCapturedAt;
  if (Object.hasOwn(patch, "runtimeIncluded"))
    artifactStatus.runtimeIncluded = patch.runtimeIncluded;
  if (Object.hasOwn(patch, "downloadableFiles"))
    artifactStatus.downloadableFiles = patch.downloadableFiles;
  if (Object.hasOwn(patch, "sealedAt")) artifactStatus.sealedAt = patch.sealedAt;
  if (Object.hasOwn(patch, "sealHash")) artifactStatus.sealHash = patch.sealHash;
  if (Object.hasOwn(patch, "evalLevel")) evaluationState = { evalLevel: patch.evalLevel ?? 0 };

  return {
    reeSpec: Object.keys(reeSpec).length > 0 ? reeSpec : undefined,
    workspaceSourceState:
      Object.keys(workspaceSourceState).length > 0 ? workspaceSourceState : undefined,
    artifactStatus: Object.keys(artifactStatus).length > 0 ? artifactStatus : undefined,
    evaluationState,
  };
}

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
              ...mapReePatchToSourceOutcome(clearPlan.reePatch),
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
  reePatch: Partial<ReeEditorViewModel>;
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
        ...mapReePatchToSourceOutcome(plan.reePatch),
        sourceSnapshotArchiveName: plan.snapshotArchiveName,
        actionState: plan.actionState,
        badge: plan.badge,
        timestamp: plan.timestamp,
      },
    },
    { type: "toast", message: plan.successMessage, toastType: "success" },
  ];
}
