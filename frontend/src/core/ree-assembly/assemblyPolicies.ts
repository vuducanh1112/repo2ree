import type { ReeSpec } from "../ree/ReeSpec";
import type { AssemblyRunOutcome } from "../ree/ReeTypes";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { ReeAssemblyRequirement } from "./assemblyStepTypes";
import type { ReeAssemblyOperationKey } from "./assemblyTypes";

type ExecutionRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

const REE_ASSEMBLY_REQUIREMENTS: Record<ReeAssemblyOperationKey, ReeAssemblyRequirement[]> = {
  evaluate: [{ field: "sourceAvailable", label: "Source loaded in workspace" }],
  build: [{ field: "sourceAvailable", label: "Source available" }],
  hbom: [],
  sbom: [{ field: "runtime", label: "Runtime" }],
  activation: [{ field: "runtime", label: "Runtime" }],
};

const WORKSPACE_REFRESH_ASSEMBLY_STEPS = new Set<ReeAssemblyOperationKey>([
  "build",
  "hbom",
  "sbom",
]);
const REE_ASSEMBLY_STEP_KEYS = new Set<ReeAssemblyOperationKey>([
  "evaluate",
  "build",
  "hbom",
  "sbom",
  "activation",
]);

export function isReeAssemblyOperationKey(key: string): key is ReeAssemblyOperationKey {
  return REE_ASSEMBLY_STEP_KEYS.has(key as ReeAssemblyOperationKey);
}

export function getReeAssemblyRequirements(key: ReeAssemblyOperationKey): ReeAssemblyRequirement[] {
  return REE_ASSEMBLY_REQUIREMENTS[key];
}

export function missingReeAssemblyRequirements(
  key: ReeAssemblyOperationKey,
  ree: Partial<ReeSpec & WorkspaceSourceState>,
): ReeAssemblyRequirement[] {
  return getReeAssemblyRequirements(key).filter((requirement) => !ree[requirement.field]);
}

export function isTerminalExecutionRunFailure(
  status: ExecutionRunStatus,
): status is Extract<ExecutionRunStatus, "failed" | "canceled"> {
  return status === "failed" || status === "canceled";
}

export function shouldRefreshWorkspaceAfterAssemblyStep(key: string): boolean {
  return WORKSPACE_REFRESH_ASSEMBLY_STEPS.has(key as ReeAssemblyOperationKey);
}

export interface AssemblyRunCompletionPlan {
  actionState: "done";
  // The run's terminal outcome, stored on the badge entry — a failed run is
  // still "done" (Re-run appears, cables stay lit) but must not read as earned.
  badge: AssemblyRunOutcome;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface AssemblyRunFailurePlan extends AssemblyRunCompletionPlan {
  errorMessage: string;
}

export function planAssemblyRunCompletion(
  key: string,
  timestamp: string,
  outcome: AssemblyRunOutcome = "succeeded",
): AssemblyRunCompletionPlan {
  return {
    actionState: "done",
    badge: outcome,
    timestamp,
    shouldRefreshWorkspace: shouldRefreshWorkspaceAfterAssemblyStep(key),
  };
}

export function planTerminalExecutionRunFailure(
  key: string,
  status: Extract<ExecutionRunStatus, "failed" | "canceled">,
  timestamp: string,
): AssemblyRunFailurePlan {
  return {
    ...planAssemblyRunCompletion(key, timestamp, status),
    errorMessage: `${key} ${status}`,
  };
}
