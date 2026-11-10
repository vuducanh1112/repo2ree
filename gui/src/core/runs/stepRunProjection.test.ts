import { describe, expect, it } from "vitest";
import type { ReeRunSummary } from "./ReeRun";
import { projectStepRuns } from "./stepRunProjection";

function run(
  patch: Partial<ReeRunSummary> & Pick<ReeRunSummary, "runId" | "status">,
): ReeRunSummary {
  return {
    operation: "build_experiment_environment",
    createdAt: "2026-01-01T00:00:00Z",
    ...patch,
  };
}

describe("projectStepRuns", () => {
  it("projects active and terminal state from backend runs", () => {
    const projection = projectStepRuns([
      run({ runId: "old-failure", status: "failed", finishedAt: "2026-01-01T00:01:00Z" }),
      run({
        runId: "active",
        status: "running",
        createdAt: "2026-01-02T00:00:00Z",
      }),
    ]);

    expect(projection.actionStates.build_experiment_environment).toBe("loading");
    expect(projection.activeRunIds.build_experiment_environment).toBe("active");
    expect(projection.badges.build_experiment_environment).toBe("failed");
  });

  it("does not turn a failed backend run into a successful badge", () => {
    expect(
      projectStepRuns([run({ runId: "failed", status: "failed" })]).badges
        .build_experiment_environment,
    ).toBe("failed");
  });
});
