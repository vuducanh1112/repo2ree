import type { ReeRunOperation } from "@core/generated/vocabulary";
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
    operation: ReeRunOperation,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  pollRun: (
    runId: string,
    onUpdate?: (update: ReeRunPollResult) => void,
  ) => Promise<ReeRunPollResult>;
}

interface ExecuteStepRunArgs {
  key: ReeRunOperation;
  params: GenericReeStepParams;
  ree: Pick<ReeSpec, "experimentEnvironmentPath">;
  workspaceFiles: FileTreeNode[];
  executionRunner: ReeRunRunner;
  stepCommandPlanners: StepCommandPlannerMap;
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
      } catch {}
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
    } catch {}
  }

  if (isReeStepKey(key)) {
    executeCommands(getStepCommands(stepCommandPlanners, key, params));
    return { lines, ts };
  }

  const nonStepPlan = planManualArtifactUpdateSuccess({ key, timestamp: ts });
  executeCommands(nonStepPlanToCommands(nonStepPlan));

  return { lines, ts };
}

function getStepCommands(
  planners: StepCommandPlannerMap,
  key: keyof StepCommandPlannerMap,
  params: GenericReeStepParams,
): StepCommand[] {
  if (key === "evaluate_reproducibility") {
    return planners.evaluate_reproducibility(
      params as ReeStepRunParamsByKey["evaluate_reproducibility"],
    );
  }
  if (key === "observe_hardware") {
    return planners.observe_hardware(params as ReeStepRunParamsByKey["observe_hardware"]);
  }
  if (key === "build_experiment_environment") {
    return planners.build_experiment_environment(
      params as ReeStepRunParamsByKey["build_experiment_environment"],
    );
  }
  if (key === "generate_sbom") {
    return planners.generate_sbom(params as ReeStepRunParamsByKey["generate_sbom"]);
  }
  return planners.activate_experiment_environment(
    params as ReeStepRunParamsByKey["activate_experiment_environment"],
  );
}
