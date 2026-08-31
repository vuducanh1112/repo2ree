import type { ReeStepKey } from "@core/ree-steps/ReeStepParams";
import { Badge } from "../../shared/components/Badge";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";

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
    <Badge
      role="status"
      aria-label={outcome.label}
      icon={Ic.check(11)}
      tint={{
        // The deep shade for the words: a stage's `line` is a mid tone for
        // rules and glyphs, and 12px bold text of it on the stage's own wash
        // lands as low as 3.1:1 where WCAG asks for 4.5:1.
        ink: stageTone(outcome.step, "ink"),
        line: stageTone(outcome.step),
        wash: stageTone(outcome.step, "wash"),
      }}
    >
      {outcome.label}
    </Badge>
  );
}
