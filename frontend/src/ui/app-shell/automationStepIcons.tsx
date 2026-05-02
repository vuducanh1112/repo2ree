import type { AutomationStepIconKey } from "../../application/workflow/WorkflowStepTypes";
import { Ic } from "../shared/components/Icon";

const AUTOMATION_STEP_ICONS = {
  chip: Ic.chip,
  cpu: Ic.cpu,
  package: Ic.package,
  shield: Ic.shield,
  star: Ic.star,
} as const;

export function automationStepIcon(iconKey: AutomationStepIconKey) {
  return AUTOMATION_STEP_ICONS[iconKey];
}
