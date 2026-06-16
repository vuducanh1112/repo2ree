import { useCallback, useEffect, useState } from "react";
import type { Badges } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { CableGeo } from "../pages/overview/PanelCableOverlayHelpers";
import { PAGE } from "../state/pages";
import { CANVAS_NODES, isNodeDone } from "./canvasNodes";
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
}: CableGeometryOptions): CableGeo | null {
  const [geo, setGeo] = useState<CableGeo | null>(null);

  const measure = useCallback(() => {
    const stage = stageRef.current;
    const podSvg = podSvgRef.current;
    if (!stage || !podSvg) return;
    const ctm = podSvg.getScreenCTM();
    if (!ctm) return;
    const cRect = stage.getBoundingClientRect();
    const toStage = (px: number, py: number) => ({
      x: ctm.a * px + ctm.c * py + ctm.e - cRect.left,
      y: ctm.b * px + ctm.d * py + ctm.f - cRect.top,
    });
    const center = toStage(POD_CX, POD_CY);
    const edge = toStage(POD_CX + POD_SR, POD_CY);
    const radius = Math.hypot(edge.x - center.x, edge.y - center.y);
    const intercept = (x: number, y: number) => {
      const dx = x - center.x;
      const dy = y - center.y;
      const len = Math.hypot(dx, dy) || 1;
      return { x: center.x + (dx / len) * radius, y: center.y + (dy / len) * radius };
    };

    const cables = CANVAS_NODES.flatMap((node) => {
      if (node.key === PAGE.FILES) return [];
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
      const pod = intercept(px, py);
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
    setGeo({ cables, decoCables: [], w: cRect.width, h: cRect.height });
  }, [stageRef, podSvgRef, nodeEls, ree, badges]);

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
