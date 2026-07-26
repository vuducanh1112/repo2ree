import { describe, expect, it } from "vitest";
import type { ReviewAttempt, ReviewStepState } from "./Review";
import { reviewStepStatuses, runnableReviewSteps } from "./reviewStatuses";

function attempt(overrides: Partial<ReviewAttempt> = {}): ReviewAttempt {
  return {
    reviewId: "review-abc",
    createdAt: "2026-07-24T10:00:00Z",
    updatedAt: "2026-07-24T10:00:01Z",
    status: "completed",
    steps: [],
    ...overrides,
  };
}

function step(
  key: ReviewStepState["step"],
  status: ReviewStepState["status"] = "completed",
): ReviewStepState {
  return { step: key, status };
}

describe("reviewStepStatuses", () => {
  it("offers source and nothing else before any attempt exists", () => {
    const statuses = reviewStepStatuses(undefined);

    expect(statuses.source).toBe("ready");
    expect(statuses.build).toBe("unavailable");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["source"]));
  });

  it("shows the comparison verdict once a step settles, not its lifecycle status", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("source")],
        sourceComparison: { basis: "independent", verdict: "identical" },
      }),
    );

    expect(statuses.source).toBe("identical");
  });

  it("unlocks build once source settles, whatever the source verdict", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("source")],
        sourceComparison: { basis: "independent", verdict: "different" },
      }),
    );

    expect(statuses.build).toBe("ready");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["source", "build"]));
  });

  it("keeps build locked when source failed — there is nothing to build against", () => {
    const statuses = reviewStepStatuses(attempt({ steps: [step("source", "failed")] }));

    expect(statuses.source).toBe("failed");
    expect(statuses.build).toBe("unavailable");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["source"]));
  });

  it("reports an equivalent rebuild as the build verdict", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("source"), step("build")],
        sourceComparison: { basis: "independent", verdict: "identical" },
        buildComparison: {
          basis: "independent",
          verdict: "equivalent",
          matched: 42,
          missingCount: 0,
          extraCount: 0,
          versionMismatchCount: 0,
          advisoryCount: 3,
          missing: [],
          extra: [],
          versionMismatches: [],
        },
      }),
    );

    expect(statuses.build).toBe("equivalent");
  });

  it("nothing is runnable while a step is in flight", () => {
    const running = reviewStepStatuses(
      attempt({ status: "running", steps: [step("source", "running")] }),
    );
    expect(running.source).toBe("running");
    expect(runnableReviewSteps(running)).toEqual(new Set());

    const queued = reviewStepStatuses(attempt({ steps: [step("source")] }), {
      pendingStep: "build",
    });
    expect(queued.build).toBe("queued");
    expect(runnableReviewSteps(queued)).toEqual(new Set());
  });

  it("leaves the steps with no reviewer path yet unavailable", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("source"), step("build")],
        sourceComparison: { basis: "independent", verdict: "identical" },
        buildComparison: {
          basis: "independent",
          verdict: "identical",
          matched: 1,
          missingCount: 0,
          extraCount: 0,
          versionMismatchCount: 0,
          advisoryCount: 0,
          missing: [],
          extra: [],
          versionMismatches: [],
        },
      }),
    );

    // Activation's dependency has settled, so the DAG would allow it; it stays
    // out of the runnable set until it has a handler behind it.
    expect(statuses.activation).toBe("ready");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["source", "build"]));
  });
});

describe("evidence basis", () => {
  it("keeps the verdict and the basis independent of each other", () => {
    // A bundled attempt still reports the verdict its comparison earned; what
    // the basis changes is the claim the console makes about it, not the DAG.
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("source")],
        sourceComparison: { basis: "bundled", verdict: "identical" },
      }),
    );

    expect(statuses.source).toBe("identical");
    expect(statuses.build).toBe("ready");
  });
});
