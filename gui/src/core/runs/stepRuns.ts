import { REE_RUN_OPERATIONS, type ReeRunOperation } from "@core/generated/vocabulary";
import type { ReeRunSummary } from "./ReeRun";
import { isTerminalReeRunStatus } from "./ReeRunStatus";

function stepOperation(step: string): ReeRunOperation | undefined {
  if (step === "experiments") return "run_experiment";
  return REE_RUN_OPERATIONS.find((operation) => operation === step);
}

function runsForStep(runs: readonly ReeRunSummary[], step: string): ReeRunSummary[] {
  const operation = stepOperation(step);
  return [...runs]
    .filter((run) => run.operation === operation)
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export function activeRunForStep(
  runs: readonly ReeRunSummary[],
  step: string,
): ReeRunSummary | undefined {
  return runsForStep(runs, step).find((run) => !isTerminalReeRunStatus(run.status));
}

export function latestRunForStep(
  runs: readonly ReeRunSummary[],
  step: string,
): ReeRunSummary | undefined {
  return runsForStep(runs, step)[0];
}
