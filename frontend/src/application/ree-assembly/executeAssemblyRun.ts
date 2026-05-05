import type { LogLine, ReeFile } from "../../domain/ree/ReeTypes";
import type { ReeView } from "../../domain/ree/ReeView";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import {
  type AssemblyCommand,
  type AssemblyCommandPlannerMap,
  nonAssemblyPlanToCommands,
} from "./assemblyCommands";
import { computeEvaluateLevelFromFiles } from "./assemblyDependencyAnalysis";
import { isReeAssemblyOperationKey } from "./assemblyPolicies";
import { runExecutionLifecycle } from "./assemblyRunLifecycle";
import {
  deriveReeAssemblyStepLevel,
  isTerminalExecutionRunFailure,
  planAssemblyRunCompletion,
  planManualArtifactUpdateSuccess,
  planTerminalExecutionRunFailure,
} from "./assemblyRunPlanning";
import { buildAssemblyRunRequest } from "./assemblyRunRequests";
import type { GenericReeAssemblyParams } from "./assemblyStepTypes";
import type { ReeAssemblyRunParamsByKey } from "./assemblyTypes";

type ExecutionRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface ExecutionRunResult {
  status: ExecutionRunStatus;
  lines: LogLine[];
  ts: string;
}

interface WorkspaceSnapshot {
  files: FileTreeNode[];
  reeFiles?: ReeFile[];
  ree?: ReeView;
}

interface ExecutionRunRunner {
  startExecutionRun: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  pollRun: (
    runId: string,
    onUpdate?: (update: ExecutionRunResult) => void,
  ) => Promise<ExecutionRunResult>;
}

interface ExecuteAssemblyRunArgs {
  key: string;
  params: GenericReeAssemblyParams;
  ree: ReeView;
  level: number;
  workspaceFiles: FileTreeNode[];
  executionRunner: ExecutionRunRunner;
  assemblyCommandPlanners: AssemblyCommandPlannerMap;
  generatedIds: {
    swhid: string;
    zenodoDoi: string;
    dataverseDoi: string;
  };
  executeCommands: (commands: AssemblyCommand[]) => void;
  refreshWorkspace: () => Promise<WorkspaceSnapshot>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

interface ExecuteAssemblyRunResult {
  lines: LogLine[];
  ts: string;
}

export async function executeAssemblyRun({
  key,
  params,
  ree,
  level,
  workspaceFiles,
  executionRunner,
  assemblyCommandPlanners,
  generatedIds,
  executeCommands,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteAssemblyRunArgs): Promise<ExecuteAssemblyRunResult> {
  executeCommands([{ type: "setActionLoading", key }]);

  const runRequest = isReeAssemblyOperationKey(key)
    ? buildAssemblyRunRequest(key, params as ReeAssemblyRunParamsByKey[typeof key], ree)
    : { scriptKey: key, params };
  const result = await runExecutionLifecycle({
    startExecutionRun: executionRunner.startExecutionRun,
    request: {
      key,
      scriptKey: runRequest.scriptKey,
      params: runRequest.params,
    },
    pollRun: executionRunner.pollRun,
    onRunStarted: (runKey, runId) => {
      executeCommands([{ type: "setActiveRunId", key: runKey, runId }]);
      onRunStarted?.(runKey, runId);
    },
    onRunFinished,
    onUpdateLogs: (update) => {
      executeCommands([{ type: "setAssemblyRunLog", key, lines: update.lines, ts: update.ts }]);
    },
  });

  const { lines, ts } = result;
  const completionPlan = planAssemblyRunCompletion(key, ts);
  executeCommands([
    {
      type: "completeAssemblyRun",
      completion: {
        key,
        assemblyRunLog: { lines, ts },
        actionState: completionPlan.actionState,
        badge: completionPlan.badge,
        timestamp: completionPlan.timestamp,
      },
    },
  ]);

  if (isTerminalExecutionRunFailure(result.status)) {
    const failurePlan = planTerminalExecutionRunFailure(key, result.status, ts);
    executeCommands([{ type: "toast", message: failurePlan.errorMessage, toastType: "error" }]);
    return { lines, ts };
  }

  if (completionPlan.shouldRefreshWorkspace) {
    try {
      const workspace = await refreshWorkspace();
      executeCommands([
        {
          type: "hydrateWorkspace",
          workspaceFiles: workspace.files,
          reeArtifactFiles: workspace.reeFiles || [],
          reeSpec: workspace.ree
            ? {
                name: workspace.ree.name,
                origin_url: workspace.ree.origin_url,
                source_type: workspace.ree.source_type,
                runtime: workspace.ree.runtime,
                build_runtime_script: workspace.ree.build_runtime_script,
                activation_script: workspace.ree.activation_script,
                sbom: workspace.ree.sbom,
                swhid: workspace.ree.swhid,
                zenodo_doi: workspace.ree.zenodo_doi,
                dataverse_doi: workspace.ree.dataverse_doi,
                repro_level: workspace.ree.repro_level,
                detected_dependencies: workspace.ree.detected_dependencies,
                hardware_description: workspace.ree.hardware_description,
              }
            : undefined,
          workspaceSourceState: workspace.ree
            ? {
                sourceAvailable: workspace.ree.sourceAvailable,
                sourceIncluded: workspace.ree.sourceIncluded,
                sourceAcquiredBy: workspace.ree.sourceAcquiredBy,
                uploadedArchive: workspace.ree.uploadedArchive,
                sourceSnapshotArchive: workspace.ree.sourceSnapshotArchive,
                sourceSnapshotCapturedAt: workspace.ree.sourceSnapshotCapturedAt,
              }
            : undefined,
          artifactStatus: workspace.ree
            ? {
                runtimeIncluded: workspace.ree.runtimeIncluded,
                downloadableFiles: workspace.ree.downloadableFiles,
                sealedAt: workspace.ree.sealedAt,
                sealHash: workspace.ree.sealHash,
              }
            : undefined,
          evaluationState: workspace.ree ? { evalLevel: workspace.ree.evalLevel } : undefined,
        },
      ]);
    } catch {
      // Keep run success status; UI can still show logs even if refresh fails.
    }
  }

  const evaluatedLevel = computeEvaluateLevelFromFiles(workspaceFiles || []);
  const newLevel = deriveReeAssemblyStepLevel(key, level, evaluatedLevel);

  if (isReeAssemblyOperationKey(key)) {
    executeCommands(getAssemblyCommands(assemblyCommandPlanners, key, params, newLevel));
    return { lines, ts };
  }

  const nonAssemblyPlan = planManualArtifactUpdateSuccess({
    key,
    generatedSwhid: generatedIds.swhid,
    generatedZenodoDoi: generatedIds.zenodoDoi,
    generatedDataverseDoi: generatedIds.dataverseDoi,
    timestamp: ts,
  });
  executeCommands(nonAssemblyPlanToCommands(nonAssemblyPlan));

  return { lines, ts };
}

function getAssemblyCommands(
  planners: AssemblyCommandPlannerMap,
  key: keyof AssemblyCommandPlannerMap,
  params: GenericReeAssemblyParams,
  newLevel: number,
): AssemblyCommand[] {
  if (key === "evaluate") {
    return planners.evaluate(params as ReeAssemblyRunParamsByKey["evaluate"], newLevel);
  }
  if (key === "hbom") {
    return planners.hbom(params as ReeAssemblyRunParamsByKey["hbom"], newLevel);
  }
  if (key === "build") {
    return planners.build(params as ReeAssemblyRunParamsByKey["build"], newLevel);
  }
  if (key === "sbom") {
    return planners.sbom(params as ReeAssemblyRunParamsByKey["sbom"], newLevel);
  }
  return planners.activation(params as ReeAssemblyRunParamsByKey["activation"], newLevel);
}
