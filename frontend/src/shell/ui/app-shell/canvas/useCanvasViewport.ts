import { useEffect, useRef, useState } from "react";

const ZOOM_MIN = 0.45;
const ZOOM_MAX = 1.7;
// Movement past this many screen px turns a node click into a drag.
const DRAG_THRESHOLD = 4;

export interface Transform {
  x: number;
  y: number;
  z: number;
}

export type NodeOffsets = Record<string, { x: number; y: number }>;

type PanState = { sx: number; sy: number; x0: number; y0: number } | null;
type NodeDragState = {
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
  startPan: (event: React.MouseEvent) => void;
  startNodeDrag: (key: string, sx: number, sy: number) => void;
  resetView: () => void;
  zoomBy: (factor: number) => void;
}

// Owns pan/zoom of the canvas and per-node drag offsets. Pan and node-drag share
// one window-level move/up pump; node-drag deltas are divided by the live zoom so
// a card tracks the cursor 1:1 at any scale.
export function useCanvasViewport(stageRef: React.RefObject<HTMLDivElement>): CanvasViewport {
  const [tf, setTf] = useState<Transform>({ x: 0, y: 0, z: 1 });
  const tfRef = useRef<Transform>({ x: 0, y: 0, z: 1 });
  const [animate, setAnimate] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [nodeOffsets, setNodeOffsets] = useState<NodeOffsets>({});
  const pan = useRef<PanState>(null);
  const nodeDrag = useRef<NodeDragState | null>(null);
  const wasNodeDragged = useRef(false);

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
      setTf((prev) => {
        const ox = event.clientX - rect.left - rect.width / 2 - prev.x;
        const oy = event.clientY - rect.top - rect.height / 2 - prev.y;
        const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
        const z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, prev.z * factor));
        const ratio = z / prev.z - 1;
        return { x: prev.x - ox * ratio, y: prev.y - oy * ratio, z };
      });
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [stageRef]);

  // One shared drag pump: node-drag takes priority over panning when active.
  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const nd = nodeDrag.current;
      if (nd) {
        const dx = event.clientX - nd.sx;
        const dy = event.clientY - nd.sy;
        if (!nd.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD) nd.moved = true;
        if (nd.moved) {
          const z = tfRef.current.z;
          setNodeOffsets((prev) => ({
            ...prev,
            [nd.key]: { x: nd.x0 + dx / z, y: nd.y0 + dy / z },
          }));
        }
        return;
      }
      const p = pan.current;
      if (!p) return;
      setTf((prev) => ({
        ...prev,
        x: p.x0 + (event.clientX - p.sx),
        y: p.y0 + (event.clientY - p.sy),
      }));
    };
    const onUp = () => {
      wasNodeDragged.current = nodeDrag.current?.moved ?? false;
      if (pan.current) setIsPanning(false);
      pan.current = null;
      nodeDrag.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const startNodeDrag = (key: string, sx: number, sy: number) => {
    setAnimate(false);
    const off = nodeOffsets[key] ?? { x: 0, y: 0 };
    nodeDrag.current = { key, sx, sy, x0: off.x, y0: off.y, moved: false };
  };

  const startPan = (event: React.MouseEvent) => {
    if (
      event.target instanceof Element &&
      event.target.closest("[data-canvas-node],[data-canvas-hud]")
    )
      return;
    setAnimate(false);
    setIsPanning(true);
    pan.current = { sx: event.clientX, sy: event.clientY, x0: tf.x, y0: tf.y };
  };

  const resetView = () => {
    setAnimate(true);
    setTf({ x: 0, y: 0, z: 1 });
    setNodeOffsets({});
  };

  const zoomBy = (factor: number) => {
    setAnimate(true);
    setTf((prev) => ({ ...prev, z: Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, prev.z * factor)) }));
  };

  return {
    tf,
    animate,
    nodeOffsets,
    wasNodeDragged,
    isPanning,
    startPan,
    startNodeDrag,
    resetView,
    zoomBy,
  };
}
