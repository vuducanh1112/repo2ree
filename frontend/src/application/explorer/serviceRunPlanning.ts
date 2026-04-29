import { PAGE } from "../../constants/pages";
import type { AutomationStepKey, Ree } from "../../types";
import type { GenericServiceParams } from "../../types/services";
import { planNonWorkflowCompletion } from "./nonWorkflowCompletionPlanning";

type ServiceRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export function buildRemoteServiceRunParams(
  key: string,
  params: GenericServiceParams,
  ree: Ree,
): GenericServiceParams {
  if (key !== "activation") {
    return params;
  }

  return {
    ...params,
    activation_script: ree.activation_script,
  };
}

export function isTerminalServiceRunFailure(
  status: ServiceRunStatus,
): status is Extract<ServiceRunStatus, "failed" | "canceled"> {
  return status === "failed" || status === "canceled";
}

export function shouldRefreshWorkspaceAfterServiceRun(key: string): boolean {
  return key === "build" || key === "sbom" || key === "hbom";
}

export function deriveServiceRunLevel(
  key: string,
  currentLevel: number,
  evaluatedLevel: number,
): number {
  return key === PAGE.EVALUATE ? evaluatedLevel : currentLevel;
}

export function isWorkflowServiceRunKey(key: string): key is AutomationStepKey {
  return (
    key === "evaluate" ||
    key === "hbom" ||
    key === "build" ||
    key === "sbom" ||
    key === "activation"
  );
}

interface ServiceRunCompletionPlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface ServiceRunFailurePlan extends ServiceRunCompletionPlan {
  errorMessage: string;
}

interface ServiceRunSuccessPlan extends ServiceRunCompletionPlan {
  successMessage?: string;
  reePatch?: Partial<Ree>;
  lock?: boolean;
}

interface NonWorkflowCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
}

export function planServiceRunCompletion(key: string, timestamp: string): ServiceRunCompletionPlan {
  return {
    actionState: "done",
    badge: true,
    timestamp,
    shouldRefreshWorkspace: shouldRefreshWorkspaceAfterServiceRun(key),
  };
}

export function planTerminalServiceRunFailure(
  key: string,
  status: Extract<ServiceRunStatus, "failed" | "canceled">,
  timestamp: string,
): ServiceRunFailurePlan {
  return {
    ...planServiceRunCompletion(key, timestamp),
    errorMessage: `${key} ${status}`,
  };
}

export function planNonWorkflowServiceRunSuccess(
  args: NonWorkflowCompletionArgs & { timestamp: string },
): ServiceRunSuccessPlan {
  const nonWorkflowCompletion = planNonWorkflowCompletion(args);
  return {
    ...planServiceRunCompletion(args.key, args.timestamp),
    ...nonWorkflowCompletion,
  };
}
