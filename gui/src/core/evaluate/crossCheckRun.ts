import type { ReeRunSummary } from "../runs/ReeRun";
import { parseSbomCrossCheck, type SbomCrossCheckSummary } from "./Threat";

/**
 * The cross-check result the REE currently stands on, read off its runs.
 *
 * The cross-check joins the runtime SBOM with the scanned dependency inventory
 * *after* evaluate wrote its report, and that report is evidence the evaluate
 * receipt digest-pins — so the join reports itself through its own run rather
 * than by rewriting an artifact it does not own. Runs arrive newest-first, but
 * that is the listing's choice, not a contract, so order here by when each run
 * finished. Pure.
 */
export function latestCrossCheckSummary(runs: ReeRunSummary[]): SbomCrossCheckSummary | null {
  const succeeded = runs
    .filter((run) => run.operation === "crosscheck" && run.status === "succeeded")
    .sort((left, right) => runInstant(right).localeCompare(runInstant(left)));
  for (const run of succeeded) {
    const summary = parseSbomCrossCheck(run.outputs?.cross_check);
    if (summary) return summary;
  }
  return null;
}

function runInstant(run: ReeRunSummary): string {
  return run.finishedAt ?? run.createdAt;
}
