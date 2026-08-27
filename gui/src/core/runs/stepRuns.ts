import type { ReeRunOperation, ReeRunSummary } from "./ReeRun";
import { isTerminalReeRunStatus } from "./ReeRunStatus";

function runsForOperation(runs: readonly ReeRunSummary[], operation: string): ReeRunSummary[] {
  return [...runs]
    .filter((run) => run.operation === (operation as ReeRunOperation))
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export function activeRunForOperation(
  runs: readonly ReeRunSummary[],
  operation: string,
): ReeRunSummary | undefined {
  return runsForOperation(runs, operation).find((run) => !isTerminalReeRunStatus(run.status));
}

export function latestRunForOperation(
  runs: readonly ReeRunSummary[],
  operation: string,
): ReeRunSummary | undefined {
  return runsForOperation(runs, operation)[0];
}
