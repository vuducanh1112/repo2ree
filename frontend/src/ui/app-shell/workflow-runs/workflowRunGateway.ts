import type { QueryClient } from "@tanstack/react-query";
import type React from "react";
import type { AppShellRuntimePorts } from "../../../app/bootstrap/ports";
import type { GenericWorkflowParams } from "../../../application/workflow/WorkflowStepTypes";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import { isAutomationStepKey } from "../../../application/workflow/workflowPolicies";
import type { WorkflowStepHandlerMap } from "../../../application/workflow/workflowStepCommands";
import type { WorkflowRunsClient } from "../../../data/workflow-runs/client";
import type { LogEntry, ReeFile } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { WorkflowRunRecord } from "../../../domain/workflow/WorkflowRun";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { WorkspaceWorkflowDispatch } from "./commandExecutors";
import type { ShowToast } from "./types";
import { executeWorkflowRunAction } from "./workflowRuns";

interface RunSessionPort {
  noteRunStarted: (key: string, runId: string) => void;
  noteRunFinished: (key: string) => void;
  cancelTrackedRun: (args: {
    key: string;
    cancelRun?: (runId: string) => Promise<unknown>;
  }) => Promise<{ ok: boolean; message?: string }>;
}

interface CreateWorkflowRunGatewayArgs {
  ree: ReeViewState;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: React.Dispatch<unknown> | WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  persistAutomationStepParams: (key: AutomationStepKey, params: GenericWorkflowParams) => void;
  showToast: ShowToast;
  workflowStepHandlers: WorkflowStepHandlerMap;
  workflowRunsClient: WorkflowRunsClient;
  reeId: string;
  queryClient: QueryClient;
  startWorkflowRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  cancelWorkflowRun?: (runId: string) => Promise<unknown>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: ReeViewState;
  }>;
  runSession: RunSessionPort;
}

export function createWorkflowRunGateway({
  ree,
  level,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  persistAutomationStepParams,
  showToast,
  workflowStepHandlers,
  workflowRunsClient,
  reeId,
  queryClient,
  startWorkflowRun,
  cancelWorkflowRun,
  ports,
  refreshWorkspace,
  runSession,
}: CreateWorkflowRunGatewayArgs) {
  const executeWorkflowRun = async (
    key: string,
    params: GenericWorkflowParams = {},
  ): Promise<LogEntry> =>
    executeWorkflowRunAction({
      key,
      params,
      ree,
      level,
      workspaceFiles,
      dispatch,
      persistWorkspaceFile,
      showToast,
      workflowStepHandlers,
      workflowRunsClient,
      reeId,
      queryClient,
      startWorkflowRun,
      ports,
      refreshWorkspace,
      onRunStarted: runSession.noteRunStarted,
      onRunFinished: runSession.noteRunFinished,
    });

  const runWorkflowStep = async (key: string, params: GenericWorkflowParams = {}) => {
    const automationKey = isAutomationStepKey(key) ? key : null;
    if (automationKey) {
      persistAutomationStepParams(automationKey, params);
    }
    await executeWorkflowRun(key, params);
  };

  const runAutomationStep = async <K extends AutomationStepKey>(
    key: K,
    params: AutomationStepRunParams<K>,
  ): Promise<void> => {
    await runWorkflowStep(key, params);
  };

  const cancelAutomationStep = async (key: string) => {
    const result = await runSession.cancelTrackedRun({
      key,
      cancelRun: cancelWorkflowRun,
    });
    if (result.message) {
      showToast(result.message, result.ok ? "info" : "error");
    }
  };

  return {
    executeWorkflowRun,
    runWorkflowStep,
    runAutomationStep,
    cancelAutomationStep,
  };
}
