import type { ReeRunOperation } from "@core/generated/vocabulary";
import type { ReeRunSummary } from "./ReeRun";
import { isTerminalReeRunStatus } from "./ReeRunStatus";

interface RunHudTab {
  key: string;
  abbrev: string;
  label: string;
  operations: readonly ReeRunOperation[];
}

export const RUN_HUD_TABS = [
  {
    key: "provision",
    abbrev: "PROV",
    label: "Provision",
    operations: ["initialize_ree", "load_ree_bundle"],
  },
  {
    key: "source",
    abbrev: "SRC",
    label: "Source",
    operations: [
      "acquire_source",
      "remove_source",
      "materialize_workspace",
      "review_acquire_source",
    ],
  },
  {
    key: "authoring",
    abbrev: "EDIT",
    label: "Authoring",
    operations: ["patch_ree_definition", "write_script", "suggest_scripts", "lint_scripts"],
  },
  {
    key: "build_experiment_environment",
    abbrev: "BLD",
    label: "Build Experiment Environment",
    operations: ["build_experiment_environment", "review_build_experiment_environment"],
  },
  { key: "sbom", abbrev: "SBOM", label: "SBOM", operations: ["generate_sbom", "cross_check_sbom"] },
  {
    key: "activation",
    abbrev: "ACT",
    label: "Activation",
    operations: ["activate_experiment_environment", "review_activate_experiment_environment"],
  },
  {
    key: "check_working_environment",
    abbrev: "CHK",
    label: "Check Working Environment",
    operations: ["check_working_environment"],
  },
  { key: "evaluate", abbrev: "EVAL", label: "Evaluate", operations: ["evaluate_reproducibility"] },
  { key: "hbom", abbrev: "HBOM", label: "HBOM", operations: ["observe_hardware"] },
  {
    key: "seal",
    abbrev: "SEAL",
    label: "Seal",
    operations: ["seal_ree", "sign_ree", "sign_review"],
  },
  {
    key: "experiment",
    abbrev: "EXP",
    label: "Experiments",
    operations: ["run_experiment", "review_run_experiment"],
  },
] as const satisfies readonly RunHudTab[];

export type RunHudTabKey = (typeof RUN_HUD_TABS)[number]["key"];

export function runHudTabLabel(key: RunHudTabKey): string {
  return RUN_HUD_TABS.find((tab) => tab.key === key)?.label ?? key;
}

export function runHudTabForOperation(operation: ReeRunOperation): RunHudTabKey {
  const tab = RUN_HUD_TABS.find((t) =>
    (t.operations as readonly ReeRunOperation[]).includes(operation),
  );
  if (!tab) throw new Error(`No run HUD tab holds ${operation}`);
  return tab.key;
}

function newestFirst(runs: readonly ReeRunSummary[]): ReeRunSummary[] {
  return [...runs].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

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

export function newestActiveRun(runs: readonly ReeRunSummary[]): ReeRunSummary | undefined {
  return newestFirst(runs).find(isActiveReeRun);
}

export function newestRun(runs: readonly ReeRunSummary[]): ReeRunSummary | undefined {
  return newestFirst(runs)[0];
}

interface RunHudTabActivity {
  active: boolean;
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

export type RunTickerTone = "idle" | "active" | "succeeded" | "failed";

interface RunTicker {
  detail: string;
  tone: RunTickerTone;
}

export function runTicker(runs: readonly ReeRunSummary[]): RunTicker {
  const active = activeRunCount(runs);
  const featured = newestActiveRun(runs) ?? newestRun(runs);
  if (!featured) return { detail: "No runs yet", tone: "idle" };

  if (active > 1) return { detail: `${active} runs active`, tone: "active" };

  const label = runHudTabLabel(runHudTabForOperation(featured.operation));
  const tone: RunTickerTone =
    active > 0
      ? "active"
      : featured.status === "succeeded"
        ? "succeeded"
        : featured.status === "failed" || featured.status === "canceled"
          ? "failed"
          : "idle";
  return { detail: `${label} · ${featured.status}`, tone };
}
