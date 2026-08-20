import {
  clampZoom,
  dragOffset,
  exceedsDragThreshold,
  fitBounds,
  type NodeOffsets,
  type Transform,
  type WorldBounds,
  zoomToward,
} from "@core/canvas/viewportMath";
import { useEffect, useRef, useState } from "react";

// The transform types live with the math that produces them; this module stays
// their public home, since the canvas imports them from the hook it drives.
export type { NodeOffsets, Transform };

type PanState = { pointerId: number; sx: number; sy: number; x0: number; y0: number } | null;
type NodeDragState = {
  pointerId: number;
  key: string;
  sx: number;
  sy: number;
  x0: number;
  y0: number;
  moved: boolean;
};

interface CanvasViewport {
  tf: Transform;
  /** Whether the world layer should ease its transform (button-driven moves) vs. track 1:1 (drag/wheel). */
  animate: boolean;
  nodeOffsets: NodeOffsets;
  /** True right after a drag that actually moved a node — read to suppress the trailing click. */
  wasNodeDragged: React.RefObject<boolean>;
  /** True while a pan is in progress — drives the grab/grabbing cursor. */
  isPanning: boolean;
  startPan: (event: React.PointerEvent) => void;
  startNodeDrag: (key: string, event: React.PointerEvent) => void;
  fitView: () => void;
  zoomBy: (factor: number) => void;
  /** Eased move to an absolute transform (used to frame the exploded view). */
  focusView: (next: Partial<Transform>) => void;
}

// Owns pan/zoom of the canvas and per-node drag offsets. Pan and node-drag share
// one window-level move/up pump; node-drag deltas are divided by the live zoom so
// a card tracks the cursor 1:1 at any scale.
export function useCanvasViewport(
  stageRef: React.RefObject<HTMLDivElement>,
  worldBounds: WorldBounds,
): CanvasViewport {
  const [tf, setTf] = useState<Transform>({ x: 0, y: 0, z: 1 });
  const tfRef = useRef<Transform>({ x: 0, y: 0, z: 1 });
  const [animate, setAnimate] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [nodeOffsets, setNodeOffsets] = useState<NodeOffsets>({});
  const pan = useRef<PanState>(null);
  const nodeDrag = useRef<NodeDragState | null>(null);
  const wasNodeDragged = useRef(false);
  const sizeClass = useRef<"compact" | "regular" | null>(null);

  // Mirror tf so the move handler reads current zoom without re-subscribing the
  // global listeners on every zoom change.
  useEffect(() => {
    tfRef.current = tf;
  });

  // Wheel-to-zoom toward the cursor. Native listener so preventDefault works.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (event: WheelEvent) => {
      // Let HUD overlays (file console, bench console, file viewer) scroll their
      // own content instead of zooming/panning the canvas underneath.
      if (event.target instanceof Element && event.target.closest("[data-canvas-hud]")) return;
      event.preventDefault();
      const rect = stage.getBoundingClientRect();
      setAnimate(false);
      setTf((prev) => zoomToward(prev, { x: event.clientX, y: event.clientY }, rect, event.deltaY));
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [stageRef]);

  // Frame the full constellation on first layout and when crossing the compact
  // breakpoint. Ordinary resizes preserve the camera the user chose.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (!box || box.width <= 0 || box.height <= 0) return;
      const nextClass = box.width <= 760 ? "compact" : "regular";
      if (sizeClass.current === nextClass) return;
      sizeClass.current = nextClass;
      const next = fitBounds(box, worldBounds, nextClass === "compact" ? 16 : 32);
      tfRef.current = next;
      setAnimate(false);
      setTf(next);
    });
    observer.observe(stage);
    return () => observer.disconnect();
  }, [stageRef, worldBounds]);

  // One shared drag pump: node-drag takes priority over panning when active.
  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const nd = nodeDrag.current;
      if (nd) {
        if (event.pointerId !== nd.pointerId) return;
        const dx = event.clientX - nd.sx;
        const dy = event.clientY - nd.sy;
        if (!nd.moved && exceedsDragThreshold(dx, dy)) nd.moved = true;
        if (nd.moved) {
          const z = tfRef.current.z;
          setNodeOffsets((prev) => ({
            ...prev,
            [nd.key]: dragOffset({ x: nd.x0, y: nd.y0 }, dx, dy, z),
          }));
        }
        return;
      }
      const p = pan.current;
      if (!p) return;
      if (event.pointerId !== p.pointerId) return;
      setTf((prev) => ({
        ...prev,
        x: p.x0 + (event.clientX - p.sx),
        y: p.y0 + (event.clientY - p.sy),
      }));
    };
    const onUp = (event: PointerEvent) => {
      const pointerId = nodeDrag.current?.pointerId ?? pan.current?.pointerId;
      if (pointerId != null && event.pointerId !== pointerId) return;
      wasNodeDragged.current = nodeDrag.current?.moved ?? false;
      if (pan.current) setIsPanning(false);
      pan.current = null;
      nodeDrag.current = null;
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

  const startNodeDrag = (key: string, event: React.PointerEvent) => {
    if (!event.isPrimary || event.button !== 0) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setAnimate(false);
    wasNodeDragged.current = false;
    const off = nodeOffsets[key] ?? { x: 0, y: 0 };
    nodeDrag.current = {
      pointerId: event.pointerId,
      key,
      sx: event.clientX,
      sy: event.clientY,
      x0: off.x,
      y0: off.y,
      moved: false,
    };
  };

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
    const next = fitBounds(stage, worldBounds, stage.width <= 760 ? 16 : 32);
    setAnimate(true);
    setTf(next);
    setNodeOffsets({});
  };

  const zoomBy = (factor: number) => {
    setAnimate(true);
    setTf((prev) => ({ ...prev, z: clampZoom(prev.z * factor) }));
  };

  const focusView = (next: Partial<Transform>) => {
    setAnimate(true);
    setTf((prev) => ({
      ...prev,
      ...next,
      z: next.z != null ? clampZoom(next.z) : prev.z,
    }));
  };

  return {
    tf,
    animate,
    nodeOffsets,
    wasNodeDragged,
    isPanning,
    startPan,
    startNodeDrag,
    fitView,
    zoomBy,
    focusView,
  };
}
