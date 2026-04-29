import type React from "react";
import type { ExplorerRuntimePorts } from "../../../../application/explorer/runtimePorts";
import type { ServiceRunHandlerMap } from "../../../../application/explorer/serviceRunCommands";
import { isAutomationStepKey } from "../../../../constants/services";
import type {
  IWorkspaceService,
  WorkspaceServiceLogEntry,
} from "../../../../services/workspaceService";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ReeFile,
} from "../../../../types";
import type { ExplorerWorkflowDispatch } from "./commandExecutors";
import { executeServiceRunAction } from "./serviceRuns";
import type { ShowToast } from "./types";

interface RunSessionPort {
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
  persistAutomationStepParams: (key: AutomationStepKey, params: GenericServiceParams) => void;
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
  runSession: RunSessionPort;
}

export function createServiceRunAdapter({
  ree,
  level,
  virtualFiles,
  dispatch,
  persistWorkspaceFile,
  persistAutomationStepParams,
  showToast,
  serviceRunHandlers,
  workspaceService,
  workspaceId,
  ports,
  refreshWorkspace,
  runSession,
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
      onRunStarted: runSession.noteRunStarted,
      onRunFinished: runSession.noteRunFinished,
    });

  const runAction = async (key: string, params: GenericServiceParams = {}) => {
    if (isAutomationStepKey(key)) {
      persistAutomationStepParams(key, params);
    }
    await executeServiceRun(key, params);
  };

  const runAutomationStep = async <K extends AutomationStepKey>(
    key: K,
    params: AutomationStepRunParams<K>,
  ): Promise<void> => {
    await runAction(key, params);
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
    executeServiceRun,
    runAction,
    runAutomationStep,
    cancelAutomationStep,
  };
}
