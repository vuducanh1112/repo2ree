import { useEffect } from "react";
import type { NodeOffsets, Transform } from "./useCanvasViewport";

// Safety ceiling for the per-frame measure loop: `transitionend` is the real
// stop signal, but a clamped zoom can leave the transform unchanged so no
// transition runs and no event fires — bail out after this either way.
const ANIM_FALLBACK_MS = 800;

interface MeasureLoopOptions {
  /** The element the cables are measured relative to; re-measured when it resizes. */
  stageRef: React.RefObject<HTMLDivElement>;
  /** The pan/zoom layer whose `transform` transition ends the per-frame loop. */
  worldRef: React.RefObject<HTMLDivElement>;
  // `tf` and `nodeOffsets` are re-measure triggers, not inputs: `measure` reads
  // the resulting DOM transform via getScreenCTM rather than these values.
  tf: Transform;
  nodeOffsets: NodeOffsets;
  animate: boolean;
}

/**
 * Runs a cable measurement at the right moments. Both cable hooks need exactly
 * this and used to carry their own copy of it.
 *
 * Re-measures on every transform/offset/data change. While `animate` is on the
 * world layer eases its transform, so it measures each frame until that
 * transition ends — otherwise cables snap to the start frame and only catch up
 * on the next render.
 */
export function useMeasuredCables(
  measure: () => void,
  { stageRef, worldRef, tf, nodeOffsets, animate }: MeasureLoopOptions,
): void {
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
}
