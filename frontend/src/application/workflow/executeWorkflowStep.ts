import type { LogLine, ReeFile } from "../../domain/ree/ReeTypes";
import type { ReeView } from "../../domain/ree/ReeView";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { GenericWorkflowParams } from "./WorkflowStepTypes";
import type { AutomationStepRunParamsByKey } from "./WorkflowTypes";
import { computeEvaluateLevelFromFiles } from "./workflowDependencyAnalysis";
import { isAutomationStepKey } from "./workflowPolicies";
import { buildWorkflowRunRequest } from "./workflowRequests";
import { runWorkflowLifecycle } from "./workflowRunLifecycle";
import {
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
  ree?: ReeView;
}

interface WorkflowRunRunner {
  startWorkflowRun: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  pollRun: (
    runId: string,
    onUpdate?: (update: WorkflowRunResult) => void,
  ) => Promise<WorkflowRunResult>;
}

interface ExecuteWorkflowStepArgs {
  key: string;
  params: GenericWorkflowParams;
  ree: ReeView;
  level: number;
  workspaceFiles: FileTreeNode[];
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
  workspaceFiles,
  workflowRunner,
  workflowStepHandlers,
  generatedIds,
  executeCommands,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteWorkflowStepArgs): Promise<ExecuteWorkflowStepResult> {
  executeCommands([{ type: "setActionLoading", key }]);

  const runRequest = isAutomationStepKey(key)
    ? buildWorkflowRunRequest(key, params as AutomationStepRunParamsByKey[typeof key], ree)
    : { scriptKey: key, params };
  const result = await runWorkflowLifecycle({
    startWorkflowRun: workflowRunner.startWorkflowRun,
    request: {
      key,
      scriptKey: runRequest.scriptKey,
      params: runRequest.params,
    },
    pollRun: workflowRunner.pollRun,
    onRunStarted: (runKey, runId) => {
      executeCommands([{ type: "setActiveRunId", key: runKey, runId }]);
      onRunStarted?.(runKey, runId);
    },
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
        workflowLog: { lines, ts },
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
  params: GenericWorkflowParams,
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
