import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ReeRunOperation, ReeRunSummary } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { CANVAS_NODES, type NodeZone } from "./canvasNodes";

// Which panel a run in flight belongs to, so the hub can show work happening
// where the user would go to look at it. This is the run-operation counterpart
// of `authoringDag`'s step→page map: the two vocabularies overlap but are not
// the same (`swh`/`zenodo`/`dataverse` are three operations behind one panel,
// and `provision`/`ree-load` raise the lab itself rather than a station on it).
const PAGE_BY_OPERATION: Readonly<Partial<Record<ReeRunOperation, AppShellPage>>> = {
  source: PAGE.SOURCE,
  build: PAGE.BUILD,
  sbom: PAGE.SBOM,
  // The cross-check is the second operation on the SBOM page.
  crosscheck: PAGE.SBOM,
  activation: PAGE.ACTIVATION,
  hbom: PAGE.HBOM,
  evaluate: PAGE.EVALUATE,
  swh: PAGE.ARCHIVE,
  zenodo: PAGE.ARCHIVE,
  dataverse: PAGE.ARCHIVE,
  experiment: PAGE.EXPERIMENTS,
};

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
 * anywhere — this tab, another tab, an agent — lights the same panel.
 *
 * `alsoRunning` carries the work that is not a backend run: sealing is driven
 * from the client and has no entry in the listing, but it is a panel on the
 * hub like any other.
 */
export function canvasActivity(
  runs: readonly ReeRunSummary[],
  alsoRunning: readonly AppShellPage[] = [],
): CanvasActivity {
  const nodeKeys = new Set<AppShellPage>();
  for (const run of runs) {
    if (isTerminalReeRunStatus(run.status)) continue;
    const page = PAGE_BY_OPERATION[run.operation];
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
