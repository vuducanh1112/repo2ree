import type { ReeSpec } from "../../core/ree/ReeSpec";
import { planManualArtifactCompletion } from "../workspace/manualArtifactUpdatePlanning";
import {
  deriveReeAssemblyStepLevel,
  isTerminalExecutionRunFailure,
  planAssemblyRunCompletion,
  planTerminalExecutionRunFailure,
  shouldRefreshWorkspaceAfterAssemblyStep,
} from "./assemblyPolicies";
import { buildAssemblyRunParams } from "./assemblyRunRequests";

interface AssemblyRunCompletionPlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface AssemblyRunSuccessPlan extends AssemblyRunCompletionPlan {
  successMessage?: string;
  reeSpecPatch?: Partial<ReeSpec>;
  lock?: boolean;
}

interface NonAssemblyCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
}

export function planManualArtifactUpdateSuccess(
  args: NonAssemblyCompletionArgs & { timestamp: string },
): AssemblyRunSuccessPlan {
  const manualArtifactCompletion = planManualArtifactCompletion(args);
  return {
    ...planAssemblyRunCompletion(args.key, args.timestamp),
    ...manualArtifactCompletion,
  };
}

export {
  buildAssemblyRunParams,
  deriveReeAssemblyStepLevel,
  isTerminalExecutionRunFailure,
  planAssemblyRunCompletion,
  planTerminalExecutionRunFailure,
  shouldRefreshWorkspaceAfterAssemblyStep,
};
