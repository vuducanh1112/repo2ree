import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
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
  build: [
    { field: "sourceAvailable", label: "Source available" },
    { field: "build_runtime_script", label: "Build script" },
  ],
  hbom: [],
  sbom: [{ field: "runtime", label: "Runtime" }],
  activation: [
    { field: "runtime", label: "Runtime" },
    { field: "activation_script", label: "Activation script" },
  ],
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
  ree: ReeEditorViewModel,
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

export function deriveReeAssemblyStepLevel(
  key: string,
  currentLevel: number,
  evaluatedLevel: number,
): number {
  return key === "evaluate" ? evaluatedLevel : currentLevel;
}

interface AssemblyRunCompletionPlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface AssemblyRunFailurePlan extends AssemblyRunCompletionPlan {
  errorMessage: string;
}

export function planAssemblyRunCompletion(
  key: string,
  timestamp: string,
): AssemblyRunCompletionPlan {
  return {
    actionState: "done",
    badge: true,
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
    ...planAssemblyRunCompletion(key, timestamp),
    errorMessage: `${key} ${status}`,
  };
}
