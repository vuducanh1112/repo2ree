import { PAGE } from "@core/app-shell/pages";
import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { ReviewAttempt, ReviewBasisRequest } from "@core/reviews/Review";
import { type ReviewStepKey, settledReviewStepCount } from "@core/reviews/reviewDag";
import {
  reviewStepStatuses,
  runnableReviewSteps,
  selectReviewAttempt,
  unreproducedExperiments,
} from "@core/reviews/reviewStatuses";
import {
  useStartActivationReviewMutation,
  useStartBuildReviewMutation,
  useStartExperimentReviewMutation,
  useStartSourceReviewMutation,
} from "@shell/data/reviews/mutations";
import { useReviewsQuery } from "@shell/data/reviews/queries";
import { useEffect, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";
import { ExperimentReviewPanel } from "./review/ExperimentReviewPanel";
import styles from "./review/ReviewConsole.module.css";
import { ReviewDag } from "./review/ReviewDag";

interface ReviewConsoleProps {
  experiments: readonly ReeExperiment[];
}

/** Active controller for isolated reviewer evidence. */
export function ReviewConsole({ experiments }: ReviewConsoleProps) {
  const [open, setOpen] = useState(false);
  // What the next step reproduces from. "auto" takes the strongest basis the
  // baseline supports; "bundled" is the deliberate choice to certify what the
  // REE already carries, which is the only path open for a bundle with no
  // reachable origin — and the weaker verdict, so it is never the default.
  const [basis, setBasis] = useState<ReviewBasisRequest>("auto");
  const reviews = useReviewsQuery();
  const startSourceReview = useStartSourceReviewMutation();
  const startBuildReview = useStartBuildReviewMutation();
  const startActivationReview = useStartActivationReviewMutation();
  const startExperimentReview = useStartExperimentReviewMutation();
  // The names a "run all" sweep still has to get through, and the one it has
  // already dispatched. Experiments share a workspace, so they must run one at
  // a time; the sweep advances on evidence (a verdict appearing) rather than on
  // the POST resolving, which only means the run was accepted.
  const [sweep, setSweep] = useState<readonly string[] | undefined>();
  const [dispatched, setDispatched] = useState<string | undefined>();
  // The attempt this console opened, named by the run that opened it. Preferred
  // over the newest listed attempt because the list lags: the workbench writes
  // the record a moment after the POST returns, and every step dispatched in
  // that gap would join the *previous* attempt instead.
  const openedReviewId = startSourceReview.data;
  const { attempt, pending } = selectReviewAttempt(reviews.data, openedReviewId);

  const pendingStep: ReviewStepKey | undefined = startSourceReview.isPending
    ? "source"
    : startBuildReview.isPending
      ? "build"
      : startActivationReview.isPending
        ? "activation"
        : startExperimentReview.isPending
          ? "experiments"
          : // An attempt opened but not yet readable is the source step still
            // going, which also keeps every later step disabled until it lands.
            pending
            ? "source"
            : undefined;
  const statuses = reviewStepStatuses(attempt, { pendingStep });
  const enabledSteps = runnableReviewSteps(statuses);
  const complete = settledReviewStepCount(statuses);
  const running = pendingStep != null || attempt?.status === "running";

  const experimentNames = experiments
    .map((experiment) => experiment.name.trim())
    .filter((name) => name.length > 0);

  const runExperiment = (experimentName: string) => {
    if (!attempt || !enabledSteps.has("experiments")) return;
    startExperimentReview.mutate({ reviewId: attempt.reviewId, experimentName });
  };

  // A sweep covers what has no verdict yet rather than everything declared:
  // re-running a settled experiment is a deliberate act, and the per-experiment
  // "Re-run" is where it belongs.
  const remaining = unreproducedExperiments(attempt, experimentNames);
  const runAllExperiments = () => {
    if (!attempt || !enabledSteps.has("experiments") || remaining.length === 0) return;
    setSweep(remaining);
  };

  // Drive a sweep one experiment at a time. The next one goes out only once the
  // previous has a verdict on the record, because the POST resolving means the
  // run was accepted rather than finished — and two experiments running at once
  // would write over each other's outputs in the shared workspace.
  useEffect(() => {
    if (!sweep || !attempt) return;
    const next = sweep.find(
      (name) => !attempt.experimentComparisons.some((entry) => entry.experimentName === name),
    );
    if (next === undefined) {
      setSweep(undefined);
      setDispatched(undefined);
      return;
    }
    // A step that failed produces no verdict, so waiting for one would stall the
    // sweep in silence. Stop instead and leave the failure on screen.
    if (attempt.status === "failed") {
      setSweep(undefined);
      setDispatched(undefined);
      return;
    }
    if (next === dispatched || startExperimentReview.isPending) return;
    setDispatched(next);
    startExperimentReview.mutate({ reviewId: attempt.reviewId, experimentName: next });
  }, [sweep, attempt, dispatched, startExperimentReview]);

  const invokeStep = (step: ReviewStepKey) => {
    if (!enabledSteps.has(step)) return;
    if (step === "source") startSourceReview.mutate(basis);
    // Build joins the attempt source opened; without one there is nothing to
    // build against, which is also why the DAG leaves it disabled until then.
    if (step === "build" && attempt) startBuildReview.mutate({ reviewId: attempt.reviewId, basis });
    // Activation takes no basis: it probes whatever runtime the build left in
    // the attempt's workspace and inherits what that evidence is worth.
    if (step === "activation" && attempt)
      startActivationReview.mutate({ reviewId: attempt.reviewId });
    // The graph node stands for the whole set, so it sweeps; one experiment at
    // a time is the panel's job.
    if (step === "experiments") runAllExperiments();
  };

  const error =
    startSourceReview.error ??
    startBuildReview.error ??
    startActivationReview.error ??
    startExperimentReview.error ??
    reviews.error;

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={660}
      widthCollapsed={270}
      className={hud.reviewPlacement}
      icon={Ic.refresh(16)}
      iconTint={running ? "var(--chrome-accent)" : stageTone(PAGE.EVALUATE)}
      title="Review"
      subtitle={attempt ? attemptSubtitle(attempt, statuses) : "ready for source review"}
      on={running || complete > 0}
      expandLabel="Expand review controls"
      collapseLabel="Collapse review controls"
      bodyMaxHeight={360}
      bodyClassName={hud.reviewBody}
    >
      <div className={styles.topSpacer} />
      <ReviewDag
        experimentCount={experiments.filter((experiment) => experiment.name.trim()).length}
        statuses={statuses}
        enabledSteps={enabledSteps}
        onRunStep={invokeStep}
      />

      <BasisPicker value={basis} onChange={setBasis} disabled={running} />

      {attempt ? <BasisNotice attempt={attempt} /> : null}
      {attempt?.buildComparison ? <BuildVerdictDetail attempt={attempt} /> : null}
      {attempt?.activationOutcome ? <ActivationOutcomeDetail attempt={attempt} /> : null}

      <ExperimentReviewPanel
        attempt={attempt}
        experimentNames={experimentNames}
        statuses={statuses}
        sweeping={sweep != null}
        canRun={enabledSteps.has("experiments") && attempt != null}
        onRun={runExperiment}
        onRunAll={runAllExperiments}
      />

      {error ? (
        <div role="alert" className={styles.error}>
          {error instanceof Error ? error.message : "Review unavailable"}
        </div>
      ) : null}
    </HudConsole>
  );
}

function attemptSubtitle(
  attempt: ReviewAttempt,
  statuses: Readonly<Record<ReviewStepKey, string>>,
): string {
  const build = attempt.buildComparison ? ` · build ${statuses.build}` : "";
  const activation = attempt.activationOutcome ? ` · activation ${statuses.activation}` : "";
  const experiments =
    attempt.experimentComparisons.length > 0 ? ` · results ${statuses.experiments}` : "";
  return `${attempt.reviewId} · source ${statuses.source}${build}${activation}${experiments}`;
}

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

/** Which evidence the next step should rest on. */
function BasisPicker({
  value,
  onChange,
  disabled,
}: {
  value: ReviewBasisRequest;
  onChange: (basis: ReviewBasisRequest) => void;
  disabled: boolean;
}) {
  return (
    <div className={styles.basis}>
      {BASIS_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            title={option.hint}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            aria-pressed={active}
            className={styles.basisOption}
          >
            {option.label}
          </button>
        );
      })}
    </div>
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
