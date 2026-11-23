import type { ReviewStepKey } from "@core/generated/vocabulary";
import type { ReviewStepStatus } from "@core/reviews/reviewDag";
import type { ReactNode } from "react";
import { Ic } from "../../../shared/components/Icon";
import { cssVars } from "../../../theme/styleVars";
import styles from "./ReviewConsole.module.css";

export const STATUS_LABEL: Record<ReviewStepStatus, string> = {
  unavailable: "Coming next",
  ready: "Ready",
  queued: "Queued",
  running: "Running",
  succeeded: "Complete",
  identical: "Identical",
  equivalent: "Equivalent",
  reproduced: "Reproduced",
  different: "Different",
  inconclusive: "Inconclusive",
  uninhabitable: "Did not activate",
  failed: "Failed",
};

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
