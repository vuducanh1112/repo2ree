import type { ReviewStepKey, ReviewStepStatus } from "@core/reviews/reviewDag";
import type { ReactNode } from "react";
import { Ic } from "../../../shared/components/Icon";
import { cssVars } from "../../../theme/styleVars";
import styles from "./ReviewConsole.module.css";

// What each state is called. How it reads is in ReviewConsole.module.css,
// keyed off the same status value.
const STATUS_LABEL: Record<ReviewStepStatus, string> = {
  unavailable: "Coming next",
  ready: "Ready",
  queued: "Queued",
  running: "Running",
  succeeded: "Complete",
  identical: "Identical",
  equivalent: "Equivalent",
  // The ordinary pass for a result: the author's own verify script accepted it.
  // Distinct from "identical" because matching output bytes are a stronger and
  // rarer thing, and from "complete" because this is a verdict, not a lifecycle
  // state.
  reproduced: "Reproduced",
  different: "Different",
  inconclusive: "Inconclusive",
  // A settled finding, not a breakdown — hence its own label. Coloured like a
  // failure because that is what it means for the reviewer, but the step ran.
  uninhabitable: "Did not activate",
  failed: "Failed",
};

export function ReviewStepButton({
  stepKey,
  label,
  detail,
  icon,
  color,
  status,
  disabled = false,
  onRun,
}: {
  stepKey: ReviewStepKey;
  label: string;
  detail?: string;
  icon: ReactNode;
  color: string;
  status: ReviewStepStatus;
  disabled?: boolean;
  onRun: (step: ReviewStepKey) => void;
}) {
  const active = status === "queued" || status === "running";

  return (
    <button
      type="button"
      onClick={() => onRun(stepKey)}
      aria-label={`Reproduce ${label}`}
      disabled={disabled}
      className={styles.step}
      data-active={active || undefined}
      style={cssVars({ "--step-tint": color })}
    >
      <span aria-hidden className={styles.stepIcon}>
        {active ? Ic.loader(16) : icon}
      </span>
      <span className={styles.stepBody}>
        <span className={styles.stepLabel}>{label}</span>
        {detail ? <span className={styles.stepDetail}>{detail}</span> : null}
        <span className={styles.stepStatus} data-status={status}>
          {STATUS_LABEL[status].toUpperCase()}
        </span>
      </span>
    </button>
  );
}
