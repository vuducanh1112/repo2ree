import type { ReeExperiment } from "@core/ree/ReeSpec";
import {
  type ReviewStepKey,
  type ReviewStepStatus,
  settledReviewStepCount,
} from "@core/reviews/reviewDag";
import { useStartSourceReviewMutation } from "@shell/data/reviews/mutations";
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
  const latest = reviews.data?.[0];

  const sourceStatus: ReviewStepStatus = startSourceReview.isPending
    ? "queued"
    : latest?.status === "running"
      ? "running"
      : latest?.status === "completed"
        ? (latest.sourceComparison?.verdict ?? "succeeded")
        : latest?.status === "failed" || latest?.status === "canceled"
          ? "failed"
          : "ready";
  const statuses: Partial<Record<ReviewStepKey, ReviewStepStatus>> = {
    source: sourceStatus,
    build: "unavailable",
    activation: "unavailable",
    experiments: "unavailable",
  };
  const complete = settledReviewStepCount(statuses);
  const running = sourceStatus === "queued" || sourceStatus === "running";
  const enabledSteps = new Set<ReviewStepKey>(running ? [] : ["source"]);

  const invokeStep = (step: ReviewStepKey) => {
    if (step === "source" && enabledSteps.has(step)) startSourceReview.mutate();
  };

  const error = startSourceReview.error ?? reviews.error;

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
      subtitle={latest ? `${latest.reviewId} · source ${sourceStatus}` : "ready for source review"}
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
          Source is enabled first. Build, activation, and experiments remain isolated next steps.
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
