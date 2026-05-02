import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import { PAGE } from "../app-shell/AppShellPages";
import type { WorkflowRequirement } from "./WorkflowStepTypes";
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

const WORKFLOW_REQUIREMENTS: Record<AutomationStepKey, WorkflowRequirement[]> = {
  evaluate: [{ field: "sourceAvailable", label: "Source loaded in workspace" }],
  build: [
    { field: "sourceAvailable", label: "Source available" },
    { field: "build_runtime_script", label: "Build script" },
  ],
  hbom: [],
  sbom: [{ field: "runtime", label: "Runtime" }],
  activation: [{ field: "activation_script", label: "Activation script" }],
};

const WORKSPACE_REFRESH_STEPS = new Set<AutomationStepKey>(["build", "hbom", "sbom"]);
const WORKFLOW_STEP_KEYS = new Set<AutomationStepKey>([
  "evaluate",
  "build",
  "hbom",
  "sbom",
  "activation",
]);

export function isAutomationStepKey(key: string): key is AutomationStepKey {
  return WORKFLOW_STEP_KEYS.has(key as AutomationStepKey);
}

export function getWorkflowRequirements(key: AutomationStepKey): WorkflowRequirement[] {
  return WORKFLOW_REQUIREMENTS[key];
}

export function missingWorkflowRequirements(
  key: AutomationStepKey,
  ree: ReeDraftViewModel,
): WorkflowRequirement[] {
  return getWorkflowRequirements(key).filter((requirement) => !ree[requirement.field]);
}

export function isTerminalWorkflowRunFailure(
  status: WorkflowRunStatus,
): status is Extract<WorkflowRunStatus, "failed" | "canceled"> {
  return status === "failed" || status === "canceled";
}

export function shouldRefreshWorkspaceAfterWorkflowStep(key: string): boolean {
  return WORKSPACE_REFRESH_STEPS.has(key as AutomationStepKey);
}

export function deriveWorkflowStepLevel(
  key: string,
  currentLevel: number,
  evaluatedLevel: number,
): number {
  return key === PAGE.EVALUATE ? evaluatedLevel : currentLevel;
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
