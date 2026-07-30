import { describe, expect, it } from "vitest";
import type { ReviewAttempt, ReviewStepState } from "./Review";
import {
  experimentReviewStatus,
  reproducedExperimentCount,
  reviewStepStatuses,
  runnableReviewSteps,
  selectReviewAttempt,
  unreproducedExperiments,
} from "./reviewStatuses";

function attempt(overrides: Partial<ReviewAttempt> = {}): ReviewAttempt {
  return {
    reviewId: "review-abc",
    createdAt: "2026-07-24T10:00:00Z",
    updatedAt: "2026-07-24T10:00:01Z",
    status: "completed",
    steps: [],
    experimentComparisons: [],
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

    // Experiments depend on activation, not on the build: a certified runtime
    // that has not been shown to come up is nothing to run results in yet.
    expect(statuses.activation).toBe("ready");
    expect(statuses.experiments).toBe("unavailable");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["source", "build", "activation"]));
  });
});

describe("activation", () => {
  const settledBuild = attempt({
    steps: [step("source"), step("build"), step("activation")],
    sourceComparison: { basis: "independent", verdict: "identical" },
    buildComparison: {
      basis: "independent",
      verdict: "equivalent",
      matched: 1,
      missingCount: 0,
      extraCount: 0,
      versionMismatchCount: 0,
      advisoryCount: 0,
      missing: [],
      extra: [],
      versionMismatches: [],
    },
  });

  it("reads a passing probe as a settled step", () => {
    const statuses = reviewStepStatuses({
      ...settledBuild,
      activationOutcome: { basis: "independent", verdict: "passed" },
    });

    expect(statuses.activation).toBe("succeeded");
  });

  it("distinguishes a runtime that did not come up from a step that broke", () => {
    // The step completed — the reviewer's machine did its job and found
    // something. Rendering that as "failed" would report the review as broken.
    const statuses = reviewStepStatuses({
      ...settledBuild,
      activationOutcome: { basis: "independent", verdict: "failed", runExitCode: 7 },
    });

    expect(statuses.activation).toBe("uninhabitable");
    expect(statuses.activation).not.toBe("failed");
  });

  it("does not offer experiments inside a runtime that would not come up", () => {
    const statuses = reviewStepStatuses({
      ...settledBuild,
      activationOutcome: { basis: "independent", verdict: "failed", runExitCode: 7 },
    });

    // Experiments run *in* that runtime, so their failures would say nothing
    // about the experiments themselves.
    expect(statuses.experiments).toBe("unavailable");
    expect(runnableReviewSteps(statuses).has("experiments")).toBe(false);
  });
});

describe("experiments", () => {
  const inhabitable = attempt({
    steps: [step("source"), step("build"), step("activation")],
    sourceComparison: { basis: "independent", verdict: "identical" },
    buildComparison: {
      basis: "independent",
      verdict: "equivalent",
      matched: 1,
      missingCount: 0,
      extraCount: 0,
      versionMismatchCount: 0,
      advisoryCount: 0,
      missing: [],
      extra: [],
      versionMismatches: [],
    },
    activationOutcome: { basis: "independent", verdict: "passed" },
  });

  function comparison(
    name: string,
    verdict: "identical" | "reproduced" | "different" | "inconclusive",
  ) {
    return {
      basis: "independent" as const,
      verdict,
      experimentName: name,
      verifyScriptPath: "ree-scripts/experiments/one.verify.sh",
      expectedVerifyExitCode: 0,
      observedVerifyExitCode: verdict === "different" ? 1 : 0,
    };
  }

  it("offers experiments once the runtime is known to come up", () => {
    const statuses = reviewStepStatuses(inhabitable);

    expect(statuses.experiments).toBe("ready");
    expect(runnableReviewSteps(statuses).has("experiments")).toBe(true);
  });

  it("rolls the step up to its worst verdict so a failure cannot hide behind passes", () => {
    const statuses = reviewStepStatuses({
      ...inhabitable,
      steps: [...inhabitable.steps, step("experiments")],
      experimentComparisons: [comparison("a", "identical"), comparison("b", "different")],
    });

    expect(statuses.experiments).toBe("different");
  });

  it("ranks an experiment with no criterion below its siblings' passes", () => {
    // "inconclusive" means nothing stated what a correct result is. Letting a
    // sibling's pass outrank it would present the step as settled when part of
    // it was never judged at all.
    const statuses = reviewStepStatuses({
      ...inhabitable,
      steps: [...inhabitable.steps, step("experiments")],
      experimentComparisons: [comparison("a", "reproduced"), comparison("b", "inconclusive")],
    });

    expect(statuses.experiments).toBe("inconclusive");
  });

  it("keeps a differing result a verdict rather than a broken step", () => {
    const statuses = reviewStepStatuses({
      ...inhabitable,
      steps: [...inhabitable.steps, step("experiments")],
      experimentComparisons: [comparison("a", "different")],
    });

    expect(statuses.experiments).not.toBe("failed");
  });

  it("gives each experiment its own status so one verdict does not settle another", () => {
    const settled = {
      ...inhabitable,
      steps: [...inhabitable.steps, step("experiments")],
      experimentComparisons: [comparison("a", "reproduced")],
    };
    const statuses = reviewStepStatuses(settled);

    expect(experimentReviewStatus(settled, "a", statuses)).toBe("reproduced");
    expect(experimentReviewStatus(settled, "b", statuses)).toBe("ready");
  });

  it("locks every experiment while the runtime is unproven", () => {
    const statuses = reviewStepStatuses(attempt({ steps: [step("source")] }));

    expect(experimentReviewStatus(undefined, "a", statuses)).toBe("unavailable");
  });

  it("counts what reproduced, not what merely settled", () => {
    // The counter carries the word "reproduced" next to it, so a `different`
    // verdict must not swell it — that would report the review's own findings
    // back as successes.
    const mixed = {
      ...inhabitable,
      experimentComparisons: [
        comparison("a", "identical"),
        comparison("b", "reproduced"),
        comparison("c", "different"),
        comparison("d", "inconclusive"),
      ],
    };

    expect(reproducedExperimentCount(mixed)).toBe(2);
    expect(reproducedExperimentCount(undefined)).toBe(0);
  });

  it("sweeps only what has no verdict yet", () => {
    const settled = {
      ...inhabitable,
      experimentComparisons: [comparison("a", "reproduced")],
    };

    expect(unreproducedExperiments(settled, ["a", "b", "c"])).toEqual(["b", "c"]);
    expect(unreproducedExperiments(settled, ["a"])).toEqual([]);
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

describe("selectReviewAttempt", () => {
  const previous = attempt({ reviewId: "review-old", steps: [step("source"), step("build")] });
  const opened = attempt({ reviewId: "review-new", steps: [step("source")] });

  it("takes the newest listed attempt before this console has opened one", () => {
    expect(selectReviewAttempt([opened, previous], undefined)).toEqual({
      attempt: opened,
      pending: false,
    });
  });

  it("drives the attempt it opened, not whichever is newest", () => {
    expect(selectReviewAttempt([opened, previous], "review-old")).toEqual({
      attempt: previous,
      pending: false,
    });
  });

  it("reports the gap rather than falling back to the previous attempt", () => {
    // The workbench writes the record a moment after the POST returns. Handing
    // back `previous` here is what let a build join the wrong attempt: its steps
    // read as settled, so the console offered — and dispatched — the next one.
    expect(selectReviewAttempt([previous], "review-new")).toEqual({
      attempt: undefined,
      pending: true,
    });
  });

  it("holds every step closed until the opened attempt is readable", () => {
    const { attempt: selected, pending } = selectReviewAttempt([previous], "review-new");
    const statuses = reviewStepStatuses(selected, { pendingStep: pending ? "source" : undefined });

    expect(statuses.source).toBe("queued");
    expect(runnableReviewSteps(statuses)).toEqual(new Set());
  });
});
