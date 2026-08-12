import type { ReviewAttempt, ReviewExperimentComparison } from "@core/reviews/Review";
import type { ReviewStepKey, ReviewStepStatus } from "@core/reviews/reviewDag";
import { experimentReviewStatus, reproducedExperimentCount } from "@core/reviews/reviewStatuses";
import { Ic } from "../../../shared/components/Icon";
import styles from "./ReviewConsole.module.css";

// What each verdict is called; ReviewConsole.module.css decides how it reads.
const VERDICT_LABEL: Partial<Record<ReviewStepStatus, string>> = {
  ready: "Ready",
  queued: "Queued",
  running: "Running",
  identical: "Identical",
  reproduced: "Reproduced",
  different: "Different",
  inconclusive: "Inconclusive",
  unavailable: "Locked",
};

/**
 * Per-experiment reproduction, plus a sweep over all of them.
 *
 * A list rather than one button because an REE's experiments are independent
 * claims: a reviewer reproducing a paper's headline result should not have to
 * sit through five others, and a verdict that differs belongs to *one*
 * experiment rather than to the step. "Run all" is a convenience over the same
 * per-experiment path — it dispatches them one at a time, because they share a
 * workspace and concurrent runs would interleave their output files.
 */
export function ExperimentReviewPanel({
  attempt,
  experimentNames,
  statuses,
  sweeping,
  canRun,
  onRun,
  onRunAll,
}: {
  attempt: ReviewAttempt | undefined;
  experimentNames: readonly string[];
  statuses: Readonly<Record<ReviewStepKey, ReviewStepStatus>>;
  sweeping: boolean;
  canRun: boolean;
  onRun: (experimentName: string) => void;
  onRunAll: () => void;
}) {
  if (experimentNames.length === 0) return null;
  // What reproduced, not what ran: an experiment that came back `different` has
  // a verdict but is not a success, and this counter carries the word
  // "reproduced" next to it.
  const reproduced = reproducedExperimentCount(attempt);

  return (
    <div className={styles.results}>
      <div className={styles.resultsHead}>
        <span className={styles.resultsCount}>
          RESULTS · {reproduced}/{experimentNames.length} REPRODUCED
        </span>
        <button
          type="button"
          onClick={onRunAll}
          disabled={!canRun || sweeping}
          aria-label="Reproduce all experiments"
          className={styles.runAll}
        >
          {sweeping ? Ic.loader(12) : Ic.play(12)}
          <span>{sweeping ? "Running all" : "Run all"}</span>
        </button>
      </div>

      {experimentNames.map((name) => (
        <ExperimentRow
          key={name}
          name={name}
          status={experimentReviewStatus(attempt, name, statuses)}
          comparison={attempt?.experimentComparisons.find((entry) => entry.experimentName === name)}
          canRun={canRun && !sweeping}
          onRun={onRun}
        />
      ))}
    </div>
  );
}

function ExperimentRow({
  name,
  status,
  comparison,
  canRun,
  onRun,
}: {
  name: string;
  status: ReviewStepStatus;
  comparison: ReviewExperimentComparison | undefined;
  canRun: boolean;
  onRun: (experimentName: string) => void;
}) {
  const label = VERDICT_LABEL[status] ?? status;
  const disabled = !canRun || status === "unavailable" || status === "running";

  return (
    <div className={styles.experiment}>
      <span className={styles.experimentName} title={name}>
        {name}
      </span>
      {comparison ? <CriterionNote comparison={comparison} /> : null}
      <span className={styles.verdict} data-status={status}>
        {label.toUpperCase()}
      </span>
      <button
        type="button"
        onClick={() => onRun(name)}
        disabled={disabled}
        aria-label={`Reproduce experiment ${name}`}
        className={styles.runOne}
      >
        {comparison ? "Re-run" : "Run"}
      </button>
    </div>
  );
}

/**
 * What the verdict rests on, in the one line there is room for.
 *
 * A `reproduced` verdict is worth exactly as much as the verify script that
 * granted it, so the script is named rather than hidden — and an experiment
 * that declares none says so, since that is why its verdict is inconclusive
 * rather than a pass.
 */
function CriterionNote({ comparison }: { comparison: ReviewExperimentComparison }) {
  const criterion = comparison.verifyScriptPath.trim();
  const note = !criterion
    ? "no verify script"
    : comparison.expectedVerifyExitCode == null
      ? "no author baseline"
      : comparison.expectedVerifyScriptDigest == null
        ? "author criterion unbound"
        : comparison.verifyScriptDigest !== comparison.expectedVerifyScriptDigest
          ? "criterion changed"
          : criterion;

  return (
    <span
      className={styles.criterion}
      title={
        criterion
          ? `criterion: ${criterion}${
              comparison.verifyScriptDigest ? ` (${comparison.verifyScriptDigest})` : ""
            }`
          : "this experiment declares no verify script, so nothing states what a correct result is"
      }
    >
      {note}
    </span>
  );
}
