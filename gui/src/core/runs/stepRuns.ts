import type { ReeRunOperation, ReeRunSummary } from "./ReeRun";
import { isTerminalReeRunStatus } from "./ReeRunStatus";

/** The operation whose run advances each step, by the step's key. */
const STEP_OPERATION: ReadonlyMap<string, ReeRunOperation> = new Map<string, ReeRunOperation>([
  ["source", "acquire_source"],
  ["hbom", "observe_hardware"],
  ["check_working_environment", "check_working_environment"],
  ["evaluate", "evaluate_reproducibility"],
  ["build_experiment_environment", "build_experiment_environment"],
  ["sbom", "generate_sbom"],
  ["crosscheck", "cross_check_sbom"],
  ["activation", "activate_experiment_environment"],
  ["experiments", "run_experiment"],
  ["seal", "seal_ree"],
]);

function runsForStep(runs: readonly ReeRunSummary[], step: string): ReeRunSummary[] {
  const operation = STEP_OPERATION.get(step);
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
