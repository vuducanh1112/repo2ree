import type { Ree } from "../../domain/ree/ReeSpec";
import { planNonWorkflowCompletion } from "../workspace/manualArtifactUpdatePlanning";
import { PAGE } from "../workspace-editor/WorkspaceEditorPages";
import type { GenericWorkflowParams } from "./WorkflowStepTypes";
import type { AutomationStepKey } from "./WorkflowTypes";

type WorkflowRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export function buildWorkflowRunParams(
  key: string,
  params: GenericWorkflowParams,
  ree: Ree,
): GenericWorkflowParams {
  if (key !== "activation") {
    return params;
  }

  return {
    ...params,
    activation_script: ree.activation_script,
  };
}

export function isTerminalWorkflowRunFailure(
  status: WorkflowRunStatus,
): status is Extract<WorkflowRunStatus, "failed" | "canceled"> {
  return status === "failed" || status === "canceled";
}

export function shouldRefreshWorkspaceAfterWorkflowStep(key: string): boolean {
  return key === "build" || key === "sbom" || key === "hbom";
}

export function deriveWorkflowStepLevel(
  key: string,
  currentLevel: number,
  evaluatedLevel: number,
): number {
  return key === PAGE.EVALUATE ? evaluatedLevel : currentLevel;
}

export function isWorkflowStepKey(key: string): key is AutomationStepKey {
  return (
    key === "evaluate" ||
    key === "hbom" ||
    key === "build" ||
    key === "sbom" ||
    key === "activation"
  );
}

interface WorkflowRunCompletionPlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface WorkflowRunFailurePlan extends WorkflowRunCompletionPlan {
  errorMessage: string;
}

interface WorkflowRunSuccessPlan extends WorkflowRunCompletionPlan {
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

export function planWorkflowRunCompletion(
  key: string,
  timestamp: string,
): WorkflowRunCompletionPlan {
  return {
    actionState: "done",
    badge: true,
    timestamp,
    shouldRefreshWorkspace: shouldRefreshWorkspaceAfterWorkflowStep(key),
  };
}

export function planTerminalWorkflowRunFailure(
  key: string,
  status: Extract<WorkflowRunStatus, "failed" | "canceled">,
  timestamp: string,
): WorkflowRunFailurePlan {
  return {
    ...planWorkflowRunCompletion(key, timestamp),
    errorMessage: `${key} ${status}`,
  };
}

export function planManualArtifactUpdateSuccess(
  args: NonWorkflowCompletionArgs & { timestamp: string },
): WorkflowRunSuccessPlan {
  const nonWorkflowCompletion = planNonWorkflowCompletion(args);
  return {
    ...planWorkflowRunCompletion(args.key, args.timestamp),
    ...nonWorkflowCompletion,
  };
}
