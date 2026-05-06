import type { ReeAssemblyIconKey } from "../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../shared/components/Icon";

const ASSEMBLY_STEP_ICONS = {
  chip: Ic.chip,
  cpu: Ic.cpu,
  package: Ic.package,
  shield: Ic.shield,
  star: Ic.star,
} as const;

export function assemblyStepIcon(iconKey: ReeAssemblyIconKey) {
  return ASSEMBLY_STEP_ICONS[iconKey];
}
