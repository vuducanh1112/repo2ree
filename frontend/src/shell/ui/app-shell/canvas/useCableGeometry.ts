import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useCallback, useEffect, useState } from "react";
import { PAGE } from "../state/pages";
import type { Cable, CableGeo } from "./cableGeometry";
import { CANVAS_NODES, isNodeDone, type NodeZone } from "./canvasNodes";
import type { NodeOffsets, Transform } from "./useCanvasViewport";

// Pod sphere geometry inside PodWidget's 580-unit viewBox (centre + radius).
const POD_CX = 290;
const POD_CY = 290;
const POD_SR = 118;
// Safety ceiling for the per-frame measure loop: `transitionend` is the real
// stop signal, but a clamped zoom can leave the transform unchanged so no
// transition runs and no event fires — bail out after this either way.
const ANIM_FALLBACK_MS = 800;

interface CableGeometryOptions {
  stageRef: React.RefObject<HTMLDivElement>;
  podSvgRef: React.RefObject<SVGSVGElement>;
  worldRef: React.RefObject<HTMLDivElement>;
  nodeEls: React.MutableRefObject<Record<string, HTMLButtonElement | null>>;
  ree: ReeEditorViewModel;
  badges: Badges;
  // `tf` and `nodeOffsets` are re-measure triggers, not inputs: measure reads the
  // resulting DOM transform via getScreenCTM rather than these values directly.
  tf: Transform;
  nodeOffsets: NodeOffsets;
  animate: boolean;
  /** When true, each shell's cables anchor to its own decomposed column pod. */
  exploded: boolean;
  /** Projection pod elements (inner/core columns) the cables anchor to when exploded. */
  projectionPods: Partial<Record<NodeZone, React.RefObject<SVGSVGElement>>>;
}

// Measures cable endpoints between each node card and the pod's surface in the
// stage's screen space (so the world layer's pan/zoom transform is absorbed),
// then feeds the shared Overview cable look.
export function useCableGeometry({
  stageRef,
  podSvgRef,
  worldRef,
  nodeEls,
  ree,
  badges,
  tf,
  nodeOffsets,
  animate,
  exploded,
  projectionPods,
}: CableGeometryOptions): CableGeo | null {
  const [geo, setGeo] = useState<CableGeo | null>(null);

  const measure = useCallback(() => {
    const stage = stageRef.current;
    const podSvg = podSvgRef.current;
    if (!stage || !podSvg) return;
    const cRect = stage.getBoundingClientRect();

    // Centre + on-screen radius of a pod SVG, in the stage's coordinate space.
    const podGeom = (svg: SVGSVGElement | null) => {
      const ctm = svg?.getScreenCTM();
      if (!ctm) return null;
      const at = (vx: number, vy: number) => ({
        x: ctm.a * vx + ctm.c * vy + ctm.e - cRect.left,
        y: ctm.b * vx + ctm.d * vy + ctm.f - cRect.top,
      });
      const center = at(POD_CX, POD_CY);
      const edge = at(POD_CX + POD_SR, POD_CY);
      return { center, radius: Math.hypot(edge.x - center.x, edge.y - center.y) };
    };

    const mainPod = podGeom(podSvg);
    if (!mainPod) return;
    // Each shell anchors to its own column pod when exploded; otherwise everything
    // ties back to the main pod.
    const podForZone = (zone: NodeZone) => {
      if (!exploded || zone === "outer") return mainPod;
      return podGeom(projectionPods[zone]?.current ?? null) ?? mainPod;
    };
    type PodGeom = { center: { x: number; y: number }; radius: number };
    type Rect = { left: number; right: number; top: number; bottom: number };

    const intercept = (pod: PodGeom, x: number, y: number) => {
      const dx = x - pod.center.x;
      const dy = y - pod.center.y;
      const len = Math.hypot(dx, dy) || 1;
      return {
        x: pod.center.x + (dx / len) * pod.radius,
        y: pod.center.y + (dy / len) * pod.radius,
      };
    };

    const rectOf = (key: string): Rect | null => {
      const el = nodeEls.current[key];
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        left: r.left - cRect.left,
        right: r.right - cRect.left,
        top: r.top - cRect.top,
        bottom: r.bottom - cRect.top,
      };
    };

    // The point on a panel's border along the ray toward (tx,ty): the knob
    // rides the edge that faces whatever the panel is wired to.
    const edgeToward = (rect: Rect, tx: number, ty: number) => {
      const cx = (rect.left + rect.right) / 2;
      const cy = (rect.top + rect.bottom) / 2;
      const dx = tx - cx;
      const dy = ty - cy;
      const hw = (rect.right - rect.left) / 2;
      const hh = (rect.bottom - rect.top) / 2;
      if ((dx === 0 && dy === 0) || hw === 0 || hh === 0) return { x: cx, y: cy };
      const scale = 1 / Math.max(Math.abs(dx) / hw, Math.abs(dy) / hh);
      return { x: cx + dx * scale, y: cy + dy * scale };
    };

    // Panels woven into the dependency chain don't also get a plain membership
    // cable in the decomposed view — the chain already wires them up.
    const CHAIN_KEYS = new Set<string>([PAGE.SOURCE, PAGE.BUILD, PAGE.ACTIVATION]);

    // Dependency chain spine, drawn only when decomposed (pushed first so they
    // render under member cables). Traces the actual data flow through specific
    // panels rather than connecting pods directly: outer shell → source panel →
    // inner shell (the build runtime itself) → test activation panel → core.
    const cables: Cable[] = [];

    if (exploded) {
      const innerPod = podGeom(projectionPods.inner?.current ?? null);
      const corePod = podGeom(projectionPods.core?.current ?? null);

      type Anchor = { kind: "pod"; pod: PodGeom } | { kind: "rect"; rect: Rect };

      const podAnchor = (pod: PodGeom | null): Anchor | null => (pod ? { kind: "pod", pod } : null);
      const rectAnchor = (rect: Rect | null): Anchor | null =>
        rect ? { kind: "rect", rect } : null;

      const anchorCenter = (a: Anchor) =>
        a.kind === "pod"
          ? a.pod.center
          : { x: (a.rect.left + a.rect.right) / 2, y: (a.rect.top + a.rect.bottom) / 2 };

      const resolve = (a: Anchor, toward: { x: number; y: number }) =>
        a.kind === "pod"
          ? intercept(a.pod, toward.x, toward.y)
          : edgeToward(a.rect, toward.x, toward.y);

      const link = (
        id: string,
        a: Anchor | null,
        b: Anchor | null,
        connected: boolean,
        color: string,
        shadow: string,
      ) => {
        if (!a || !b) return;
        const p1 = resolve(a, anchorCenter(b));
        const p2 = resolve(b, anchorCenter(a));
        cables.push({ id, x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y, connected, color, shadow });
      };

      const chainNodeMeta = new Map(
        CANVAS_NODES.filter((n) => CHAIN_KEYS.has(n.key)).map((n) => [n.key, n]),
      );
      const sourceNode = chainNodeMeta.get(PAGE.SOURCE);
      const buildNode = chainNodeMeta.get(PAGE.BUILD);
      const activationNode = chainNodeMeta.get(PAGE.ACTIVATION);
      if (!sourceNode || !buildNode || !activationNode) return;
      const sourceDone = isNodeDone(sourceNode, ree, badges);
      const buildDone = isNodeDone(buildNode, ree, badges);
      const activationDone = isNodeDone(activationNode, ree, badges);

      const source = rectAnchor(rectOf(PAGE.SOURCE));
      const activation = rectAnchor(rectOf(PAGE.ACTIVATION));

      // outer shell → source → inner shell (build runtime) → activation → core.
      // The inner shell stands in for the build runtime here, so the chain wires
      // straight from the source panel into it — no separate build panel.
      link(
        "chain-outer-source",
        podAnchor(mainPod),
        source,
        sourceDone,
        sourceNode.color,
        sourceNode.shadow,
      );
      link(
        "chain-source-inner",
        source,
        podAnchor(innerPod),
        buildDone,
        buildNode.color,
        buildNode.shadow,
      );
      link(
        "chain-inner-activation",
        podAnchor(innerPod),
        activation,
        activationDone,
        activationNode.color,
        activationNode.shadow,
      );
      link(
        "chain-activation-core",
        activation,
        podAnchor(corePod),
        activationDone,
        activationNode.color,
        activationNode.shadow,
      );
    }

    for (const node of CANVAS_NODES) {
      if (exploded && CHAIN_KEYS.has(node.key)) continue;
      // Decomposed, the core column is taken over by per-experiment satellites
      // (CoreExperiments), each with its own cable — so the lone Experiments
      // node and its membership cable step aside.
      if (exploded && node.key === PAGE.EXPERIMENTS) continue;
      const rect = rectOf(node.key);
      if (!rect) continue;
      const pod = podForZone(node.zone);
      // Knob rides the panel edge facing the pod; the pod end faces that knob.
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
        connected: isNodeDone(node, ree, badges),
      });
    }

    setGeo({ cables, w: cRect.width, h: cRect.height });
  }, [stageRef, podSvgRef, nodeEls, ree, badges, exploded, projectionPods]);

  // Re-measure on every transform/offset/data change. While `animate` is on, the
  // world layer eases its transform, so we measure each frame until that
  // transition ends — otherwise cables snap to the start frame and only catch up
  // on the next render.
  // biome-ignore lint/correctness/useExhaustiveDependencies: tf/nodeOffsets drive re-measurement
  useEffect(() => {
    let raf = requestAnimationFrame(measure);
    if (!animate) return () => cancelAnimationFrame(raf);

    const world = worldRef.current;
    let running = true;
    const loop = () => {
      measure();
      if (running) raf = requestAnimationFrame(loop);
    };
    // Only the world layer's own `transform` transition stops us — ignore
    // bubbled transitionend from child cards (box-shadow/opacity/etc.).
    const onEnd = (event: TransitionEvent) => {
      if (event.target === world && event.propertyName === "transform") running = false;
    };
    raf = requestAnimationFrame(loop);
    world?.addEventListener("transitionend", onEnd);
    const fallback = window.setTimeout(() => {
      running = false;
    }, ANIM_FALLBACK_MS);
    return () => {
      running = false;
      cancelAnimationFrame(raf);
      world?.removeEventListener("transitionend", onEnd);
      clearTimeout(fallback);
    };
  }, [measure, tf, nodeOffsets, animate, worldRef]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(measure));
    ro.observe(stage);
    return () => ro.disconnect();
  }, [measure, stageRef]);

  return geo;
}
