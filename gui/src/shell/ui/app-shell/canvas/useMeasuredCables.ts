import { useEffect } from "react";
import type { Transform } from "./useCanvasViewport";

const ANIM_FALLBACK_MS = 800;

interface MeasureLoopOptions {
  stageRef: React.RefObject<HTMLDivElement>;
  worldRef: React.RefObject<HTMLDivElement>;
  tf: Transform;
  animate: boolean;
}

export function useMeasuredCables(
  measure: () => void,
  { stageRef, worldRef, tf, animate }: MeasureLoopOptions,
): void {
  // biome-ignore lint/correctness/useExhaustiveDependencies: tf drives re-measurement
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
  }, [measure, tf, animate, worldRef]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(measure));
    ro.observe(stage);
    return () => ro.disconnect();
  }, [measure, stageRef]);
}
