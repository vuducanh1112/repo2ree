import type { ReeSpec } from "../ree/ReeSpec";
import { planManualArtifactCompletion } from "../workspace/manualArtifactUpdatePlanning";
import {
  isTerminalReeRunFailure,
  planStepRunCompletion,
  planTerminalReeRunFailure,
  type StepRunCompletionPlan,
  shouldRefreshWorkspaceAfterStep,
} from "./stepPolicies";
import { buildStepRunParams } from "./stepRunRequests";

interface StepRunSuccessPlan extends StepRunCompletionPlan {
  successMessage?: string;
  reeSpecPatch?: Partial<ReeSpec>;
  lock?: boolean;
}

interface NonStepCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
}

export function planManualArtifactUpdateSuccess(
  args: NonStepCompletionArgs & { timestamp: string },
): StepRunSuccessPlan {
  const manualArtifactCompletion = planManualArtifactCompletion(args);
  return {
    ...planStepRunCompletion(args.key, args.timestamp),
    ...manualArtifactCompletion,
  };
}

export {
  buildStepRunParams,
  isTerminalReeRunFailure,
  planStepRunCompletion,
  planTerminalReeRunFailure,
  shouldRefreshWorkspaceAfterStep,
};
