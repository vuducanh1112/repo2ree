import { PAGE } from "@core/app-shell/pages";
import type { ReviewStepKey } from "@core/generated/vocabulary";
import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import type { ReviewBasisRequest } from "@core/reviews/Review";
import { REVIEW_STEPS } from "@core/reviews/reviewDag";
import { Ic } from "../../../shared/components/Icon";
import { stageTone } from "../../../theme/appearance";
import { stepIcon } from "../../stepIcons";
import styles from "./ReviewConsole.module.css";
import { ReviewStepCard } from "./ReviewStepCard";
import type { ReviewWorkflowModel } from "./useReviewWorkflowModel";

const SHARED_STEP_META = Object.fromEntries(REE_STEPS.map((step) => [step.key, step]));

function presentation(key: ReviewStepKey) {
  const shared = SHARED_STEP_META[key];
  if (shared) {
    return {
      label: shared.label,
      color: stageTone(shared.key),
      icon: stepIcon(shared.iconKey)(14),
    };
  }
  if (key === "acquire_source") {
    return { label: "Source", color: stageTone(PAGE.ACQUIRE_SOURCE), icon: Ic.globe(14) };
  }
  return { label: "Experiments", color: stageTone(PAGE.EXPERIMENTS), icon: Ic.terminal(14) };
}

const STEP_SUBJECT: Record<ReviewStepKey, string> = {
  acquire_source: "SWHID",
  build_experiment_environment: "experiment environment · SBOM diff",
  activate_experiment_environment: "experiment environment entry",
  experiments: "declared experiments",
};

const BASIS_OPTIONS: { value: ReviewBasisRequest; label: string; hint: string }[] = [
  {
    value: "auto",
    label: "Strongest",
    hint: "Fetch the origin and rebuild where the REE allows it",
  },
  {
    value: "independent",
    label: "Independent",
    hint: "Require the origin and a real rebuild; fail if unavailable",
  },
  {
    value: "bundled",
    label: "From bundle",
    hint: "Verify the source and experiment environment this REE already carries",
  },
];

export function ReviewStrip({
  model,
  openStep,
  onOpenStep,
}: {
  model: ReviewWorkflowModel;
  openStep: ReviewStepKey | null;
  onOpenStep: (step: ReviewStepKey) => void;
}) {
  return (
    <nav aria-label="Review workflow" className={styles.scroller}>
      <div className={styles.strip}>
        <BasisPicker value={model.basis} onChange={model.setBasis} disabled={model.running} />

        <ol className={styles.dag}>
          {REVIEW_STEPS.map((step, index) => {
            const meta = presentation(step.key);
            return (
              <li key={step.key} className={styles.item}>
                {index > 0 ? <span aria-hidden className={styles.edge} /> : null}
                <ReviewStepCard
                  stepKey={step.key}
                  label={meta.label}
                  detail={STEP_SUBJECT[step.key]}
                  icon={meta.icon}
                  color={meta.color}
                  status={model.statuses[step.key] ?? "ready"}
                  open={openStep === step.key}
                  disabled={!model.enabledSteps.has(step.key)}
                  onOpen={onOpenStep}
                  onRun={model.invokeStep}
                />
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
}

function BasisPicker({
  value,
  onChange,
  disabled,
}: {
  value: ReviewBasisRequest;
  onChange: (basis: ReviewBasisRequest) => void;
  disabled: boolean;
}) {
  const selected = BASIS_OPTIONS.find((option) => option.value === value) ?? BASIS_OPTIONS[0];

  return (
    <fieldset className={styles.basis}>
      <legend className={styles.basisLegend}>Evidence basis</legend>
      <div className={styles.basisChips}>
        {BASIS_OPTIONS.map((option) => (
          <label key={option.value} title={option.hint} className={styles.basisOption}>
            <input
              type="radio"
              name="review-basis"
              value={option.value}
              checked={option.value === value}
              disabled={disabled}
              onChange={() => onChange(option.value)}
              className={styles.basisInput}
            />
            {option.label}
          </label>
        ))}
      </div>
      <span className={styles.basisHint}>{selected.hint}</span>
    </fieldset>
  );
}
