import type { ReeView } from "../../domain/ree/ReeView";
import { planNonWorkflowCompletion } from "../workspace/manualArtifactUpdatePlanning";
import { planWorkflowRunCompletion } from "./workflowPolicies";

export {
  deriveWorkflowStepLevel,
  isAutomationStepKey as isWorkflowStepKey,
  isTerminalWorkflowRunFailure,
  planTerminalWorkflowRunFailure,
  planWorkflowRunCompletion,
  shouldRefreshWorkspaceAfterWorkflowStep,
} from "./workflowPolicies";
export { buildWorkflowRunParams } from "./workflowRequests";

interface WorkflowRunCompletionPlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface WorkflowRunSuccessPlan extends WorkflowRunCompletionPlan {
  successMessage?: string;
  reePatch?: Partial<ReeView>;
  lock?: boolean;
}

interface NonWorkflowCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
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
