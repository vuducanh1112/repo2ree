import type { QueryClient } from "@tanstack/react-query";
import type { ExecutionRun } from "../../../core/execution/ExecutionRun";
import type { RawReeDraftSlices } from "../../../core/ree/mapRawReeDraft";
import type { LogEntry, ReeFile } from "../../../core/ree/ReeTypes";
import type { AssemblyCommandPlannerMap } from "../../../core/ree-assembly/assemblyCommands";
import { isReeAssemblyOperationKey } from "../../../core/ree-assembly/assemblyPolicies";
import type { GenericReeAssemblyParams } from "../../../core/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../core/ree-assembly/assemblyTypes";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import type { ExecutionRunsClient } from "../../../data/execution-runs/client";
import type { AppShellRuntimePorts } from "../../../shell/app/bootstrap/ports";
import type { ShowToast } from "../types";
import type { ReeEditorDispatch } from "./assemblyActionEffects";
import { executeAssemblyRunAction } from "./executeAssemblyRunAction";

interface RunSessionPort {
  noteRunStarted: (key: string, runId: string) => void;
  noteRunFinished: (key: string) => void;
  cancelTrackedRun: (args: {
    key: string;
    cancelRun?: (runId: string) => Promise<unknown>;
  }) => Promise<{ ok: boolean; message?: string }>;
}

interface CreateAssemblyRunGatewayArgs {
  ree: ReeEditorViewModel;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  persistAssemblyParams: (key: ReeAssemblyOperationKey, params: GenericReeAssemblyParams) => void;
  showToast: ShowToast;
  assemblyCommandPlanners: AssemblyCommandPlannerMap;
  executionRunsClient: ExecutionRunsClient;
  reeId: string;
  queryClient: QueryClient;
  startExecutionRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ExecutionRun>;
  cancelExecutionRun?: (runId: string) => Promise<unknown>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: RawReeDraftSlices;
  }>;
  runSession: RunSessionPort;
}

export function createAssemblyRunGateway({
  ree,
  level,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  persistAssemblyParams,
  showToast,
  assemblyCommandPlanners,
  executionRunsClient,
  reeId,
  queryClient,
  startExecutionRun,
  cancelExecutionRun,
  ports,
  refreshWorkspace,
  runSession,
}: CreateAssemblyRunGatewayArgs) {
  const executeAction = async (
    key: string,
    params: GenericReeAssemblyParams = {},
  ): Promise<LogEntry> =>
    executeAssemblyRunAction({
      key,
      params,
      ree,
      level,
      workspaceFiles,
      dispatch,
      persistWorkspaceFile,
      showToast,
      assemblyCommandPlanners,
      executionRunsClient,
      reeId,
      queryClient,
      startExecutionRun,
      ports,
      refreshWorkspace,
      onRunStarted: runSession.noteRunStarted,
      onRunFinished: runSession.noteRunFinished,
    });

  const runAction = async (key: string, params: GenericReeAssemblyParams = {}) => {
    if (isReeAssemblyOperationKey(key)) {
      persistAssemblyParams(key, params);
    }
    await executeAction(key, params);
  };

  const runAssemblyStep = async <K extends ReeAssemblyOperationKey>(
    key: K,
    params: ReeAssemblyRunParams<K>,
  ): Promise<void> => {
    await runAction(key, params);
  };

  const cancelAction = async (key: string) => {
    const result = await runSession.cancelTrackedRun({
      key,
      cancelRun: cancelExecutionRun,
    });
    if (result.message) {
      showToast(result.message, result.ok ? "info" : "error");
    }
  };

  return {
    executeAction,
    runAction,
    runAssemblyStep,
    cancelAction,
  };
}
