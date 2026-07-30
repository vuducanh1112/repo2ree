import type { RawReeIntentSlices } from "@core/ree/mapRawReeIntent";
import type { LogEntry, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import {
  cancelFailureMessage,
  cancelSuccessMessage,
  planCancelRequest,
} from "@core/ree-steps/cancelPlan";
import type { StepCommandPlannerMap } from "@core/ree-steps/stepCommands";
import { isReeStepKey } from "@core/ree-steps/stepPolicies";
import type { ReeStepKey, ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import type { ReeRun } from "@core/runs/ReeRun";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { AppShellRuntimePorts } from "@shell/app/bootstrap/ports";
import type { ReeRunsClient } from "@shell/data/runs/client";
import { cancelStepRun } from "@shell/ui/app-shell/state/actions";
import type { QueryClient } from "@tanstack/react-query";
import type { ShowToast } from "../types";
import { executeStepRunAction } from "./executeStepRunAction";
import type { ReeEditorDispatch } from "./stepActionEffects";

interface CreateStepRunGatewayArgs {
  ree: ReeEditorViewModel;
  workspaceFiles: FileTreeNode[];
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  persistStepParams: (key: ReeStepKey, params: GenericReeStepParams) => void;
  showToast: ShowToast;
  stepCommandPlanners: StepCommandPlannerMap;
  executionRunsClient: ReeRunsClient;
  reeId: string;
  queryClient: QueryClient;
  startReeRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ReeRun>;
  cancelReeRun?: (runId: string) => Promise<unknown>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: RawReeIntentSlices;
  }>;
  getActiveRunId: (key: string) => string | undefined;
}

export function createStepRunGateway({
  ree,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  persistStepParams,
  showToast,
  stepCommandPlanners,
  executionRunsClient,
  reeId,
  queryClient,
  startReeRun,
  cancelReeRun,
  ports,
  refreshWorkspace,
  getActiveRunId,
}: CreateStepRunGatewayArgs) {
  const executeAction = async (key: string, params: GenericReeStepParams = {}): Promise<LogEntry> =>
    executeStepRunAction({
      key,
      params,
      ree,
      workspaceFiles,
      dispatch,
      persistWorkspaceFile,
      showToast,
      stepCommandPlanners,
      executionRunsClient,
      reeId,
      queryClient,
      startReeRun,
      ports,
      refreshWorkspace,
    });

  const runAction = async (key: string, params: GenericReeStepParams = {}) => {
    if (isReeStepKey(key)) {
      persistStepParams(key, params);
    }
    await executeAction(key, params);
  };

  const runStep = async <K extends ReeStepKey>(
    key: K,
    params: ReeStepRunParams<K>,
  ): Promise<void> => {
    await runAction(key, params);
  };

  const cancelAction = async (key: string) => {
    const plan = planCancelRequest(getActiveRunId(key));
    if (!plan || !cancelReeRun) {
      return;
    }
    try {
      await cancelReeRun(plan.runId);
      showToast(cancelSuccessMessage(key), "info");
      dispatch(cancelStepRun(key, plan.runId));
    } catch (error) {
      showToast(cancelFailureMessage(key, error), "error");
    }
  };

  return {
    executeAction,
    runAction,
    runStep,
    cancelAction,
  };
}
