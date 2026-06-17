import { useCallback, useEffect, useState } from "react";
import type { Badges } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { CableGeo } from "../pages/overview/PanelCableOverlayHelpers";
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
    const intercept = (
      pod: { center: { x: number; y: number }; radius: number },
      x: number,
      y: number,
    ) => {
      const dx = x - pod.center.x;
      const dy = y - pod.center.y;
      const len = Math.hypot(dx, dy) || 1;
      return {
        x: pod.center.x + (dx / len) * pod.radius,
        y: pod.center.y + (dy / len) * pod.radius,
      };
    };

    const cables = CANVAS_NODES.flatMap((node) => {
      const el = nodeEls.current[node.key];
      if (!el) return [];
      const r = el.getBoundingClientRect();
      const left = r.left - cRect.left;
      const right = r.right - cRect.left;
      const top = r.top - cRect.top;
      const bottom = r.bottom - cRect.top;
      let px = (left + right) / 2;
      let py = (top + bottom) / 2;
      if (node.x <= -60) px = right;
      else if (node.x >= 60) px = left;
      else if (node.y < 0) py = bottom;
      else py = top;
      const pod = intercept(podForZone(node.zone), px, py);
      return [
        {
          id: node.key,
          x1: px,
          y1: py,
          x2: pod.x,
          y2: pod.y,
          color: node.color,
          shadow: node.shadow,
          connected: isNodeDone(node, ree, badges),
        },
      ];
    });

    // Cross-shell dependency spine, drawn only when decomposed: source feeds the
    // runtime feeds the experiment, i.e. outer shell → inner shell → core. We
    // connect the column pods edge-to-edge so it reads as a faded backbone behind
    // the membership cables. (In the assembled view the shells overlap into one
    // pod, so there is nothing to span.)
    const decoCables: CableGeo["decoCables"] = [];
    if (exploded) {
      const innerPod = podGeom(projectionPods.inner?.current ?? null);
      const corePod = podGeom(projectionPods.core?.current ?? null);
      const spine = (
        id: string,
        from: { center: { x: number; y: number }; radius: number } | null,
        to: { center: { x: number; y: number }; radius: number } | null,
      ) => {
        if (!from || !to) return;
        const a = intercept(from, to.center.x, to.center.y);
        const b = intercept(to, from.center.x, from.center.y);
        decoCables.push({ id, x1: a.x, y1: a.y, x2: b.x, y2: b.y });
      };
      spine("spine-outer-inner", mainPod, innerPod);
      spine("spine-inner-core", innerPod, corePod);
    }

    setGeo({ cables, decoCables, w: cRect.width, h: cRect.height });
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
