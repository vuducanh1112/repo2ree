import type {
  AutomationStepRunParamsByKey,
  FileTreeNode,
  LogLine,
  Ree,
  ReeFile,
} from "../../types";
import type { GenericServiceParams } from "../../types/services";
import { computeEvaluateLevelFromFiles } from "./dependencyParser";
import {
  nonWorkflowPlanToCommands,
  type ServiceRunCommand,
  type ServiceRunHandlerMap,
} from "./serviceRunCommands";
import {
  buildRemoteServiceRunParams,
  deriveServiceRunLevel,
  isTerminalServiceRunFailure,
  isWorkflowServiceRunKey,
  planNonWorkflowServiceRunSuccess,
  planServiceRunCompletion,
  planTerminalServiceRunFailure,
} from "./serviceRunPlanning";
import { runServiceWorkflow } from "./serviceWorkflow";

type ServiceWorkflowStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface ServiceWorkflowResult {
  status: ServiceWorkflowStatus;
  lines: LogLine[];
  ts: string;
}

interface ServiceWorkspaceSnapshot {
  files: FileTreeNode[];
  reeFiles?: ReeFile[];
  ree?: Ree;
}

interface ServiceRunWorkflowRunner {
  startWorkflowRun?: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  pollRun: (
    runId: string,
    onUpdate?: (update: ServiceWorkflowResult) => void,
  ) => Promise<ServiceWorkflowResult>;
  createMockResult: () => Promise<ServiceWorkflowResult>;
}

interface ExecuteServiceRunUseCaseArgs {
  key: string;
  params: GenericServiceParams;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  workflowRunner: ServiceRunWorkflowRunner;
  serviceRunHandlers: ServiceRunHandlerMap;
  generatedIds: {
    swhid: string;
    zenodoDoi: string;
    dataverseDoi: string;
  };
  executeCommands: (commands: ServiceRunCommand[]) => void;
  refreshWorkspace: () => Promise<ServiceWorkspaceSnapshot>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

interface ExecuteServiceRunUseCaseResult {
  lines: LogLine[];
  ts: string;
}

export async function executeServiceRunUseCase({
  key,
  params,
  ree,
  level,
  virtualFiles,
  workflowRunner,
  serviceRunHandlers,
  generatedIds,
  executeCommands,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteServiceRunUseCaseArgs): Promise<ExecuteServiceRunUseCaseResult> {
  executeCommands([{ type: "setActionLoading", key }]);

  const runParams = buildRemoteServiceRunParams(key, params, ree);
  const result = await runServiceWorkflow({
    startWorkflowRun: workflowRunner.startWorkflowRun,
    key,
    runParams,
    pollRun: workflowRunner.pollRun,
    createMockResult: workflowRunner.createMockResult,
    onRunStarted,
    onRunFinished,
    onUpdateLogs: (update) => {
      executeCommands([{ type: "setServiceLog", key, lines: update.lines, ts: update.ts }]);
    },
  });

  const { lines, ts } = result;
  const completionPlan = planServiceRunCompletion(key, ts);
  executeCommands([
    {
      type: "completeServiceRun",
      completion: {
        key,
        serviceLog: { lines, ts },
        actionState: completionPlan.actionState,
        badge: completionPlan.badge,
        timestamp: completionPlan.timestamp,
      },
    },
  ]);

  if (isTerminalServiceRunFailure(result.status)) {
    const failurePlan = planTerminalServiceRunFailure(key, result.status, ts);
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
  const newLevel = deriveServiceRunLevel(key, level, evaluatedLevel);

  if (isWorkflowServiceRunKey(key)) {
    executeCommands(getWorkflowServiceCommands(serviceRunHandlers, key, params, newLevel));
    return { lines, ts };
  }

  const nonWorkflowPlan = planNonWorkflowServiceRunSuccess({
    key,
    generatedSwhid: generatedIds.swhid,
    generatedZenodoDoi: generatedIds.zenodoDoi,
    generatedDataverseDoi: generatedIds.dataverseDoi,
    timestamp: ts,
  });
  executeCommands(nonWorkflowPlanToCommands(nonWorkflowPlan));

  return { lines, ts };
}

function getWorkflowServiceCommands(
  serviceRunHandlers: ServiceRunHandlerMap,
  key: keyof ServiceRunHandlerMap,
  params: GenericServiceParams,
  newLevel: number,
): ServiceRunCommand[] {
  if (key === "evaluate") {
    return serviceRunHandlers.evaluate(
      params as AutomationStepRunParamsByKey["evaluate"],
      newLevel,
    );
  }
  if (key === "hbom") {
    return serviceRunHandlers.hbom(params as AutomationStepRunParamsByKey["hbom"], newLevel);
  }
  if (key === "build") {
    return serviceRunHandlers.build(params as AutomationStepRunParamsByKey["build"], newLevel);
  }
  if (key === "sbom") {
    return serviceRunHandlers.sbom(params as AutomationStepRunParamsByKey["sbom"], newLevel);
  }
  return serviceRunHandlers.activation(
    params as AutomationStepRunParamsByKey["activation"],
    newLevel,
  );
}
