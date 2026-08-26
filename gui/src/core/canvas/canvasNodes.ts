import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import {
  EVIDENCE_STEP_BY_PAGE,
  PROCESS_STEPS,
  resolveNavCompleted,
} from "@core/app-shell/processSteps";
import { axisStandings, axisStepLabel } from "@core/evaluate/axes";
import type { SbomCrossCheckSummary } from "@core/evaluate/Threat";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges } from "@core/ree/ReeTypes";
import { isEvidenceStale } from "@core/ree/StepEvidence";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { findFileByWorkspacePath } from "@core/workspace/fileTreeTraversal";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";

// A canvas node is a page standing on the bench around the pod. `zone` groups
// nodes into concentric shells for the pod's own readout: `core` is the
// experiment itself, `inner` the execution substrate it runs on, `outer` the
// provenance/credential membrane around the whole thing. A running step lights
// its shell (see canvasActivity and PodSphere).
//
// Placement is polar, not hand-typed: a node declares the `angle` it stands at
// and `RING` supplies the radii, so the layout is a rule rather than ten pairs
// of coordinates that drift out of agreement with each other. `x`/`y` fall out
// of that, with the pod at the origin (0,0). How a node and its cable read is
// keyed off `key` in the shell (see theme/tones.css), so the node carries no
// colour of its own.
export type NodeZone = "outer" | "inner" | "core";

/**
 * Which glyph a node shows, named rather than supplied. The node definitions are
 * functional-core data, so they carry the *key* and the shell resolves it to a
 * component — the same indirection `ReeStepIconKey` and `stepIcons.tsx` already
 * use for the pipeline steps.
 */
export type CanvasIconKey =
  | "globe"
  | "grid"
  | "chip"
  | "terminal"
  | "star"
  | "cpu"
  | "package"
  | "shield"
  | "archive"
  | "lock";

/**
 * The bench floor's tilt. The shell hands it to CSS as `--floor-tilt`, and the
 * projection helpers below read the same constant, so the geometry TypeScript
 * computes and the geometry the browser draws cannot disagree.
 */
export const FLOOR_TILT_DEGREES = 54;

/** The scene's perspective depth in world units; CSS receives it as `--scene-depth`. */
export const SCENE_DEPTH = 1900;

const TILT = (FLOOR_TILT_DEGREES * Math.PI) / 180;
const TILT_COS = Math.cos(TILT);
const TILT_SIN = Math.sin(TILT);

/**
 * The horseshoe the panels stand on, as an ellipse in world units.
 *
 * It is much wider than it is deep on purpose. The floor tilt compresses depth
 * on screen by cos(54°) ≈ 0.59, so a circle of this radius would render as an
 * ellipse anyway — but one sized by the *vertical* budget, which is the scarce
 * axis in a 16:9 viewport. Choosing the ellipse directly spends the width the
 * viewport actually has and keeps the height inside what it does not.
 */
export const RING = { rx: 790, ry: 470 } as const;

/**
 * A panel's box in world units, used for the layout bounds and the overlap
 * test. Deliberately conservative: the tallest card (Metadata, seven fact rows)
 * sets the height, so a box that clears its neighbours here clears them for
 * every node.
 */
const CARD_BOX = { width: 248, height: 210 } as const;

/** The deck plate a node's strut is bolted to, lying flat in the floor plane. */
const FLOOR_PLATE = { width: 152, height: 96 } as const;

/** The pod and its cradle, as a screen-space box around the floor origin. */
const POD_BOX = { halfWidth: 200, height: 360 } as const;

export interface CanvasNode {
  key: AppShellPage;
  label: string;
  zone: NodeZone;
  /**
   * Where the node stands on the ring, in degrees clockwise from the far side
   * of the bench (0° is directly behind the pod, 90° stage right, 180° directly
   * in front of it).
   */
  angle: number;
  /** Derived from `angle` and {@link RING}; the pod sits at (0, 0). */
  x: number;
  y: number;
  /** Height of the billboard's support above the 2.5D bench, in world units. */
  standHeight: number;
  iconKey: CanvasIconKey;
}

type CanvasNodePlacement = Omit<CanvasNode, "x" | "y">;

function ringPosition(angle: number): { x: number; y: number } {
  const radians = (angle * Math.PI) / 180;
  return {
    x: Math.round(RING.rx * Math.sin(radians)),
    y: Math.round(-RING.ry * Math.cos(radians)),
  };
}

/**
 * Panels are billboards: they counter-rotate to face the camera, so perspective
 * should not also be deciding how big their text is. A panel on the far side of
 * the bench would otherwise render at 0.83× and one at the front at 1.25× — a
 * 1.5× spread across the canvas, with the steps a user meets first (Source,
 * Reproducibility Readiness) landing at the small end.
 *
 * This is the exact inverse of the perspective scale at the node's depth, so
 * every panel resolves to the same size on screen while the floor, the posts,
 * the grid and the pod keep their depth. `BILLBOARD_CORRECTION` dials it back:
 * 1 cancels perspective outright, 0 leaves it alone.
 */
const BILLBOARD_CORRECTION = 1;

export function nodeScale(node: CanvasNode): number {
  const perspective = SCENE_DEPTH / (SCENE_DEPTH - node.y * TILT_SIN);
  return (1 / perspective) ** BILLBOARD_CORRECTION;
}

/**
 * Project a point on the bench floor into the units the camera layer pans and
 * zooms in: the tilt foreshortens depth, then perspective scales what is left
 * by how far away it ended up.
 *
 * The scene's `perspective-origin` sits at 48% rather than 50%, which shifts
 * every projected point by the same small amount. `fitBounds` centres on the
 * bounds it is given, so a uniform shift comes out in the wash.
 */
export function screenPointFromFloor(point: { x: number; y: number }): { x: number; y: number } {
  const perspective = SCENE_DEPTH / (SCENE_DEPTH - point.y * TILT_SIN);
  return { x: point.x * perspective, y: point.y * TILT_COS * perspective };
}

/**
 * The exact inverse of {@link screenPointFromFloor}, so a pointer dragging a
 * panel can be turned back into the spot on the floor it is over.
 *
 * Depth has to be recovered first, because the perspective divisor depends on
 * it. Writing the projection out and solving for y gives a closed form rather
 * than an iterative search:
 *
 *     sy = y·cos·D / (D − y·sin)   ⟹   y = sy·D / (cos·D + sy·sin)
 */
export function floorPointFromScreen(point: { x: number; y: number }): { x: number; y: number } {
  const y = (point.y * SCENE_DEPTH) / (TILT_COS * SCENE_DEPTH + point.y * TILT_SIN);
  const perspective = SCENE_DEPTH / (SCENE_DEPTH - y * TILT_SIN);
  return { x: point.x / perspective, y };
}

interface ScreenBox {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/**
 * Just the readable face of a panel, relative to the floor origin. This is the
 * box that must not overlap another node's: two cards on top of each other cost
 * the reader, whereas a strut crossing a neighbour's deck plate does not.
 *
 * The anchor is perspective-projected; the card is not, because
 * {@link nodeScale} has already cancelled the perspective inside the billboard.
 */
export function nodeCardBox(node: CanvasNode): ScreenBox {
  const anchor = screenPointFromFloor(node);
  const bottom = anchor.y - node.standHeight;
  return {
    left: anchor.x - CARD_BOX.width / 2,
    right: anchor.x + CARD_BOX.width / 2,
    top: bottom - CARD_BOX.height,
    bottom,
  };
}

/**
 * Everything one node puts on screen: the card, the strut holding it up, and
 * the deck plate the strut is bolted to. This is the box the view has to frame.
 *
 * The plate is not part of the billboard, so it takes the perspective at its
 * own near edge — which puts a panel's foot *below* its anchor. Measuring only
 * to the bottom of the card is what cut the feet off the front-most panels:
 * `fitView` framed a box that stopped where the card stopped.
 */
export function nodeScreenBox(node: CanvasNode): ScreenBox {
  const card = nodeCardBox(node);
  const plateNear = screenPointFromFloor({ x: node.x, y: node.y + FLOOR_PLATE.height / 2 });
  const halfWidth = Math.max(CARD_BOX.width, FLOOR_PLATE.width) / 2;
  const anchor = screenPointFromFloor(node);
  return {
    left: anchor.x - halfWidth,
    right: anchor.x + halfWidth,
    top: card.top,
    bottom: plateNear.y,
  };
}

/**
 * The box `fitView` frames, derived from the nodes themselves rather than
 * carried as a hand-maintained constant. The old constant declared 1240 units
 * of height against roughly 720 of content, and `fitBounds` dutifully zoomed
 * out to frame the padding — which is what shrank an 11px label to 7px on the
 * far side of the bench.
 */
export function canvasWorldBounds(nodes: readonly CanvasNode[] = CANVAS_NODES): {
  left: number;
  top: number;
  width: number;
  height: number;
} {
  let left: number = -POD_BOX.halfWidth;
  let right: number = POD_BOX.halfWidth;
  let top: number = -POD_BOX.height;
  let bottom = 0;
  for (const node of nodes) {
    const box = nodeScreenBox(node);
    left = Math.min(left, box.left);
    right = Math.max(right, box.right);
    top = Math.min(top, box.top);
    bottom = Math.max(bottom, box.bottom);
  }
  return { left, top, width: right - left, height: bottom - top };
}

// The Workbench is absent from the ring on purpose: it IS the canvas — the lab
// the pod sits in. Its setup lives in WorkbenchLab (pre-provision) and the
// bench nameplate on the hub (post-provision).
//
// The angles walk the authoring pipeline in order: Source enters stage left,
// the sequence sweeps clockwise over the far side and down the near right, and
// Seal — the last authoring step — lands at 180°, dead centre in front of the
// pod, where perspective renders a panel largest and the eye finishes. Archive
// trails just past it, off the authoring arc, because depositing happens after
// the REE is sealed rather than as part of building it. The remaining sector
// stays open on purpose: it is the canvas's breathing room, and where the file
// and receipt consoles dock.
//
// The spacing is even along the *screen* ellipse rather than even in angle. On
// an ellipse those are different things — equal angles bunch panels together at
// the ends of the major axis, which is exactly where this ring is busiest.
const CANVAS_NODE_PLACEMENTS: CanvasNodePlacement[] = [
  {
    key: PAGE.SOURCE,
    label: "Source",
    zone: "outer",
    angle: 265,
    standHeight: 96,
    iconKey: "globe",
  },
  {
    key: PAGE.METADATA,
    label: "Metadata",
    zone: "outer",
    angle: 314.2,
    standHeight: 150,
    iconKey: "grid",
  },
  {
    key: PAGE.HBOM,
    label: "Hardware",
    zone: "inner",
    angle: 342.4,
    standHeight: 100,
    iconKey: "chip",
  },
  {
    key: PAGE.EVALUATE,
    label: "Reproducibility Readiness",
    zone: "inner",
    angle: 7,
    standHeight: 164,
    iconKey: "star",
  },
  // Build / SBOM / Activation are the three facets of the runtime — the inner
  // shell. They are plain inner-shell members (each cables to the inner shell),
  // not a node-to-node chain. Direction is read from the arc: Build stands
  // first, and SBOM + Activation follow it, since they consume the artifact
  // Build emits.
  {
    key: PAGE.BUILD,
    label: "Build",
    zone: "inner",
    angle: 32.8,
    standHeight: 104,
    iconKey: "cpu",
  },
  {
    key: PAGE.SBOM,
    label: "SBOM",
    zone: "inner",
    angle: 68.3,
    standHeight: 168,
    iconKey: "package",
  },
  {
    key: PAGE.ACTIVATION,
    label: "Activation",
    zone: "inner",
    angle: 124.1,
    standHeight: 96,
    iconKey: "shield",
  },
  {
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    zone: "core",
    angle: 155,
    standHeight: 150,
    iconKey: "terminal",
  },
  {
    key: PAGE.SEAL,
    label: "Seal",
    zone: "outer",
    angle: 180,
    standHeight: 104,
    iconKey: "lock",
  },
  {
    key: PAGE.ARCHIVE,
    label: "Archive",
    zone: "outer",
    angle: 214,
    standHeight: 96,
    iconKey: "archive",
  },
];

export const CANVAS_NODES: CanvasNode[] = CANVAS_NODE_PLACEMENTS.map((placement) => ({
  ...placement,
  ...ringPosition(placement.angle),
}));

const STEP_BY_KEY = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

// A node reflects "done" from the same lifecycle source of truth the rail used.
export function isNodeDone(node: CanvasNode, ree: ReeEditorViewModel, badges: Badges): boolean {
  const step = STEP_BY_KEY.get(node.key);
  return step ? resolveNavCompleted(step, ree, badges) : false;
}

/**
 * A node whose receipt no longer speaks for the REE — an edited build script,
 * a re-pointed source. `isNodeDone` already reads false for these; this says
 * *why*, so the card can show STALE rather than a plain "not run yet".
 */
export function isNodeStale(node: CanvasNode, ree: ReeEditorViewModel): boolean {
  const step = EVIDENCE_STEP_BY_PAGE[node.key];
  return step ? isEvidenceStale(ree.audit, step) : false;
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

export interface CanvasScriptPreview {
  key: string;
  label: string;
  path: string;
  /** A deliberately short, exact preview of the saved workspace file. */
  lines: readonly string[];
  available: boolean;
}

export interface CanvasReceiptSummary {
  count: number;
  label: string;
  duration: string;
  recordedAt: string;
  /** Script digest recorded by the operation, already abbreviated for display. */
  scriptDigest: string;
}

export interface CanvasNodeOverview {
  facts: SummaryRow[];
  scripts: CanvasScriptPreview[];
  evidenceExpected: boolean;
  receipt: CanvasReceiptSummary | null;
}

interface CanvasNodeOverviewContext {
  workspaceFiles?: FileTreeNode[];
  receipts?: ReceiptView[];
  /** Backend-owned reserved path published by the script-template catalog. */
  buildScriptPath?: string;
  crossCheck?: SbomCrossCheckSummary | null;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] || url;
  }
}

function abbreviate(value: string): string {
  return value.length > 20 ? `${value.slice(0, 16)}…` : value;
}

function basename(path: string): string {
  return path.split("/").at(-1) || path;
}

// Per-node summary: the headline facts a node shows before the user dives in.
export function nodeSummary(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
  context: CanvasNodeOverviewContext = {},
): SummaryRow[] {
  switch (node.key) {
    case PAGE.SOURCE: {
      // Once a source is in the workspace, surface the backend-computed stats;
      // before that, fall back to the declared origin so the card isn't empty.
      const repo = ree.source.sourceAvailable ? sourceRepo : undefined;
      return [
        { label: "Size", value: repo?.sizeLabel ?? null },
        {
          label: "Origin",
          value: repo
            ? hostOf(repo.origin)
            : ree.spec.originUrl
              ? hostOf(ree.spec.originUrl)
              : null,
        },
        { label: "SWHID", value: repo?.swhid || null, title: repo?.swhid },
      ];
    }
    case PAGE.METADATA:
      return [
        { label: "Name", value: ree.spec.name || null },
        { label: "Description", value: ree.spec.catalogMetadata?.description || null },
        { label: "Version", value: ree.spec.catalogMetadata?.version || null },
        { label: "Website", value: ree.spec.catalogMetadata?.website || null },
        {
          label: "Keywords",
          value: ree.spec.catalogMetadata?.keywords.length
            ? ree.spec.catalogMetadata.keywords.join(", ")
            : null,
        },
        {
          label: "Contributors",
          value: ree.spec.catalogMetadata?.contributors.length
            ? ree.spec.catalogMetadata.contributors
                .map((contributor) => contributor.name || contributor.identifier)
                .join(", ")
            : null,
        },
        {
          label: "Corresponding author",
          value: ree.spec.catalogMetadata?.correspondingAuthorIdentifier || null,
        },
      ];
    case PAGE.HBOM: {
      const hbom = ree.spec.hardwareDescription;
      const cpus = Object.values(hbom.cpus).reduce((total, cpu) => total + cpu.quantity, 0);
      const cores = Object.values(hbom.cpus).reduce(
        (total, cpu) => total + cpu.quantity * cpu.coresPerCpu,
        0,
      );
      const memory = Object.values(hbom.memory).reduce(
        (total, item) => total + item.quantity * item.capacityGb,
        0,
      );
      const gpus = Object.values(hbom.gpus).reduce((total, gpu) => total + gpu.quantity, 0);
      const storage = Object.values(hbom.storage).reduce(
        (total, item) => total + item.quantity * item.capacityGb,
        0,
      );
      const network = Object.values(hbom.network).reduce(
        (total, item) => total + item.quantity * item.bandwidthGbps,
        0,
      );
      return [
        {
          label: "Compute",
          value: cpus ? `${cpus} CPU · ${cores} cores` : null,
        },
        { label: "Memory", value: memory ? `${memory} GB` : null },
        { label: "GPU", value: gpus ? String(gpus) : null },
        { label: "Storage", value: storage ? `${storage} GB` : null },
        { label: "Network", value: network ? `${network} Gbps` : null },
      ];
    }
    case PAGE.EXPERIMENTS: {
      const experiments = ree.spec.experiments ?? [];
      const count = experiments.filter((entry) => entry.runScript?.trim()).length;
      const verifyCount = experiments.filter((entry) => entry.verifyScript?.trim()).length;
      return [
        { label: "Experiments", value: experiments.length ? String(experiments.length) : null },
        { label: "Run scripts", value: count > 0 ? `${count} defined` : null },
        { label: "Verify", value: verifyCount > 0 ? `${verifyCount} defined` : null },
      ];
    }
    case PAGE.EVALUATE:
      // Always surface each axis's standing — level 0 reads as "None", so the
      // three axes are visible whether or not the REE has been scored yet.
      return [
        ...axisStandings(ree.evaluation).map(({ axis, level }) => ({
          label: axis.label,
          value: axisStepLabel(axis, level),
        })),
        {
          label: "Detected deps",
          value: ree.evaluation.detectedDependencies || null,
        },
      ];
    case PAGE.BUILD:
      return [
        {
          label: "Runtime",
          value: ree.spec.runtime && ree.spec.runtime !== "__skipped__" ? "image ready" : null,
        },
      ];
    case PAGE.SBOM: {
      const sbom = ree.spec.sbom || "";
      const crossCheck = context.crossCheck;
      return [
        {
          label: "SBOM",
          value: sbom ? abbreviate(basename(sbom)) : null,
          title: sbom || undefined,
        },
        {
          label: "Cross-check",
          value: crossCheck
            ? `${crossCheck.observedMatched}/${crossCheck.observedTotal} matched`
            : null,
        },
      ];
    }
    case PAGE.ACTIVATION:
      return [
        {
          label: "Run",
          value: ree.spec.activation?.runScript?.trim() ? "configured" : null,
        },
        {
          label: "Verify",
          value: ree.spec.activation?.verifyScript?.trim() ? "configured" : null,
        },
      ];
    case PAGE.ARCHIVE:
      return [
        { label: "DOI", value: null },
        { label: "SWHID", value: ree.spec.swhid || null, title: ree.spec.swhid },
      ];
    case PAGE.SEAL: {
      const hash = ree.artifact.sealHash || "";
      return [
        { label: "State", value: ree.artifact.sealedAt ? "sealed" : "draft" },
        { label: "Hash", value: hash ? abbreviate(hash) : null, title: hash || undefined },
      ];
    }
    default:
      return [];
  }
}

const RECEIPT_OPERATIONS_BY_PAGE: Readonly<Partial<Record<AppShellPage, readonly string[]>>> = {
  [PAGE.SOURCE]: ["acquire_source"],
  [PAGE.HBOM]: ["observe_hardware"],
  [PAGE.EVALUATE]: ["evaluate_reproducibility"],
  [PAGE.BUILD]: ["build_runtime"],
  [PAGE.SBOM]: ["generate_sbom", "cross_check_sbom"],
  // Keep the old spelling readable for REEs written before the contract name settled.
  [PAGE.ACTIVATION]: ["test_activation", "activation_test"],
  [PAGE.EXPERIMENTS]: ["run_experiment"],
};

function receiptField(receipt: ReceiptView, key: string): string {
  return receipt.fields.find((field) => field.key === key)?.value ?? "";
}

function scriptDigest(node: CanvasNode, receipt: ReceiptView): string {
  if (node.key === PAGE.BUILD) return receiptField(receipt, "build_runtime_script_digest");
  if (node.key === PAGE.ACTIVATION || node.key === PAGE.EXPERIMENTS) {
    return receiptField(receipt, "run_script_digest");
  }
  return "";
}

function receiptSummary(
  node: CanvasNode,
  receipts: readonly ReceiptView[],
  experimentCount: number,
): CanvasReceiptSummary | null {
  const operations = RECEIPT_OPERATIONS_BY_PAGE[node.key] ?? [];
  const matching = receipts.filter((receipt) => operations.includes(receipt.operation));
  if (!matching.length) return null;
  const latest = [...matching].sort((left, right) =>
    right.recordedAt.localeCompare(left.recordedAt),
  )[0];
  const label =
    node.key === PAGE.EXPERIMENTS && experimentCount > 0
      ? `${matching.length}/${experimentCount} receipts`
      : matching.length === 1
        ? "receipt recorded"
        : `${matching.length} receipts`;
  return {
    count: matching.length,
    label,
    duration: latest.duration,
    recordedAt: latest.recordedAt,
    scriptDigest: scriptDigest(node, latest),
  };
}

function previewLines(content: string | undefined, limit: number): readonly string[] {
  if (!content?.trim()) return [];
  return content.replace(/\r\n/g, "\n").trimEnd().split("\n").slice(0, limit);
}

function scriptPreview(
  files: FileTreeNode[],
  key: string,
  label: string,
  path: string | null | undefined,
  lineLimit: number,
): CanvasScriptPreview {
  const settledPath = path?.trim() ?? "";
  const file = settledPath ? findFileByWorkspacePath(files, settledPath) : null;
  return {
    key,
    label,
    path: settledPath,
    lines: previewLines(file?.content, lineLimit),
    available: !!file?.content?.trim(),
  };
}

/**
 * The canvas projection of a page: saved inputs plus the materialised evidence
 * those exact inputs produced. It stays read-only; editing remains in the drawer.
 */
export function nodeOverview(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
  context: CanvasNodeOverviewContext = {},
): CanvasNodeOverview {
  const files = context.workspaceFiles ?? [];
  const experiments = ree.spec.experiments ?? [];
  let scripts: CanvasScriptPreview[] = [];

  if (node.key === PAGE.BUILD) {
    scripts = [scriptPreview(files, "build", "BUILD SCRIPT", context.buildScriptPath, 3)];
  } else if (node.key === PAGE.ACTIVATION) {
    scripts = [
      scriptPreview(files, "activation-run", "RUN SCRIPT", ree.spec.activation.runScript, 2),
      scriptPreview(
        files,
        "activation-verify",
        "VERIFY SCRIPT",
        ree.spec.activation.verifyScript,
        1,
      ),
    ];
  } else if (node.key === PAGE.EXPERIMENTS) {
    scripts = experiments.map((experiment, index) =>
      scriptPreview(
        files,
        `experiment-${index}`,
        experiment.name.trim() || `EXPERIMENT ${index + 1}`,
        experiment.runScript,
        1,
      ),
    );
  }

  return {
    facts: nodeSummary(node, ree, sourceRepo, context),
    scripts,
    evidenceExpected: !!RECEIPT_OPERATIONS_BY_PAGE[node.key]?.length,
    receipt: receiptSummary(node, context.receipts ?? [], experiments.length),
  };
}
