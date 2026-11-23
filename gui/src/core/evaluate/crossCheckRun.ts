import type { ReeRunSummary } from "../runs/ReeRun";
import { parseSbomCrossCheck, type SbomCrossCheckSummary } from "./Threat";

export function latestCrossCheckSummary(runs: ReeRunSummary[]): SbomCrossCheckSummary | null {
  const succeeded = runs
    .filter((run) => run.operation === "cross_check_sbom" && run.status === "succeeded")
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
