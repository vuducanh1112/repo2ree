import { PAGE } from "@core/app-shell/pages";
import {
  type Cable,
  type CableGeo,
  edgeToward,
  intercept,
  type PodGeom,
  type Point,
  type Rect,
  rectCenter,
} from "@core/canvas/cableGeometry";
import { CANVAS_NODES, type NodeZone } from "@core/canvas/canvasNodes";

/**
 * Which cables exist and where their ends land, given geometry someone else
 * measured. The measuring hooks read the DOM into one of these scenes and hand
 * it here; everything below is arithmetic and layout rules, so it is testable
 * without a browser.
 */
export interface CableScene {
  /** Stage size, carried through to the overlay's viewBox. */
  stage: { width: number; height: number };
  /** The assembled view's single pod. Also the fallback for any missing column. */
  mainPod: PodGeom;
  /** Column pods of the decomposed view. Absent zones fall back to `mainPod`. */
  projectionPods: Partial<Record<NodeZone, PodGeom>>;
  /** Measured panel boxes by node key. A node with no box gets no cable. */
  nodeRects: Partial<Record<string, Rect>>;
  /** Node keys whose step is complete — drives each cable's lit/dim look. */
  doneKeys: ReadonlySet<string>;
  exploded: boolean;
}

// Panels woven into the dependency chain don't also get a plain membership
// cable in the decomposed view — the chain already wires them up.
const CHAIN_KEYS: ReadonlySet<string> = new Set([PAGE.SOURCE, PAGE.BUILD, PAGE.ACTIVATION]);

/** A cable end: either a pod surface or a panel border. */
type Anchor = { kind: "pod"; pod: PodGeom } | { kind: "rect"; rect: Rect };

function anchorCenter(anchor: Anchor): Point {
  return anchor.kind === "pod" ? anchor.pod.center : rectCenter(anchor.rect);
}

function resolveAnchor(anchor: Anchor, toward: Point): Point {
  return anchor.kind === "pod"
    ? intercept(anchor.pod, toward.x, toward.y)
    : edgeToward(anchor.rect, toward.x, toward.y);
}

function podAnchor(pod: PodGeom | undefined): Anchor | null {
  return pod ? { kind: "pod", pod } : null;
}

function rectAnchor(rect: Rect | undefined): Anchor | null {
  return rect ? { kind: "rect", rect } : null;
}

/** Each shell anchors to its own column pod when decomposed; otherwise everything
 *  ties back to the main pod. The outer shell keeps the main pod either way —
 *  it *is* the whole artifact. */
function podForZone(scene: CableScene, zone: NodeZone): PodGeom {
  if (!scene.exploded || zone === "outer") return scene.mainPod;
  return scene.projectionPods[zone] ?? scene.mainPod;
}

function link(
  cables: Cable[],
  id: string,
  a: Anchor | null,
  b: Anchor | null,
  connected: boolean,
  color: string,
  shadow: string,
): void {
  if (!a || !b) return;
  const p1 = resolveAnchor(a, anchorCenter(b));
  const p2 = resolveAnchor(b, anchorCenter(a));
  cables.push({ id, x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y, connected, color, shadow });
}

/**
 * The dependency-chain spine, drawn only when decomposed. It traces the actual
 * data flow through specific panels rather than connecting pods directly:
 * outer shell -> source panel -> inner shell (the build runtime itself) ->
 * activation panel -> core. The inner shell stands in for the build runtime, so
 * the chain wires straight from the source panel into it — no separate build
 * panel.
 *
 * Pushed before the membership cables so the spine renders *under* them.
 */
function pushChainCables(cables: Cable[], scene: CableScene): void {
  const meta = new Map(
    CANVAS_NODES.filter((node) => CHAIN_KEYS.has(node.key)).map((n) => [n.key, n]),
  );
  const sourceNode = meta.get(PAGE.SOURCE);
  const buildNode = meta.get(PAGE.BUILD);
  const activationNode = meta.get(PAGE.ACTIVATION);
  if (!sourceNode || !buildNode || !activationNode) return;

  const source = rectAnchor(scene.nodeRects[PAGE.SOURCE]);
  const activation = rectAnchor(scene.nodeRects[PAGE.ACTIVATION]);
  const inner = podAnchor(scene.projectionPods.inner);
  const core = podAnchor(scene.projectionPods.core);
  const main = podAnchor(scene.mainPod);

  const sourceDone = scene.doneKeys.has(PAGE.SOURCE);
  const buildDone = scene.doneKeys.has(PAGE.BUILD);
  const activationDone = scene.doneKeys.has(PAGE.ACTIVATION);

  link(cables, "chain-outer-source", main, source, sourceDone, sourceNode.color, sourceNode.shadow);
  link(cables, "chain-source-inner", source, inner, buildDone, buildNode.color, buildNode.shadow);
  link(
    cables,
    "chain-inner-activation",
    inner,
    activation,
    activationDone,
    activationNode.color,
    activationNode.shadow,
  );
  link(
    cables,
    "chain-activation-core",
    activation,
    core,
    activationDone,
    activationNode.color,
    activationNode.shadow,
  );
}

/** One membership cable per node: panel edge facing its pod, pod end facing that knob. */
function pushMembershipCables(cables: Cable[], scene: CableScene): void {
  for (const node of CANVAS_NODES) {
    if (scene.exploded && CHAIN_KEYS.has(node.key)) continue;
    // Decomposed, the core column is taken over by per-experiment satellites
    // (CoreExperiments), each with its own cable — so the lone Experiments node
    // and its membership cable step aside.
    if (scene.exploded && node.key === PAGE.EXPERIMENTS) continue;
    const rect = scene.nodeRects[node.key];
    if (!rect) continue;
    const pod = podForZone(scene, node.zone);
    const panel = edgeToward(rect, pod.center.x, pod.center.y);
    const hit = intercept(pod, panel.x, panel.y);
    cables.push({
      id: node.key,
      x1: panel.x,
      y1: panel.y,
      x2: hit.x,
      y2: hit.y,
      color: node.color,
      shadow: node.shadow,
      connected: scene.doneKeys.has(node.key),
    });
  }
}

export function buildCables(scene: CableScene): CableGeo {
  const cables: Cable[] = [];
  if (scene.exploded) pushChainCables(cables, scene);
  pushMembershipCables(cables, scene);
  return { cables, w: scene.stage.width, h: scene.stage.height };
}

// One satellite's cable identity: what it ties to the core and how the cable
// should read (lit when the experiment is wired up, dim otherwise).
export interface CoreCableTarget {
  key: string;
  connected: boolean;
  color: string;
  shadow: string;
}

/**
 * The experiment canvas: one pod, a flat ring of satellites, no shells and no
 * chain. A focused twin of `buildCables` sharing all of its primitives.
 */
export interface ExperimentCableScene {
  stage: { width: number; height: number };
  corePod: PodGeom;
  targets: readonly CoreCableTarget[];
  /** Measured satellite boxes by target key. An unmeasured satellite is skipped. */
  satelliteRects: Partial<Record<string, Rect>>;
}

export function buildExperimentCables(scene: ExperimentCableScene): CableGeo {
  const cables: Cable[] = [];
  for (const target of scene.targets) {
    const rect = scene.satelliteRects[target.key];
    if (!rect) continue;
    const panel = edgeToward(rect, scene.corePod.center.x, scene.corePod.center.y);
    const hit = intercept(scene.corePod, panel.x, panel.y);
    cables.push({
      id: target.key,
      x1: panel.x,
      y1: panel.y,
      x2: hit.x,
      y2: hit.y,
      color: target.color,
      shadow: target.shadow,
      connected: target.connected,
    });
  }
  return { cables, w: scene.stage.width, h: scene.stage.height };
}
