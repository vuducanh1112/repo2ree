import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { ReviewAttempt, ReviewBasisRequest } from "@core/reviews/Review";
import { type ReviewStepKey, settledReviewStepCount } from "@core/reviews/reviewDag";
import {
  reviewStepStatuses,
  runnableReviewSteps,
  selectReviewAttempt,
} from "@core/reviews/reviewStatuses";
import {
  useStartActivationReviewMutation,
  useStartBuildReviewMutation,
  useStartSourceReviewMutation,
} from "@shell/data/reviews/mutations";
import { useReviewsQuery } from "@shell/data/reviews/queries";
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { HudConsole } from "./HudConsole";
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
        : // An attempt opened but not yet readable is the source step still
          // going, which also keeps every later step disabled until it lands.
          pending
          ? "source"
          : undefined;
  const statuses = reviewStepStatuses(attempt, { pendingStep });
  const enabledSteps = runnableReviewSteps(statuses);
  const complete = settledReviewStepCount(statuses);
  const running = pendingStep != null || attempt?.status === "running";

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
  };

  const error =
    startSourceReview.error ??
    startBuildReview.error ??
    startActivationReview.error ??
    reviews.error;

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={660}
      widthCollapsed={270}
      outerStyle={{
        left: "50%",
        bottom: 16,
        transform: "translateX(-50%)",
        zIndex: 35,
        maxWidth: "calc(100% - 640px)",
      }}
      icon={Ic.refresh(16)}
      iconColor={running ? C.accent : "#7c3aed"}
      title="Review"
      subtitle={attempt ? attemptSubtitle(attempt, statuses) : "ready for source review"}
      on={running || complete > 0}
      expandLabel="Expand review controls"
      collapseLabel="Collapse review controls"
      bodyMaxHeight={360}
      bodyStyle={{ gap: 10, overflowX: "auto" }}
    >
      <div style={{ height: 4 }} />
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

      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <button
          type="button"
          disabled
          style={{
            flex: 1,
            minHeight: 36,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            border: `1px solid ${C.border}`,
            borderRadius: 9,
            background: C.surfaceAlt,
            color: C.textMuted,
            cursor: "not-allowed",
            fontSize: 12,
            fontWeight: 750,
          }}
        >
          {Ic.play(13)}
          <span>Lifecycle coming next</span>
        </button>
        <span
          style={{
            maxWidth: 205,
            color: C.textMuted,
            fontFamily: F.mono,
            fontSize: 9,
            lineHeight: 1.35,
          }}
        >
          Source, build and activation are enabled. Experiments remain the next isolated step.
        </span>
      </div>

      {error ? (
        <div
          role="alert"
          style={{
            padding: "6px 8px",
            border: `1px solid ${C.border}`,
            borderRadius: 7,
            background: C.surfaceAlt,
            color: C.error,
            fontFamily: F.mono,
            fontSize: 9.5,
          }}
        >
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
  return `${attempt.reviewId} · source ${statuses.source}${build}${activation}`;
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
    <div style={{ display: "flex", gap: 5 }}>
      {BASIS_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            title={option.hint}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            style={{
              flex: 1,
              minHeight: 28,
              border: `1px solid ${active ? C.accent : C.border}`,
              borderRadius: 7,
              background: active ? C.surface : C.surfaceAlt,
              color: active ? C.text : C.textMuted,
              cursor: disabled ? "not-allowed" : "pointer",
              fontFamily: F.mono,
              fontSize: 9.5,
              fontWeight: active ? 750 : 500,
            }}
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
    <div
      style={{
        padding: "6px 9px",
        border: `1px solid ${C.borderMid}`,
        borderRadius: 7,
        background: C.surfaceAlt,
        color: C.textMuted,
        fontFamily: F.mono,
        fontSize: 9,
        lineHeight: 1.5,
      }}
    >
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
    <div
      style={{
        padding: "7px 9px",
        border: `1px solid ${C.border}`,
        borderRadius: 7,
        background: C.surfaceAlt,
        color: passed ? C.textMuted : C.error,
        fontFamily: F.mono,
        fontSize: 9,
        lineHeight: 1.5,
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
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
    <div
      style={{
        padding: "7px 9px",
        border: `1px solid ${C.border}`,
        borderRadius: 7,
        background: C.surfaceAlt,
        color: C.textMuted,
        fontFamily: F.mono,
        fontSize: 9,
        lineHeight: 1.5,
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
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
