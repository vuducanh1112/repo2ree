import type {
  WorkflowDefinition,
  WorkflowRequirement,
} from "../../../application/workflow/WorkflowStepTypes";
import type { Ree } from "../../../domain/ree/ReeSpec";

/**
 * Return list of workflow requirements that are not met by the current REE.
 */
export function missingRequirements(workflow: WorkflowDefinition, ree: Ree): WorkflowRequirement[] {
  return (workflow.requires || []).filter((requiredField) => !ree[requiredField.field]);
}
