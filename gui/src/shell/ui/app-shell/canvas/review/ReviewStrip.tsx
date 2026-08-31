import { PAGE } from "@core/app-shell/pages";
import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import type { ReviewBasisRequest } from "@core/reviews/Review";
import { REVIEW_STEPS, type ReviewStepKey } from "@core/reviews/reviewDag";
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
      label: shared.label.replace(" Runtime", ""),
      color: stageTone(shared.key),
      icon: stepIcon(shared.iconKey)(14),
    };
  }
  if (key === "source") {
    return { label: "Source", color: stageTone(PAGE.SOURCE), icon: Ic.globe(14) };
  }
  return { label: "Experiments", color: stageTone(PAGE.EXPERIMENTS), icon: Ic.terminal(14) };
}

const STEP_SUBJECT: Record<ReviewStepKey, string> = {
  source: "SWHID",
  build: "runtime · SBOM diff",
  activation: "runtime entry",
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
    hint: "Verify the source and runtime this REE already carries",
  },
];

/**
 * The reviewer's graph, on the same strip the authoring workflow uses.
 *
 * It stands where the authoring steps stand and scrolls the same way, so
 * switching workflows changes what the bar is about rather than how the bar
 * behaves. The evidence each step settles is too big for a 72px strip and
 * opens in the drawer beside the canvas instead.
 */
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

/**
 * Which evidence the next step should rest on.
 *
 * Native radios, not three pressed buttons: the options are exclusive, and
 * anything else reads as three unrelated switches and loses the arrow-key
 * behaviour a group is supposed to have. It sits ahead of the Source step
 * because that is what it governs — where the graph is allowed to start — and
 * the hint for the current choice is spelled out rather than left in a tooltip,
 * since the difference between these options is the difference between an
 * integrity check and a reproduction.
 */
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
