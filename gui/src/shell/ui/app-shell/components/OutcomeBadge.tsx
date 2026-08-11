import type { ReeStepKey } from "@core/ree-steps/ReeStepParams";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";
import { lgOutcomeBadge } from "../../theme/lightGlassTheme";

/** What a step earned by running successfully: which step, and what it says.
 * The step key is the identity the badge tints from — the chip carries no
 * colour of its own, and neither does the catalog it comes from. */
export interface StepOutcome {
  step: ReeStepKey;
  label: string;
}

/**
 * The earned-outcome chip shown in a step page header once its run has
 * succeeded (e.g. "Built", "Activation passed"). Rendered with role="status"
 * so tests and assistive tech can address the run outcome semantically rather
 * than by matching styled text. The status role names from author only (not
 * from contents), so the label is mirrored into aria-label.
 */
export function OutcomeBadge({ outcome }: { outcome: StepOutcome }) {
  return (
    <span
      role="status"
      aria-label={outcome.label}
      style={lgOutcomeBadge(stageTone(outcome.step), stageTone(outcome.step, "wash"))}
    >
      {Ic.check(11)} {outcome.label}
    </span>
  );
}
