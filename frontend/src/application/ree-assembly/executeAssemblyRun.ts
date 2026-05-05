import type { RawReeDraftSlices } from "../../domain/ree/mapRawReeDraft";
import type { LogLine, ReeFile } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
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
  ree?: RawReeDraftSlices;
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
  ree: ReeEditorViewModel;
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
          reeSpec: workspace.ree?.reeSpec,
          workspaceSourceState: workspace.ree?.workspaceSourceState,
          artifactStatus: workspace.ree?.artifactStatus,
          evaluationState: workspace.ree?.evaluationState,
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
