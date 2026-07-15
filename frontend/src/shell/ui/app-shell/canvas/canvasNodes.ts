import { axisStandings, axisStepLabel } from "@core/evaluate/axes";
import { hbomHasAnyComponents } from "@core/hbom/HbomSummary";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { Ic } from "../../shared/components/Icon";
import { PROCESS_STEPS, resolveNavCompleted } from "../sidebar/processSteps";
import { type AppShellPage, PAGE } from "../state/pages";

// A canvas node is a page floating around the pod in the hub. `kind` keeps the
// declarations/evidence split: things you DECLARE cluster left, evidence the
// system RETURNS clusters right. `x`/`y` are canvas coordinates with the pod at
// the origin (0,0). `color`/`shadow` drive its cable to the pod.
// `zone` groups nodes into concentric shells around the pod for the master
// view: `core` is the experiment itself, `inner` the execution substrate it
// runs on, `outer` the provenance/credential membrane around the whole thing.
export type NodeZone = "outer" | "inner" | "core";

export interface CanvasNode {
  key: AppShellPage;
  label: string;
  kind: "setup" | "declare" | "evidence";
  zone: NodeZone;
  x: number;
  y: number;
  /** Override x position used only in the decomposed (exploded) view. */
  xExploded?: number;
  color: string;
  shadow: string;
  icon: (size?: number) => JSX.Element;
}

// The Workbench is absent from the ring on purpose: it IS the canvas — the lab
// the pod sits in. Its setup lives in WorkbenchLab (pre-provision) and the
// bench nameplate on the hub (post-provision).
export const CANVAS_NODES: CanvasNode[] = [
  {
    key: PAGE.SOURCE,
    label: "Source",
    kind: "declare",
    zone: "outer",
    x: -312,
    y: -150,
    xExploded: 312,
    color: "#f59e0b",
    shadow: "#92400e",
    icon: Ic.globe,
  },
  {
    key: PAGE.METADATA,
    label: "Metadata",
    kind: "declare",
    zone: "outer",
    x: -378,
    y: -16,
    color: "#22c55e",
    shadow: "#166534",
    icon: Ic.grid,
  },
  {
    key: PAGE.HBOM,
    label: "Hardware",
    kind: "declare",
    zone: "inner",
    x: -330,
    y: 120,
    color: "#0f766e",
    shadow: "#134e4a",
    icon: Ic.chip,
  },
  {
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    kind: "declare",
    zone: "core",
    x: -190,
    y: 236,
    color: "#4f46e5",
    shadow: "#3730a3",
    icon: Ic.terminal,
  },
  {
    key: PAGE.EVALUATE,
    label: "Reproducibility Readiness",
    kind: "evidence",
    zone: "inner",
    x: 312,
    y: -150,
    color: "#7c3aed",
    shadow: "#3b0764",
    icon: Ic.star,
  },
  // Build / SBOM / Activation are the three facets of the runtime — the inner
  // shell. They are plain inner-shell members (each cables to the inner shell),
  // not a node-to-node chain. Direction is read from their layout: Build sits at
  // the inlet (nearest the pod / the source-facing side), and SBOM + Activation
  // sit downstream toward the core, since they consume the artifact Build emits.
  {
    key: PAGE.BUILD,
    label: "Build",
    kind: "evidence",
    zone: "inner",
    x: 340,
    y: 0,
    xExploded: -340,
    color: "#0891b2",
    shadow: "#164e63",
    icon: Ic.cpu,
  },
  {
    key: PAGE.SBOM,
    label: "SBOM",
    kind: "evidence",
    zone: "inner",
    x: 520,
    y: -58,
    color: "#16a34a",
    shadow: "#14532d",
    icon: Ic.package,
  },
  {
    key: PAGE.ACTIVATION,
    label: "Activation",
    kind: "evidence",
    zone: "inner",
    x: 520,
    y: 75,
    color: "#7c3aed",
    shadow: "#3b0764",
    icon: Ic.shield,
  },
  {
    key: PAGE.ARCHIVE,
    label: "Archive",
    kind: "evidence",
    zone: "outer",
    x: 330,
    y: 120,
    color: "#e4572e",
    shadow: "#7c2d12",
    icon: Ic.archive,
  },
  {
    key: PAGE.SEAL,
    label: "Seal",
    kind: "evidence",
    zone: "outer",
    x: 190,
    y: 236,
    color: "#b91c1c",
    shadow: "#7f1d1d",
    icon: Ic.lock,
  },
];

// Exploded ("decomposed") view: each shell becomes its own column to the right,
// drawn at a decreasing scale so the single pod graphic reads as magnification
// levels (full artifact → substrate → core). Each column is a real pod entity
// the cable geometry anchors to, so cables land on that column's pod surface.
interface ProjectionLayer {
  zone: NodeZone;
  label: string;
  sub: string;
  /** World-x of the column centre (pod sits here). */
  cx: number;
  /** Size of the column's POD relative to the full pod — the shrinking
   *  "magnification levels" look. Panels stay full-size regardless (see
   *  nodeProjection), so they read the same in every column. */
  scale: number;
}
export const EXPLODE_BASE_POD = 760;
// Must stay above ZOOM_MIN in useCanvasViewport so focusView can reach it.
export const EXPLODE_ZOOM = 0.42;
// World-x the camera centres on when decomposed (mid-point of the spread).
export const EXPLODE_CENTER = 1250;
export const EXPLODE_LAYERS: ProjectionLayer[] = [
  { zone: "outer", label: "Outer shell", sub: "describe · certify · seal", cx: 0, scale: 1 },
  { zone: "inner", label: "Inner shell", sub: "execution substrate", cx: 1400, scale: 0.58 },
  { zone: "core", label: "Core", sub: "the experiment", cx: 2500, scale: 0.38 },
];
const LAYER_BY_ZONE = new Map<NodeZone, ProjectionLayer>(
  EXPLODE_LAYERS.map((layer) => [layer.zone, layer]),
);

export interface NodeProjection {
  dx: number;
  dy: number;
  scale: number;
}

// Where a node sits in the exploded view: its shell's full-size cluster is
// translated bodily into that shell's column. Panels keep full size (scale 1) so
// they read identically in every column — only the pod they orbit shrinks. The
// card's relative spread (node.x/node.y) is preserved; we just shift it so its
// origin lands on the column centre. Assembled view is the identity.
// xExploded overrides node.x for the decomposed position only.
export function nodeProjection(node: CanvasNode, exploded: boolean): NodeProjection {
  const layer = LAYER_BY_ZONE.get(node.zone);
  if (!exploded || !layer) return { dx: 0, dy: 0, scale: 1 };
  const ex = node.xExploded ?? node.x;
  // Card CSS left is node.x; shift so its centre lands at layer.cx + ex.
  return { dx: layer.cx + (ex - node.x), dy: 0, scale: 1 };
}

const STEP_BY_KEY = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

// A node reflects "done" from the same lifecycle source of truth the rail used.
export function isNodeDone(node: CanvasNode, ree: ReeEditorViewModel, badges: Badges): boolean {
  const step = STEP_BY_KEY.get(node.key);
  return step ? resolveNavCompleted(step, ree, badges) : false;
}

// Every node lives inside the workbench, so nothing on the ring is reachable
// until the workbench (the lab) is provisioned.
export function isNodeLocked(_node: CanvasNode, provisioned: boolean): boolean {
  return !provisioned;
}

export function isNodeActive(node: CanvasNode, page: AppShellPage): boolean {
  return page === node.key;
}

export function activeNode(page: AppShellPage): CanvasNode | undefined {
  return CANVAS_NODES.find((node) => isNodeActive(node, page));
}

export interface SummaryRow {
  label: string;
  value: string | null;
  /** Full text shown on hover when `value` is a shortened form. */
  title?: string;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] || url;
  }
}

// Per-node summary: the headline facts a node shows before the user dives in.
export function nodeSummary(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
): SummaryRow[] {
  switch (node.key) {
    case PAGE.SOURCE: {
      // Once a source is in the workspace, surface the backend-computed stats;
      // before that, fall back to the declared origin so the card isn't empty.
      const repo = ree.sourceAvailable ? sourceRepo : undefined;
      return [
        { label: "Name", value: repo?.name ?? null },
        { label: "Size", value: repo?.sizeLabel ?? null },
        {
          label: "Origin",
          value: repo ? hostOf(repo.origin) : ree.originUrl ? hostOf(ree.originUrl) : null,
        },
        { label: "SWHID", value: repo?.swhid || null, title: repo?.swhid },
      ];
    }
    case PAGE.METADATA:
      return [
        { label: "Name", value: ree.name || null },
        { label: "Version", value: ree.catalogMetadata?.version || null },
      ];
    case PAGE.HBOM:
      return [
        {
          label: "Components",
          value: hbomHasAnyComponents(ree.hardwareDescription) ? "described" : null,
        },
      ];
    case PAGE.EXPERIMENTS: {
      const count = (ree.experiments ?? []).filter((entry) => entry.runScript.trim() !== "").length;
      return [{ label: "Run scripts", value: count > 0 ? `${count} defined` : null }];
    }
    case PAGE.EVALUATE:
      // Always surface each axis's standing — level 0 reads as "None", so the
      // three axes are visible whether or not the REE has been scored yet.
      return axisStandings(ree).map(({ axis, level }) => ({
        label: axis.label,
        value: axisStepLabel(axis, level),
      }));
    case PAGE.BUILD:
      return [
        {
          label: "Runtime",
          value: ree.runtime && ree.runtime !== "__skipped__" ? "image ready" : null,
        },
      ];
    case PAGE.SBOM:
      return [{ label: "SBOM", value: ree.sbom ? "inventoried" : null }];
    case PAGE.ACTIVATION:
      return [
        {
          label: "Run script",
          value: ree.activation?.runScript?.trim() ? "configured" : null,
        },
      ];
    case PAGE.ARCHIVE:
      return [
        { label: "DOI", value: ree.zenodoDoi || ree.dataverseDoi || null },
        { label: "SWHID", value: ree.swhid || null, title: ree.swhid },
      ];
    case PAGE.SEAL:
      return [{ label: "State", value: ree.sealedAt ? "sealed" : "draft" }];
    default:
      return [];
  }
}
