import type { ActionStates, Badges, Timestamps } from "../ree/ReeTypes";
import type { ReeRunSummary } from "./ReeRun";
import { isTerminalReeRunStatus } from "./ReeRunStatus";

export interface StepRunProjection {
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  activeRunIds: Record<string, string>;
}

/** Project the durable run list into the legacy page-facing shape. */
export function projectStepRuns(runs: readonly ReeRunSummary[]): StepRunProjection {
  const projection: StepRunProjection = {
    actionStates: {},
    badges: {},
    timestamps: {},
    activeRunIds: {},
  };
  const newest = [...runs].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
  for (const run of newest) {
    const key = run.operation;
    if (!(key in projection.activeRunIds)) {
      projection.activeRunIds[key] = run.runId;
      projection.timestamps[key] = run.finishedAt ?? run.startedAt ?? run.createdAt;
    }
    if (!isTerminalReeRunStatus(run.status)) {
      projection.actionStates[key] = "loading";
      projection.activeRunIds[key] = run.runId;
      continue;
    }
    if (!(key in projection.badges)) {
      if (projection.actionStates[key] !== "loading") {
        projection.actionStates[key] = "done";
      }
      projection.badges[key] =
        run.status === "succeeded"
          ? "succeeded"
          : run.status === "canceled"
            ? "canceled"
            : "failed";
    }
  }
  return projection;
}
