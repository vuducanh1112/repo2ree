import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import { planNonWorkflowCompletion } from "../workspace/manualArtifactUpdatePlanning";
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
  reePatch?: Partial<ReeEditorViewModel>;
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
  const nonWorkflowCompletion = planNonWorkflowCompletion(args);
  return {
    ...planAssemblyRunCompletion(args.key, args.timestamp),
    ...nonWorkflowCompletion,
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
