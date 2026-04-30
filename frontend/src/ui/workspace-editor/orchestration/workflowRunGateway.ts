import type React from "react";
import type {
  WorkflowRunLogEntry,
  WorkspaceBackendGateway,
} from "../../../application/ports/WorkspaceBackendGateway";
import { isAutomationStepKey } from "../../../application/workflow/WorkflowStepDefinitions";
import type { GenericWorkflowParams } from "../../../application/workflow/WorkflowStepTypes";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import type { WorkflowStepHandlerMap } from "../../../application/workflow/workflowStepCommands";
import type { WorkspaceEditorRuntimePorts } from "../../../application/workspace-editor/WorkspaceEditorPorts";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
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
  ree: Ree;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: React.Dispatch<unknown> | WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  persistAutomationStepParams: (key: AutomationStepKey, params: GenericWorkflowParams) => void;
  showToast: ShowToast;
  workflowStepHandlers: WorkflowStepHandlerMap;
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
  ports: WorkspaceEditorRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: Ree;
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
  workspaceService,
  workspaceId,
  ports,
  refreshWorkspace,
  runSession,
}: CreateWorkflowRunGatewayArgs) {
  const executeWorkflowRun = async (
    key: string,
    params: GenericWorkflowParams = {},
  ): Promise<WorkflowRunLogEntry> =>
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
      workspaceService,
      workspaceId,
      ports,
      refreshWorkspace,
      onRunStarted: runSession.noteRunStarted,
      onRunFinished: runSession.noteRunFinished,
    });

  const runWorkflowStep = async (key: string, params: GenericWorkflowParams = {}) => {
    if (isAutomationStepKey(key)) {
      persistAutomationStepParams(key, params);
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
    const cancelWorkflowRun = workspaceService.cancelWorkflowRun;
    const cancelRun = cancelWorkflowRun
      ? (runId: string) => cancelWorkflowRun(workspaceId, runId)
      : undefined;
    const result = await runSession.cancelTrackedRun({
      key,
      cancelRun,
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
