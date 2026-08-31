import type { ReviewStepKey, ReviewStepStatus } from "@core/reviews/reviewDag";
import type { ReactNode } from "react";
import { Ic } from "../../../shared/components/Icon";
import { cssVars } from "../../../theme/styleVars";
import styles from "./ReviewConsole.module.css";

// What each state is called, for every surface that names one. How it reads is
// in ReviewConsole.module.css, keyed off the same status value.
export const STATUS_LABEL: Record<ReviewStepStatus, string> = {
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

/**
 * One step of the review graph, at strip size.
 *
 * Two controls rather than one. Reading a verdict and dispatching a ten-minute
 * rebuild are different acts and should not share a hitbox: the face opens the
 * step's evidence, and the run key beside it starts the work. What the step
 * reproduces from — "SWHID", "runtime · SBOM diff" — rides on the face's
 * accessible name, because the strip has room for the verdict or the subject
 * and the verdict is the reason to look.
 */
export function ReviewStepCard({
  stepKey,
  label,
  detail,
  icon,
  color,
  status,
  open,
  disabled = false,
  onOpen,
  onRun,
}: {
  stepKey: ReviewStepKey;
  label: string;
  detail?: string;
  icon: ReactNode;
  color: string;
  status: ReviewStepStatus;
  /** This step's evidence is the section the drawer is showing. */
  open: boolean;
  disabled?: boolean;
  onOpen: (step: ReviewStepKey) => void;
  onRun: (step: ReviewStepKey) => void;
}) {
  const active = status === "queued" || status === "running";

  return (
    <div
      className={styles.step}
      data-active={active || undefined}
      data-open={open || undefined}
      style={cssVars({ "--step-tint": color })}
    >
      <button
        type="button"
        onClick={() => onOpen(stepKey)}
        aria-current={open ? "step" : undefined}
        aria-label={`Open ${label} review evidence, ${STATUS_LABEL[status].toLowerCase()}${
          detail ? `, ${detail}` : ""
        }`}
        className={styles.stepFace}
      >
        <span aria-hidden className={styles.stepIcon}>
          {active ? Ic.loader(14) : icon}
        </span>
        <span className={styles.stepLabel}>{label}</span>
        <span className={styles.stepStatus} data-status={status}>
          {STATUS_LABEL[status].toUpperCase()}
        </span>
      </button>

      <button
        type="button"
        onClick={() => onRun(stepKey)}
        aria-label={`Reproduce ${label}`}
        disabled={disabled}
        className={styles.stepRun}
      >
        <span aria-hidden>{Ic.play(11)}</span>
      </button>
    </div>
  );
}
