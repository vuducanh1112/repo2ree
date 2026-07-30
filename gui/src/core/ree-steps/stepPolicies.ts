import type { ReeSpec } from "../ree/ReeSpec";
import type { StepRunOutcome } from "../ree/ReeTypes";
import type { TerminalReeRunFailure } from "../runs/ReeRunStatus";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { ReeStepKey } from "./stepRunParams";
import type { ReeStepRequirement } from "./stepTypes";

const REE_STEP_REQUIREMENTS: Record<ReeStepKey, ReeStepRequirement[]> = {
  evaluate: [{ field: "sourceAvailable", label: "Source loaded in workspace" }],
  build: [{ field: "sourceAvailable", label: "Source available" }],
  hbom: [],
  sbom: [{ field: "runtime", label: "Runtime" }],
  activation: [{ field: "runtime", label: "Runtime" }],
};

const WORKSPACE_REFRESH_STEPS = new Set<ReeStepKey>(["build", "hbom", "sbom"]);
const REE_STEP_KEYS = new Set<ReeStepKey>(["evaluate", "build", "hbom", "sbom", "activation"]);

export function isReeStepKey(key: string): key is ReeStepKey {
  return REE_STEP_KEYS.has(key as ReeStepKey);
}

export function getReeStepRequirements(key: ReeStepKey): ReeStepRequirement[] {
  return REE_STEP_REQUIREMENTS[key];
}

export function missingReeStepRequirements(
  key: ReeStepKey,
  ree: Partial<ReeSpec & WorkspaceSourceState>,
): ReeStepRequirement[] {
  return getReeStepRequirements(key).filter((requirement) => !ree[requirement.field]);
}

export function shouldRefreshWorkspaceAfterStep(key: string): boolean {
  return WORKSPACE_REFRESH_STEPS.has(key as ReeStepKey);
}

export interface StepRunCompletionPlan {
  actionState: "done";
  // The run's terminal outcome, stored on the badge entry — a failed run is
  // still "done" (Re-run appears, cables stay lit) but must not read as earned.
  badge: StepRunOutcome;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface StepRunFailurePlan extends StepRunCompletionPlan {
  errorMessage: string;
}

export function planStepRunCompletion(
  key: string,
  timestamp: string,
  outcome: StepRunOutcome = "succeeded",
): StepRunCompletionPlan {
  return {
    actionState: "done",
    badge: outcome,
    timestamp,
    shouldRefreshWorkspace: shouldRefreshWorkspaceAfterStep(key),
  };
}

export function planTerminalReeRunFailure(
  key: string,
  status: TerminalReeRunFailure,
  timestamp: string,
): StepRunFailurePlan {
  return {
    ...planStepRunCompletion(key, timestamp, status),
    errorMessage: `${key} ${status}`,
  };
}
