import { useCallback, useEffect, useState } from "react";
import type { Cable, CableGeo } from "./cableGeometry";
import type { NodeOffsets, Transform } from "./useCanvasViewport";

// The satellites anchor to the PodWidget core pod, so its sphere geometry must
// match PodWidget's: centre + radius inside its 580-unit viewBox. (Same values
// useCableGeometry uses for the main pod.)
const CORE_CX = 290;
const CORE_CY = 290;
const CORE_R = 118;
// Mirrors the per-frame measure ceiling in the main canvas: transitionend is the
// real stop signal, but a no-op transform fires no event, so bail out anyway.
const ANIM_FALLBACK_MS = 800;

// One satellite's cable identity: what it ties to the core and how the cable
// should read (lit when the experiment is wired up, dim otherwise).
export interface CoreCableTarget {
  key: string;
  connected: boolean;
  color: string;
  shadow: string;
}

interface Options {
  stageRef: React.RefObject<HTMLDivElement>;
  coreSvgRef: React.RefObject<SVGSVGElement>;
  worldRef: React.RefObject<HTMLDivElement>;
  satEls: React.MutableRefObject<Record<string, HTMLElement | null>>;
  targets: CoreCableTarget[];
  // tf/nodeOffsets are re-measure triggers, not inputs: measure reads the live
  // DOM transform via getScreenCTM rather than these values.
  tf: Transform;
  nodeOffsets: NodeOffsets;
  animate: boolean;
}

// Measures a cable from each satellite panel to the core pod's surface in the
// stage's screen space (so the world layer's pan/zoom is absorbed), then hands
// the result to the shared cable overlay. A focused twin of the main canvas's
// useCableGeometry: one pod, a flat ring of satellites, no shells or chain.
export function useExperimentCables({
  stageRef,
  coreSvgRef,
  worldRef,
  satEls,
  targets,
  tf,
  nodeOffsets,
  animate,
}: Options): CableGeo | null {
  const [geo, setGeo] = useState<CableGeo | null>(null);

  const measure = useCallback(() => {
    const stage = stageRef.current;
    const coreSvg = coreSvgRef.current;
    if (!stage || !coreSvg) return;
    const cRect = stage.getBoundingClientRect();

    const ctm = coreSvg.getScreenCTM();
    if (!ctm) return;
    const at = (vx: number, vy: number) => ({
      x: ctm.a * vx + ctm.c * vy + ctm.e - cRect.left,
      y: ctm.b * vx + ctm.d * vy + ctm.f - cRect.top,
    });
    const center = at(CORE_CX, CORE_CY);
    const edge = at(CORE_CX + CORE_R, CORE_CY);
    const radius = Math.hypot(edge.x - center.x, edge.y - center.y);

    // The point on the core surface along the ray toward (x,y).
    const intercept = (x: number, y: number) => {
      const dx = x - center.x;
      const dy = y - center.y;
      const len = Math.hypot(dx, dy) || 1;
      return { x: center.x + (dx / len) * radius, y: center.y + (dy / len) * radius };
    };

    // The point on a panel's border along the ray toward the core: the knob
    // rides the edge that faces the core it's wired to.
    const edgeToward = (
      rect: { left: number; right: number; top: number; bottom: number },
      tx: number,
      ty: number,
    ) => {
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

    const cables: Cable[] = [];
    for (const target of targets) {
      const el = satEls.current[target.key];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const rect = {
        left: r.left - cRect.left,
        right: r.right - cRect.left,
        top: r.top - cRect.top,
        bottom: r.bottom - cRect.top,
      };
      const panel = edgeToward(rect, center.x, center.y);
      const hit = intercept(panel.x, panel.y);
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

    setGeo({ cables, w: cRect.width, h: cRect.height });
  }, [stageRef, coreSvgRef, satEls, targets]);

  // Re-measure on every transform/offset/target change. While `animate` is on
  // the world layer eases its transform, so measure each frame until that
  // transition ends — otherwise cables snap to the start frame.
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
