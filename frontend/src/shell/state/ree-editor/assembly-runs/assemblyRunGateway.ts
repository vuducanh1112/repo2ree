import type { ExecutionRun } from "@core/execution/ExecutionRun";
import type { RawReeIntentSlices } from "@core/ree/mapRawReeIntent";
import type { LogEntry, ReeFile } from "@core/ree/ReeTypes";
import type { AssemblyCommandPlannerMap } from "@core/ree-assembly/assemblyCommands";
import { isReeAssemblyOperationKey } from "@core/ree-assembly/assemblyPolicies";
import type { GenericReeAssemblyParams } from "@core/ree-assembly/assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "@core/ree-assembly/assemblyTypes";
import {
  cancelFailureMessage,
  cancelSuccessMessage,
  planCancelRequest,
} from "@core/ree-assembly/cancelPlan";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { AppShellRuntimePorts } from "@shell/app/bootstrap/ports";
import type { ExecutionRunsClient } from "@shell/data/execution-runs/client";
import { cancelAssemblyRun } from "@shell/ui/app-shell/state/actions";
import type { QueryClient } from "@tanstack/react-query";
import type { ShowToast } from "../types";
import type { ReeEditorDispatch } from "./assemblyActionEffects";
import { executeAssemblyRunAction } from "./executeAssemblyRunAction";

interface CreateAssemblyRunGatewayArgs {
  ree: ReeEditorViewModel;
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
    ree?: RawReeIntentSlices;
  }>;
  getActiveRunId: (key: string) => string | undefined;
}

export function createAssemblyRunGateway({
  ree,
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
  getActiveRunId,
}: CreateAssemblyRunGatewayArgs) {
  const executeAction = async (
    key: string,
    params: GenericReeAssemblyParams = {},
  ): Promise<LogEntry> =>
    executeAssemblyRunAction({
      key,
      params,
      ree,
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
    const plan = planCancelRequest(getActiveRunId(key));
    if (!plan || !cancelExecutionRun) {
      return;
    }
    try {
      await cancelExecutionRun(plan.runId);
      showToast(cancelSuccessMessage(key), "info");
      dispatch(cancelAssemblyRun(key, plan.runId));
    } catch (error) {
      showToast(cancelFailureMessage(key, error), "error");
    }
  };

  return {
    executeAction,
    runAction,
    runAssemblyStep,
    cancelAction,
  };
}
