import type { ReviewStepKey } from "@core/generated/vocabulary";
import type { ReviewAttempt } from "@core/reviews/Review";
import { REVIEW_STEPS, type ReviewStepStatus, reviewStep } from "@core/reviews/reviewDag";
import { type ReactNode, type Ref, useEffect, useRef } from "react";
import { ExperimentReviewPanel } from "./ExperimentReviewPanel";
import styles from "./ReviewConsole.module.css";
import { STATUS_LABEL } from "./ReviewStepCard";
import type { ReviewWorkflowModel } from "./useReviewWorkflowModel";

export function ReviewEvidence({
  model,
  focusStep,
}: {
  model: ReviewWorkflowModel;
  focusStep: ReviewStepKey | null;
}) {
  const { attempt, statuses, experimentNames, error } = model;
  const focusRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!focusStep) return;
    focusRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [focusStep]);

  const section = (step: ReviewStepKey, children: ReactNode) => (
    <EvidenceSection
      key={step}
      label={reviewStep(step).label}
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
        if (key === "build_experiment_environment") {
          return section(
            key,
            attempt?.experimentEnvironmentComparison ? (
              <ExperimentEnvironmentVerdictDetail attempt={attempt} />
            ) : null,
          );
        }
        if (key === "activate_experiment_environment") {
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

function BasisNotice({ attempt }: { attempt: ReviewAttempt }) {
  const bundled: string[] = [];
  if (attempt.sourceComparison?.basis === "bundled") bundled.push("source");
  if (attempt.experimentEnvironmentComparison?.basis === "bundled")
    bundled.push("experiment environment");
  if (bundled.length === 0) return null;

  return (
    <div className={styles.detail} data-tone="notice">
      {bundled.join(" and ")} verified from the REE's own artifacts — integrity check, not an
      independent reproduction.
    </div>
  );
}

function ActivationOutcomeDetail({ attempt }: { attempt: ReviewAttempt }) {
  const outcome = attempt.activationOutcome;
  if (!outcome) return null;
  const passed = outcome.verdict === "passed";

  return (
    <div className={styles.detail} data-tone={passed ? undefined : "fault"}>
      <span>
        activation:{" "}
        {passed
          ? "it enters the experiment environment and hands over"
          : "it did not enter the experiment environment"}
      </span>
      {passed ? null : <span>exited {outcome.exitCode ?? "?"}</span>}
    </div>
  );
}

function ExperimentEnvironmentVerdictDetail({ attempt }: { attempt: ReviewAttempt }) {
  const comparison = attempt.experimentEnvironmentComparison;
  if (!comparison) return null;
  const digestsMatch =
    !!comparison.expectedArtifactDigest &&
    comparison.expectedArtifactDigest === comparison.observedArtifactDigest;

  return (
    <div className={styles.detail}>
      <span>
        artifact digest: {digestsMatch ? "bit-identical" : "differs — closure decides the verdict"}
      </span>
      <span>
        closure: {comparison.matched} matched · {comparison.missingCount} missing ·{" "}
        {comparison.extraCount} extra · {comparison.versionMismatchCount} version drift
        {comparison.advisoryCount > 0 ? ` · ${comparison.advisoryCount} advisory` : ""}
      </span>
    </div>
  );
}
