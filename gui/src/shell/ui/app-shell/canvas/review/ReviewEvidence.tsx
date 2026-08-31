import type { ReviewAttempt } from "@core/reviews/Review";
import { REVIEW_STEPS, type ReviewStepKey, type ReviewStepStatus } from "@core/reviews/reviewDag";
import { type ReactNode, type Ref, useEffect, useRef } from "react";
import { ExperimentReviewPanel } from "./ExperimentReviewPanel";
import styles from "./ReviewConsole.module.css";
import { STATUS_LABEL } from "./ReviewStepCard";
import type { ReviewWorkflowModel } from "./useReviewWorkflowModel";

const STEP_LABEL: Record<ReviewStepKey, string> = {
  source: "Source",
  build: "Build",
  activation: "Activation",
  experiments: "Experiments",
};

/**
 * Everything one review attempt has settled, in the order the graph settles it.
 *
 * The whole attempt rather than the step that was clicked: evidence accumulates
 * while a reviewer works, and a reader who has to click each step to see what
 * landed cannot watch a reproduction happen. The strip's step decides what is
 * scrolled to and marked current, not what is rendered.
 */
export function ReviewEvidence({
  model,
  focusStep,
}: {
  model: ReviewWorkflowModel;
  focusStep: ReviewStepKey | null;
}) {
  const { attempt, statuses, experimentNames, error } = model;
  const focusRef = useRef<HTMLElement>(null);

  // Re-runs when the strip selects another step, which is the only thing that
  // moves this drawer's attention.
  useEffect(() => {
    if (!focusStep) return;
    focusRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [focusStep]);

  const section = (step: ReviewStepKey, children: ReactNode) => (
    <EvidenceSection
      key={step}
      label={STEP_LABEL[step]}
      status={statuses[step] ?? "ready"}
      current={focusStep === step}
      sectionRef={focusStep === step ? focusRef : undefined}
    >
      {children}
    </EvidenceSection>
  );

  return (
    <div className={styles.evidence}>
      {error ? (
        <div role="alert" className={styles.error}>
          {error instanceof Error ? error.message : "Review unavailable"}
        </div>
      ) : null}

      {attempt ? <BasisNotice attempt={attempt} /> : null}

      {REVIEW_STEPS.map(({ key }) => {
        if (key === "build") {
          return section(
            key,
            attempt?.buildComparison ? <BuildVerdictDetail attempt={attempt} /> : null,
          );
        }
        if (key === "activation") {
          return section(
            key,
            attempt?.activationOutcome ? <ActivationOutcomeDetail attempt={attempt} /> : null,
          );
        }
        if (key === "experiments") {
          return section(
            key,
            <ExperimentReviewPanel
              attempt={attempt}
              experimentNames={experimentNames}
              statuses={statuses}
              sweeping={model.sweeping}
              canRun={model.enabledSteps.has("experiments") && attempt != null}
              onRun={model.runExperiment}
              onRunAll={model.runAllExperiments}
            />,
          );
        }
        return section(key, null);
      })}
    </div>
  );
}

/**
 * One step's findings, or why there are none yet.
 *
 * A step with nothing to show still gets its heading: the drawer answers for
 * the whole graph, and a missing section would read as evidence that was never
 * looked for rather than work not yet done.
 */
function EvidenceSection({
  label,
  status,
  current,
  sectionRef,
  children,
}: {
  label: string;
  status: ReviewStepStatus;
  current: boolean;
  sectionRef?: Ref<HTMLElement>;
  children: ReactNode;
}) {
  const settled =
    status !== "unavailable" && status !== "ready" && status !== "queued" && status !== "running";

  return (
    <section
      ref={sectionRef}
      aria-label={`${label} evidence`}
      className={styles.section}
      data-current={current || undefined}
    >
      <h3 className={styles.sectionHead}>
        <span className={styles.sectionLabel}>{label}</span>
        <span className={styles.sectionStatus} data-status={status}>
          {STATUS_LABEL[status].toUpperCase()}
        </span>
      </h3>
      {children ?? (
        <p className={styles.sectionEmpty}>
          {status === "unavailable"
            ? "Waiting on the step before it."
            : status === "queued" || status === "running"
              ? "Running — the verdict lands here."
              : settled
                ? "Settled with no detail beyond the verdict."
                : "Not reproduced yet."}
        </p>
      )}
    </section>
  );
}

/**
 * States plainly when a settled verdict rests on the REE's own bytes.
 *
 * Without this the console would show "identical" for a bundled attempt exactly
 * as it does for a fetched-and-rebuilt one, and the two mean very different
 * things — the first says the bundle is intact, the second says the work
 * reproduces. The verdict colour is deliberately left alone; this is a
 * qualification of the claim, not a downgrade of it.
 */
function BasisNotice({ attempt }: { attempt: ReviewAttempt }) {
  const bundled: string[] = [];
  if (attempt.sourceComparison?.basis === "bundled") bundled.push("source");
  if (attempt.buildComparison?.basis === "bundled") bundled.push("runtime");
  // Activation inherits its basis, so naming it separately would double-count
  // the same weakness the source or runtime line already reports.
  if (bundled.length === 0) return null;

  return (
    <div className={styles.detail} data-tone="notice">
      {bundled.join(" and ")} verified from the REE's own artifacts — integrity check, not an
      independent reproduction.
    </div>
  );
}

/**
 * What the activation probe settled, and on a failure which half settled it.
 *
 * A run script that never brought the runtime up and a verify script that
 * rejected a runtime which did come up both read as "failed" and call for
 * entirely different work, so the exit codes are shown rather than summarised.
 */
function ActivationOutcomeDetail({ attempt }: { attempt: ReviewAttempt }) {
  const outcome = attempt.activationOutcome;
  if (!outcome) return null;
  const passed = outcome.verdict === "passed";

  return (
    <div className={styles.detail} data-tone={passed ? undefined : "fault"}>
      <span>
        activation: {passed ? "the runtime is inhabitable" : "the runtime did not activate"}
      </span>
      {passed ? null : (
        <span>
          run exited {outcome.runExitCode ?? "?"} · verify{" "}
          {outcome.verifyExitCode == null ? "not run" : `exited ${outcome.verifyExitCode}`}
        </span>
      )}
    </div>
  );
}

/**
 * Why the build earned its verdict. A digest line and a closure line, because
 * "equivalent" is a claim about the dependency closure and a reviewer should
 * see the counts it rests on without opening the run log.
 */
function BuildVerdictDetail({ attempt }: { attempt: ReviewAttempt }) {
  const comparison = attempt.buildComparison;
  if (!comparison) return null;
  const digestsMatch =
    !!comparison.expectedRuntimeDigest &&
    comparison.expectedRuntimeDigest === comparison.observedRuntimeDigest;

  return (
    <div className={styles.detail}>
      <span>
        runtime digest: {digestsMatch ? "bit-identical" : "differs — closure decides the verdict"}
      </span>
      <span>
        closure: {comparison.matched} matched · {comparison.missingCount} missing ·{" "}
        {comparison.extraCount} extra · {comparison.versionMismatchCount} version drift
        {comparison.advisoryCount > 0 ? ` · ${comparison.advisoryCount} advisory` : ""}
      </span>
    </div>
  );
}
