import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ReeRunOperation, ReeRunSummary } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { CANVAS_NODES, type NodeZone } from "./canvasNodes";

// Which panel a run in flight belongs to, so the hub can show work happening
// where the user would go to look at it. This is the run-operation counterpart
// of `authoringDag`'s step→page map (`initialize_ree`/`load_ree_bundle` raise
// the lab itself rather than a station on it).
const PAGE_BY_OPERATION: ReadonlyMap<ReeRunOperation, AppShellPage> = new Map<
  ReeRunOperation,
  AppShellPage
>([
  ["acquire_source", PAGE.ACQUIRE_SOURCE],
  ["build_experiment_environment", PAGE.BUILD_EXPERIMENT_ENVIRONMENT],
  ["generate_sbom", PAGE.GENERATE_SBOM],
  // The cross-check is the second operation on the SBOM page.
  ["cross_check_sbom", PAGE.GENERATE_SBOM],
  ["activate_experiment_environment", PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT],
  ["observe_hardware", PAGE.OBSERVE_HARDWARE],
  ["evaluate_reproducibility", PAGE.EVALUATE_REPRODUCIBILITY],
  ["seal_ree", PAGE.SEAL_REE],
  ["run_experiment", PAGE.EXPERIMENTS],
]);

const ZONE_BY_PAGE: ReadonlyMap<AppShellPage, NodeZone> = new Map(
  CANVAS_NODES.map((node) => [node.key, node.zone]),
);

/**
 * What is happening on the hub right now: which panels have a run in flight,
 * and which of the pod's shells that work is happening inside. The zone falls
 * out of the node's own `zone` rather than a second table, so a panel that
 * moves shell keeps lighting the shell it belongs to.
 */
export interface CanvasActivity {
  /** Panels whose step is running. */
  nodeKeys: ReadonlySet<AppShellPage>;
  /** Pod shells with work happening inside them. */
  zones: ReadonlySet<NodeZone>;
}

export const NO_CANVAS_ACTIVITY: CanvasActivity = {
  nodeKeys: new Set<AppShellPage>(),
  zones: new Set<NodeZone>(),
};

/**
 * Reads the hub's live activity off the REE's run listing, so a run started
 * anywhere — this tab, another tab, a workbench service — lights the same panel.
 *
 * `alsoRunning` carries work that has not become a backend run yet, such as
 * flushing pending editor changes before the seal run starts.
 */
export function canvasActivity(
  runs: readonly ReeRunSummary[],
  alsoRunning: readonly AppShellPage[] = [],
): CanvasActivity {
  const nodeKeys = new Set<AppShellPage>();
  for (const run of runs) {
    if (isTerminalReeRunStatus(run.status)) continue;
    const page = PAGE_BY_OPERATION.get(run.operation);
    if (page) nodeKeys.add(page);
  }
  for (const page of alsoRunning) nodeKeys.add(page);

  const zones = new Set<NodeZone>();
  for (const key of nodeKeys) {
    const zone = ZONE_BY_PAGE.get(key);
    if (zone) zones.add(zone);
  }
  return { nodeKeys, zones };
}
