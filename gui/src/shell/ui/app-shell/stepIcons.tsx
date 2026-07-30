import type { ReeStepIconKey } from "@core/ree-steps/stepTypes";
import { Ic } from "../shared/components/Icon";

const STEP_ICONS = {
  chip: Ic.chip,
  cpu: Ic.cpu,
  package: Ic.package,
  shield: Ic.shield,
  star: Ic.star,
} as const;

export function stepIcon(iconKey: ReeStepIconKey) {
  return STEP_ICONS[iconKey];
}
