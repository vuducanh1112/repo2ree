import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ReeRunOperation } from "@core/generated/vocabulary";
import type { ReeRunSummary } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { CANVAS_NODES, type NodeZone } from "./canvasNodes";

const PAGE_BY_OPERATION: ReadonlyMap<ReeRunOperation, AppShellPage> = new Map<
  ReeRunOperation,
  AppShellPage
>([
  ["acquire_source", PAGE.ACQUIRE_SOURCE],
  ["build_experiment_environment", PAGE.BUILD_EXPERIMENT_ENVIRONMENT],
  ["generate_sbom", PAGE.GENERATE_SBOM],
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

export interface CanvasActivity {
  nodeKeys: ReadonlySet<AppShellPage>;
  zones: ReadonlySet<NodeZone>;
}

export const NO_CANVAS_ACTIVITY: CanvasActivity = {
  nodeKeys: new Set<AppShellPage>(),
  zones: new Set<NodeZone>(),
};

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
