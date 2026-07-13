// View model for the logs HUD: one tab per pipeline step, each tab holding
// that step's run history. Tab order is pipeline order (not recency) so tab
// positions stay stable across sessions.
import type { ReeRunOperation, ReeRunSummary } from "./ReeRun";
import { isTerminalReeRunStatus } from "./ReeRunStatus";

interface RunHudTab {
  key: string;
  /** Short label shown in the resting tab strip. */
  abbrev: string;
  /** Full name the tab expands to on hover. */
  label: string;
  /** Run operations collected under this tab. */
  operations: readonly ReeRunOperation[];
}

export const RUN_HUD_TABS = [
  { key: "provision", abbrev: "PROV", label: "Provision", operations: ["provision"] },
  { key: "source", abbrev: "SRC", label: "Source", operations: ["source"] },
  { key: "build", abbrev: "BLD", label: "Build", operations: ["build"] },
  { key: "sbom", abbrev: "SBOM", label: "SBOM", operations: ["sbom"] },
  { key: "activation", abbrev: "ACT", label: "Activation", operations: ["activation"] },
  { key: "evaluate", abbrev: "EVAL", label: "Evaluate", operations: ["evaluate"] },
  { key: "hbom", abbrev: "HBOM", label: "HBOM", operations: ["hbom"] },
  { key: "archive", abbrev: "ARC", label: "Archive", operations: ["swh", "zenodo", "dataverse"] },
  { key: "experiment", abbrev: "EXP", label: "Experiments", operations: ["experiment"] },
] as const satisfies readonly RunHudTab[];

export type RunHudTabKey = (typeof RUN_HUD_TABS)[number]["key"];

export function runHudTabForOperation(operation: ReeRunOperation): RunHudTabKey {
  const tab = RUN_HUD_TABS.find((t) => (t.operations as readonly string[]).includes(operation));
  // Every ReeRunOperation is listed in RUN_HUD_TABS; guard for forward compat
  // with operations this build does not know yet.
  return tab ? tab.key : "experiment";
}

function newestFirst(runs: readonly ReeRunSummary[]): ReeRunSummary[] {
  return [...runs].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

/** Runs belonging to a tab, newest first. */
export function runsForHudTab(
  runs: readonly ReeRunSummary[],
  tabKey: RunHudTabKey,
): ReeRunSummary[] {
  const tab = RUN_HUD_TABS.find((t) => t.key === tabKey);
  if (!tab) return [];
  return newestFirst(
    runs.filter((run) => (tab.operations as readonly string[]).includes(run.operation)),
  );
}

function isActiveReeRun(run: ReeRunSummary): boolean {
  return !isTerminalReeRunStatus(run.status);
}

export function activeRunCount(runs: readonly ReeRunSummary[]): number {
  return runs.filter(isActiveReeRun).length;
}

/** The most recently started run that is still active, if any. */
export function newestActiveRun(runs: readonly ReeRunSummary[]): ReeRunSummary | undefined {
  return newestFirst(runs).find(isActiveReeRun);
}

/** The most recent run overall — what the collapsed ticker shows. */
export function newestRun(runs: readonly ReeRunSummary[]): ReeRunSummary | undefined {
  return newestFirst(runs)[0];
}

interface RunHudTabActivity {
  /** A run under this tab is currently active. */
  active: boolean;
  /** The tab's newest run finished without succeeding (and none is active). */
  failed: boolean;
}

export function hudTabActivity(
  runs: readonly ReeRunSummary[],
  tabKey: RunHudTabKey,
): RunHudTabActivity {
  const tabRuns = runsForHudTab(runs, tabKey);
  const active = tabRuns.some(isActiveReeRun);
  const newest = tabRuns[0];
  const failed = !active && (newest?.status === "failed" || newest?.status === "canceled");
  return { active, failed };
}

/** "4m 02s" run duration, or undefined while the run has no usable window yet. */
export function formatRunDuration(run: ReeRunSummary): string | undefined {
  const start = run.startedAt ?? run.createdAt;
  const end = run.finishedAt;
  if (!start || !end) return undefined;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms < 0) return undefined;
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}
