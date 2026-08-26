import {
  clampZoom,
  fitBounds,
  type Transform,
  type WorldBounds,
  zoomToward,
} from "@core/canvas/viewportMath";
import { useEffect, useRef, useState } from "react";

export type { Transform };

type PanState = { pointerId: number; sx: number; sy: number; x0: number; y0: number } | null;

interface CanvasViewport {
  tf: Transform;
  /** Whether button-driven movement should ease instead of tracking the pointer. */
  animate: boolean;
  isPanning: boolean;
  startPan: (event: React.PointerEvent) => void;
  fitView: () => void;
  zoomBy: (factor: number) => void;
}

/** Owns pan and zoom for the assembled 2.5D canvas. */
export function useCanvasViewport(
  stageRef: React.RefObject<HTMLDivElement>,
  worldBounds: WorldBounds,
): CanvasViewport {
  const [tf, setTf] = useState<Transform>({ x: 0, y: 0, z: 1 });
  const [animate, setAnimate] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const pan = useRef<PanState>(null);
  const sizeClass = useRef<"compact" | "regular" | null>(null);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (event: WheelEvent) => {
      if (event.target instanceof Element && event.target.closest("[data-canvas-hud]")) return;
      event.preventDefault();
      const rect = stage.getBoundingClientRect();
      setAnimate(false);
      setTf((previous) =>
        zoomToward(previous, { x: event.clientX, y: event.clientY }, rect, event.deltaY),
      );
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [stageRef]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (!box || box.width <= 0 || box.height <= 0) return;
      const nextClass = box.width <= 760 ? "compact" : "regular";
      if (sizeClass.current === nextClass) return;
      sizeClass.current = nextClass;
      setAnimate(false);
      setTf(fitBounds(box, worldBounds, nextClass === "compact" ? 16 : 32));
    });
    observer.observe(stage);
    return () => observer.disconnect();
  }, [stageRef, worldBounds]);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const activePan = pan.current;
      if (!activePan || event.pointerId !== activePan.pointerId) return;
      setTf((previous) => ({
        ...previous,
        x: activePan.x0 + (event.clientX - activePan.sx),
        y: activePan.y0 + (event.clientY - activePan.sy),
      }));
    };
    const onUp = (event: PointerEvent) => {
      if (!pan.current || event.pointerId !== pan.current.pointerId) return;
      setIsPanning(false);
      pan.current = null;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, []);

  const startPan = (event: React.PointerEvent) => {
    if (!event.isPrimary || event.button !== 0) return;
    if (
      event.target instanceof Element &&
      event.target.closest("[data-canvas-node],[data-canvas-hud]")
    )
      return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
    setAnimate(false);
    setIsPanning(true);
    pan.current = {
      pointerId: event.pointerId,
      sx: event.clientX,
      sy: event.clientY,
      x0: tf.x,
      y0: tf.y,
    };
  };

  const fitView = () => {
    const stage = stageRef.current?.getBoundingClientRect();
    if (!stage || stage.width <= 0 || stage.height <= 0) return;
    setAnimate(true);
    setTf(fitBounds(stage, worldBounds, stage.width <= 760 ? 16 : 32));
  };

  const zoomBy = (factor: number) => {
    setAnimate(true);
    setTf((previous) => ({ ...previous, z: clampZoom(previous.z * factor) }));
  };

  return { tf, animate, isPanning, startPan, fitView, zoomBy };
}
