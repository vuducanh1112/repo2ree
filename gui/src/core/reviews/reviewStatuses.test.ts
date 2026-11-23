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

    expect(statuses.acquire_source).toBe("ready");
    expect(statuses.build_experiment_environment).toBe("unavailable");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["acquire_source"]));
  });

  it("shows the comparison verdict once a step settles, not its lifecycle status", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("acquire_source")],
        sourceComparison: { basis: "independent", verdict: "identical" },
      }),
    );

    expect(statuses.acquire_source).toBe("identical");
  });

  it("unlocks build once source settles, whatever the source verdict", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("acquire_source")],
        sourceComparison: { basis: "independent", verdict: "different" },
      }),
    );

    expect(statuses.build_experiment_environment).toBe("ready");
    expect(runnableReviewSteps(statuses)).toEqual(
      new Set(["acquire_source", "build_experiment_environment"]),
    );
  });

  it("keeps build locked when source failed — there is nothing to build against", () => {
    const statuses = reviewStepStatuses(attempt({ steps: [step("acquire_source", "failed")] }));

    expect(statuses.acquire_source).toBe("failed");
    expect(statuses.build_experiment_environment).toBe("unavailable");
    expect(runnableReviewSteps(statuses)).toEqual(new Set(["acquire_source"]));
  });

  it("reports an equivalent rebuild as the build verdict", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("acquire_source"), step("build_experiment_environment")],
        sourceComparison: { basis: "independent", verdict: "identical" },
        experimentEnvironmentComparison: {
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

    expect(statuses.build_experiment_environment).toBe("equivalent");
  });

  it("nothing is runnable while a step is in flight", () => {
    const running = reviewStepStatuses(
      attempt({ status: "running", steps: [step("acquire_source", "running")] }),
    );
    expect(running.acquire_source).toBe("running");
    expect(runnableReviewSteps(running)).toEqual(new Set());

    const queued = reviewStepStatuses(attempt({ steps: [step("acquire_source")] }), {
      pendingStep: "build_experiment_environment",
    });
    expect(queued.build_experiment_environment).toBe("queued");
    expect(runnableReviewSteps(queued)).toEqual(new Set());
  });

  it("leaves the steps with no reviewer path yet unavailable", () => {
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("acquire_source"), step("build_experiment_environment")],
        sourceComparison: { basis: "independent", verdict: "identical" },
        experimentEnvironmentComparison: {
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

    expect(statuses.activate_experiment_environment).toBe("ready");
    expect(statuses.experiments).toBe("unavailable");
    expect(runnableReviewSteps(statuses)).toEqual(
      new Set([
        "acquire_source",
        "build_experiment_environment",
        "activate_experiment_environment",
      ]),
    );
  });
});

describe("activate_experiment_environment", () => {
  const settledBuild = attempt({
    steps: [
      step("acquire_source"),
      step("build_experiment_environment"),
      step("activate_experiment_environment"),
    ],
    sourceComparison: { basis: "independent", verdict: "identical" },
    experimentEnvironmentComparison: {
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

    expect(statuses.activate_experiment_environment).toBe("succeeded");
  });

  it("distinguishes an experiment environment that did not come up from a step that broke", () => {
    const statuses = reviewStepStatuses({
      ...settledBuild,
      activationOutcome: { basis: "independent", verdict: "failed", exitCode: 7 },
    });

    expect(statuses.activate_experiment_environment).toBe("uninhabitable");
    expect(statuses.activate_experiment_environment).not.toBe("failed");
  });

  it("does not offer experiments inside an experiment environment that would not come up", () => {
    const statuses = reviewStepStatuses({
      ...settledBuild,
      activationOutcome: { basis: "independent", verdict: "failed", exitCode: 7 },
    });

    expect(statuses.experiments).toBe("unavailable");
    expect(runnableReviewSteps(statuses).has("experiments")).toBe(false);
  });
});

describe("experiments", () => {
  const inhabitable = attempt({
    steps: [
      step("acquire_source"),
      step("build_experiment_environment"),
      step("activate_experiment_environment"),
    ],
    sourceComparison: { basis: "independent", verdict: "identical" },
    experimentEnvironmentComparison: {
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

  it("offers experiments once the experiment environment is known to come up", () => {
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

  it("locks every experiment while the experiment environment is unproven", () => {
    const statuses = reviewStepStatuses(attempt({ steps: [step("acquire_source")] }));

    expect(experimentReviewStatus(undefined, "a", statuses)).toBe("unavailable");
  });

  it("counts what reproduced, not what merely settled", () => {
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
    const statuses = reviewStepStatuses(
      attempt({
        steps: [step("acquire_source")],
        sourceComparison: { basis: "bundled", verdict: "identical" },
      }),
    );

    expect(statuses.acquire_source).toBe("identical");
    expect(statuses.build_experiment_environment).toBe("ready");
  });
});

describe("selectReviewAttempt", () => {
  const previous = attempt({
    reviewId: "review-old",
    steps: [step("acquire_source"), step("build_experiment_environment")],
  });
  const opened = attempt({ reviewId: "review-new", steps: [step("acquire_source")] });

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
    expect(selectReviewAttempt([previous], "review-new")).toEqual({
      attempt: undefined,
      pending: true,
    });
  });

  it("holds every step closed until the opened attempt is readable", () => {
    const { attempt: selected, pending } = selectReviewAttempt([previous], "review-new");
    const statuses = reviewStepStatuses(selected, {
      pendingStep: pending ? "acquire_source" : undefined,
    });

    expect(statuses.acquire_source).toBe("queued");
    expect(runnableReviewSteps(statuses)).toEqual(new Set());
  });
});
