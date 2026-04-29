import type React from "react";
import type { ExplorerRuntimePorts } from "../../../../application/explorer/runtimePorts";
import type { ServiceRunHandlerMap } from "../../../../application/explorer/serviceRunCommands";
import { isWorkflowServiceKey } from "../../../../constants/services";
import type {
  IWorkspaceService,
  WorkspaceServiceLogEntry,
} from "../../../../services/workspaceService";
import type {
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ReeFile,
  WorkflowServiceKey,
  WorkflowServiceRunParams,
} from "../../../../types";
import type { ExplorerWorkflowDispatch } from "./commandExecutors";
import { executeServiceRunAction } from "./serviceRuns";
import type { ShowToast } from "./types";

interface WorkflowSessionPort {
  noteRunStarted: (key: string, runId: string) => void;
  noteRunFinished: (key: string) => void;
  cancelTrackedRun: (args: {
    key: string;
    cancelRun?: (runId: string) => Promise<unknown>;
  }) => Promise<{ ok: boolean; message?: string }>;
}

interface CreateServiceRunAdapterArgs {
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  dispatch: React.Dispatch<unknown> | ExplorerWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  persistWorkflowParams: (key: WorkflowServiceKey, params: GenericServiceParams) => void;
  showToast: ShowToast;
  serviceRunHandlers: ServiceRunHandlerMap;
  workspaceService: IWorkspaceService<FileTreeNode>;
  workspaceId: string;
  ports: ExplorerRuntimePorts;
  refreshWorkspace: () => Promise<{
    virtualFiles: FileTreeNode[];
    workspaceReeFiles: ReeFile[];
    ree?: Ree;
  }>;
  workflowSession: WorkflowSessionPort;
}

export function createServiceRunAdapter({
  ree,
  level,
  virtualFiles,
  dispatch,
  persistWorkspaceFile,
  persistWorkflowParams,
  showToast,
  serviceRunHandlers,
  workspaceService,
  workspaceId,
  ports,
  refreshWorkspace,
  workflowSession,
}: CreateServiceRunAdapterArgs) {
  const executeServiceRun = async (
    key: string,
    params: GenericServiceParams = {},
  ): Promise<WorkspaceServiceLogEntry> =>
    executeServiceRunAction({
      key,
      params,
      ree,
      level,
      virtualFiles,
      dispatch,
      persistWorkspaceFile,
      showToast,
      serviceRunHandlers,
      workspaceService,
      workspaceId,
      ports,
      refreshWorkspace,
      onRunStarted: workflowSession.noteRunStarted,
      onRunFinished: workflowSession.noteRunFinished,
    });

  const runAction = async (key: string, params: GenericServiceParams = {}) => {
    if (isWorkflowServiceKey(key)) {
      persistWorkflowParams(key, params);
    }
    await executeServiceRun(key, params);
  };

  const runWorkflowAction = async <K extends WorkflowServiceKey>(
    key: K,
    params: WorkflowServiceRunParams<K>,
  ): Promise<void> => {
    await runAction(key, params);
  };

  const cancelWorkflowAction = async (key: string) => {
    const cancelWorkflowRun = workspaceService.cancelWorkflowRun;
    const cancelRun = cancelWorkflowRun
      ? (runId: string) => cancelWorkflowRun(workspaceId, runId)
      : undefined;
    const result = await workflowSession.cancelTrackedRun({
      key,
      cancelRun,
    });
    if (result.message) {
      showToast(result.message, result.ok ? "info" : "error");
    }
  };

  return {
    executeServiceRun,
    runAction,
    runWorkflowAction,
    cancelWorkflowAction,
  };
}
