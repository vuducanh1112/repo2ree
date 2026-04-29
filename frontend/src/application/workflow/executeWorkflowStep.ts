import type {
  AutomationStepRunParamsByKey,
  FileTreeNode,
  LogLine,
  Ree,
  ReeFile,
} from "../../types";
import type { GenericServiceParams } from "../../types/workflowSteps";
import { computeEvaluateLevelFromFiles } from "./workflowDependencyAnalysis";
import { runWorkflowLifecycle } from "./workflowRunLifecycle";
import {
  buildWorkflowRunParams,
  deriveWorkflowStepLevel,
  isTerminalWorkflowRunFailure,
  isWorkflowStepKey,
  planManualArtifactUpdateSuccess,
  planTerminalWorkflowRunFailure,
  planWorkflowRunCompletion,
} from "./workflowRunPolicy";
import {
  nonWorkflowPlanToCommands,
  type WorkflowStepCommand,
  type WorkflowStepHandlerMap,
} from "./workflowStepCommands";

type WorkflowRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface WorkflowRunResult {
  status: WorkflowRunStatus;
  lines: LogLine[];
  ts: string;
}

interface WorkflowWorkspaceSnapshot {
  files: FileTreeNode[];
  reeFiles?: ReeFile[];
  ree?: Ree;
}

interface WorkflowRunRunner {
  startWorkflowRun?: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  pollRun: (
    runId: string,
    onUpdate?: (update: WorkflowRunResult) => void,
  ) => Promise<WorkflowRunResult>;
  createMockResult: () => Promise<WorkflowRunResult>;
}

interface ExecuteWorkflowStepArgs {
  key: string;
  params: GenericServiceParams;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  workflowRunner: WorkflowRunRunner;
  workflowStepHandlers: WorkflowStepHandlerMap;
  generatedIds: {
    swhid: string;
    zenodoDoi: string;
    dataverseDoi: string;
  };
  executeCommands: (commands: WorkflowStepCommand[]) => void;
  refreshWorkspace: () => Promise<WorkflowWorkspaceSnapshot>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

interface ExecuteWorkflowStepResult {
  lines: LogLine[];
  ts: string;
}

export async function executeWorkflowStep({
  key,
  params,
  ree,
  level,
  virtualFiles,
  workflowRunner,
  workflowStepHandlers,
  generatedIds,
  executeCommands,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteWorkflowStepArgs): Promise<ExecuteWorkflowStepResult> {
  executeCommands([{ type: "setActionLoading", key }]);

  const runParams = buildWorkflowRunParams(key, params, ree);
  const result = await runWorkflowLifecycle({
    startWorkflowRun: workflowRunner.startWorkflowRun,
    key,
    runParams,
    pollRun: workflowRunner.pollRun,
    createMockResult: workflowRunner.createMockResult,
    onRunStarted,
    onRunFinished,
    onUpdateLogs: (update) => {
      executeCommands([{ type: "setWorkflowRunLog", key, lines: update.lines, ts: update.ts }]);
    },
  });

  const { lines, ts } = result;
  const completionPlan = planWorkflowRunCompletion(key, ts);
  executeCommands([
    {
      type: "completeWorkflowRun",
      completion: {
        key,
        serviceLog: { lines, ts },
        actionState: completionPlan.actionState,
        badge: completionPlan.badge,
        timestamp: completionPlan.timestamp,
      },
    },
  ]);

  if (isTerminalWorkflowRunFailure(result.status)) {
    const failurePlan = planTerminalWorkflowRunFailure(key, result.status, ts);
    executeCommands([{ type: "toast", message: failurePlan.errorMessage, toastType: "error" }]);
    return { lines, ts };
  }

  if (completionPlan.shouldRefreshWorkspace) {
    try {
      const workspace = await refreshWorkspace();
      executeCommands([
        {
          type: "hydrateWorkspace",
          virtualFiles: workspace.files,
          workspaceReeFiles: workspace.reeFiles || [],
          ree: workspace.ree,
        },
      ]);
    } catch {
      // Keep run success status; UI can still show logs even if refresh fails.
    }
  }

  const evaluatedLevel = computeEvaluateLevelFromFiles(virtualFiles || []);
  const newLevel = deriveWorkflowStepLevel(key, level, evaluatedLevel);

  if (isWorkflowStepKey(key)) {
    executeCommands(getWorkflowStepCommands(workflowStepHandlers, key, params, newLevel));
    return { lines, ts };
  }

  const nonWorkflowPlan = planManualArtifactUpdateSuccess({
    key,
    generatedSwhid: generatedIds.swhid,
    generatedZenodoDoi: generatedIds.zenodoDoi,
    generatedDataverseDoi: generatedIds.dataverseDoi,
    timestamp: ts,
  });
  executeCommands(nonWorkflowPlanToCommands(nonWorkflowPlan));

  return { lines, ts };
}

function getWorkflowStepCommands(
  workflowStepHandlers: WorkflowStepHandlerMap,
  key: keyof WorkflowStepHandlerMap,
  params: GenericServiceParams,
  newLevel: number,
): WorkflowStepCommand[] {
  if (key === "evaluate") {
    return workflowStepHandlers.evaluate(
      params as AutomationStepRunParamsByKey["evaluate"],
      newLevel,
    );
  }
  if (key === "hbom") {
    return workflowStepHandlers.hbom(params as AutomationStepRunParamsByKey["hbom"], newLevel);
  }
  if (key === "build") {
    return workflowStepHandlers.build(params as AutomationStepRunParamsByKey["build"], newLevel);
  }
  if (key === "sbom") {
    return workflowStepHandlers.sbom(params as AutomationStepRunParamsByKey["sbom"], newLevel);
  }
  return workflowStepHandlers.activation(
    params as AutomationStepRunParamsByKey["activation"],
    newLevel,
  );
}
