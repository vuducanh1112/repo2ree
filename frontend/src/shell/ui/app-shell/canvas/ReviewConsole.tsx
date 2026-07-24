import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { ReviewAttempt } from "@core/reviews/Review";
import { type ReviewStepKey, settledReviewStepCount } from "@core/reviews/reviewDag";
import { reviewStepStatuses, runnableReviewSteps } from "@core/reviews/reviewStatuses";
import {
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
  const reviews = useReviewsQuery();
  const startSourceReview = useStartSourceReviewMutation();
  const startBuildReview = useStartBuildReviewMutation();
  const latest = reviews.data?.[0];

  const pendingStep: ReviewStepKey | undefined = startSourceReview.isPending
    ? "source"
    : startBuildReview.isPending
      ? "build"
      : undefined;
  const statuses = reviewStepStatuses(latest, { pendingStep });
  const enabledSteps = runnableReviewSteps(statuses);
  const complete = settledReviewStepCount(statuses);
  const running = pendingStep != null || latest?.status === "running";

  const invokeStep = (step: ReviewStepKey) => {
    if (!enabledSteps.has(step)) return;
    if (step === "source") startSourceReview.mutate();
    // Build joins the attempt source opened; without one there is nothing to
    // build against, which is also why the DAG leaves it disabled until then.
    if (step === "build" && latest) startBuildReview.mutate(latest.reviewId);
  };

  const error = startSourceReview.error ?? startBuildReview.error ?? reviews.error;

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
      subtitle={latest ? attemptSubtitle(latest, statuses) : "ready for source review"}
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

      {latest?.buildComparison ? <BuildVerdictDetail attempt={latest} /> : null}

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
          Source and build are enabled. Activation and experiments remain isolated next steps.
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
  return `${attempt.reviewId} · source ${statuses.source}${build}`;
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
