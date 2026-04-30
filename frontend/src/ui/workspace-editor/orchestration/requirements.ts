import type { Service, ServiceRequire } from "../../../application/workflow/WorkflowStepTypes";
import type { Ree } from "../../../domain/ree/ReeSpec";

/**
 * Return list of service requirements that are not met by the current REE.
 */
export function missingRequirements(svc: Service, ree: Ree): ServiceRequire[] {
  return (svc.requires || []).filter((requiredField) => !ree[requiredField.field]);
}
