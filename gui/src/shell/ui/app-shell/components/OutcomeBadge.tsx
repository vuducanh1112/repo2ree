import type { ReeStepKey } from "@core/ree-steps/ReeStepParams";
import { Badge } from "../../shared/components/Badge";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";

export interface StepOutcome {
  step: ReeStepKey;
  label: string;
}

export function OutcomeBadge({ outcome }: { outcome: StepOutcome }) {
  return (
    <Badge
      role="status"
      aria-label={outcome.label}
      icon={Ic.check(11)}
      tint={{
        ink: stageTone(outcome.step, "ink"),
        line: stageTone(outcome.step),
        wash: stageTone(outcome.step, "wash"),
      }}
    >
      {outcome.label}
    </Badge>
  );
}
