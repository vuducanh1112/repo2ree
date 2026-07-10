import type { ReeAssemblyBadge } from "@core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../shared/components/Icon";
import { lgOutcomeBadge } from "../../theme/lightGlassTheme";

/**
 * The earned-outcome chip shown in an assembly page header once its run has
 * succeeded (e.g. "Built", "Activation passed"). Rendered with role="status"
 * so tests and assistive tech can address the run outcome semantically rather
 * than by matching styled text. The status role names from author only (not
 * from contents), so the label is mirrored into aria-label.
 */
export function OutcomeBadge({ badge }: { badge: ReeAssemblyBadge }) {
  return (
    <span role="status" aria-label={badge.label} style={lgOutcomeBadge(badge.color, badge.bg)}>
      {Ic.check(11)} {badge.label}
    </span>
  );
}
