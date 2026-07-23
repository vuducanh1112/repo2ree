import type { RawReeIntentSlices } from "../ree/mapRawReeIntent";
import type { ReeSpec } from "../ree/ReeSpec";
import type { LogLine, ReeFile } from "../ree/ReeTypes";
import { isTerminalReeRunFailure, type ReeRunStatus } from "../runs/ReeRunStatus";
import type { FileTreeNode } from "../workspace/FileTree";
import {
  nonStepPlanToCommands,
  type StepCommand,
  type StepCommandPlannerMap,
} from "./stepCommands";
import { isReeStepKey } from "./stepPolicies";
import { runExecutionLifecycle } from "./stepRunLifecycle";
import type { ReeStepRunParamsByKey } from "./stepRunParams";
import {
  planManualArtifactUpdateSuccess,
  planStepRunCompletion,
  planTerminalReeRunFailure,
} from "./stepRunPlanning";
import { buildStepRunRequest } from "./stepRunRequests";
import type { GenericReeStepParams } from "./stepTypes";

interface ReeRunPollResult {
  status: ReeRunStatus;
  lines: LogLine[];
  ts: string;
}

interface WorkspaceSnapshot {
  files: FileTreeNode[];
  reeFiles?: ReeFile[];
  ree?: RawReeIntentSlices;
}

interface ReeRunRunner {
  startReeRun: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  pollRun: (
    runId: string,
    onUpdate?: (update: ReeRunPollResult) => void,
  ) => Promise<ReeRunPollResult>;
}

interface ExecuteStepRunArgs {
  key: string;
  params: GenericReeStepParams;
  ree: Pick<ReeSpec, "runtime">;
  workspaceFiles: FileTreeNode[];
  executionRunner: ReeRunRunner;
  stepCommandPlanners: StepCommandPlannerMap;
  generatedIds: {
    swhid: string;
    zenodoDoi: string;
    dataverseDoi: string;
  };
  executeCommands: (commands: StepCommand[]) => void;
  refreshWorkspace: () => Promise<WorkspaceSnapshot>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string, runId: string) => void;
}

interface ExecuteStepRunResult {
  lines: LogLine[];
  ts: string;
}

export async function executeStepRun({
  key,
  params,
  ree,
  executionRunner,
  stepCommandPlanners,
  generatedIds,
  executeCommands,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteStepRunArgs): Promise<ExecuteStepRunResult> {
  executeCommands([{ type: "setActionLoading", key }]);

  const runRequest = isReeStepKey(key)
    ? buildStepRunRequest(key, params as ReeStepRunParamsByKey[typeof key], ree)
    : { scriptKey: key, params };
  const result = await runExecutionLifecycle({
    startReeRun: executionRunner.startReeRun,
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
      executeCommands([{ type: "setStepRunLog", key, lines: update.lines, ts: update.ts }]);
    },
  });

  const { lines, ts } = result;
  const completionPlan = planStepRunCompletion(
    key,
    ts,
    isTerminalReeRunFailure(result.status) ? result.status : "succeeded",
  );
  executeCommands([
    {
      type: "completeStepRun",
      completion: {
        key,
        runId: result.runId,
        stepRunLog: { lines, ts },
        actionState: completionPlan.actionState,
        badge: completionPlan.badge,
        timestamp: completionPlan.timestamp,
      },
    },
  ]);

  if (isTerminalReeRunFailure(result.status)) {
    const failurePlan = planTerminalReeRunFailure(key, result.status, ts);
    executeCommands([{ type: "toast", message: failurePlan.errorMessage, toastType: "error" }]);
    if (failurePlan.shouldRefreshWorkspace) {
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
        // Best-effort; UI can still show logs even if refresh fails.
      }
    }
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

  if (isReeStepKey(key)) {
    executeCommands(getStepCommands(stepCommandPlanners, key, params));
    return { lines, ts };
  }

  const nonStepPlan = planManualArtifactUpdateSuccess({
    key,
    generatedSwhid: generatedIds.swhid,
    generatedZenodoDoi: generatedIds.zenodoDoi,
    generatedDataverseDoi: generatedIds.dataverseDoi,
    timestamp: ts,
  });
  executeCommands(nonStepPlanToCommands(nonStepPlan));

  return { lines, ts };
}

function getStepCommands(
  planners: StepCommandPlannerMap,
  key: keyof StepCommandPlannerMap,
  params: GenericReeStepParams,
): StepCommand[] {
  if (key === "evaluate") {
    return planners.evaluate(params as ReeStepRunParamsByKey["evaluate"]);
  }
  if (key === "hbom") {
    return planners.hbom(params as ReeStepRunParamsByKey["hbom"]);
  }
  if (key === "build") {
    return planners.build(params as ReeStepRunParamsByKey["build"]);
  }
  if (key === "sbom") {
    return planners.sbom(params as ReeStepRunParamsByKey["sbom"]);
  }
  return planners.activation(params as ReeStepRunParamsByKey["activation"]);
}
