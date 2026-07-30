import type { Point } from "./cableGeometry";

/** Pan (x, y) and zoom (z) of the world layer. */
export interface Transform {
  x: number;
  y: number;
  z: number;
}

export type NodeOffsets = Record<string, { x: number; y: number }>;

export const ZOOM_MIN = 0.38;
export const ZOOM_MAX = 1.7;
// Movement past this many screen px turns a node click into a drag. Private:
// callers ask `exceedsDragThreshold` rather than comparing against it.
const DRAG_THRESHOLD = 4;
// One wheel notch. Zooming out is the exact inverse, so a notch each way
// returns to where it started.
const WHEEL_ZOOM_STEP = 1.1;

/** The stage box a pointer position is interpreted against. `DOMRect` satisfies this. */
export interface StageBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function clampZoom(z: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
}

/**
 * Zoom one wheel notch about the pointer, keeping whatever is under the cursor
 * under the cursor. `offset` is the pointer's position relative to the world's
 * current centre; scaling by `z/prev.z - 1` moves the world by exactly the
 * amount the zoom would otherwise have shifted that point.
 *
 * At a zoom limit the clamp makes the ratio 0, so a further notch is a no-op
 * rather than a pan — which is also why the measure loop needs its own timeout:
 * a no-op transform fires no `transitionend`.
 */
export function zoomToward(
  prev: Transform,
  pointer: Point,
  stage: StageBox,
  deltaY: number,
): Transform {
  const ox = pointer.x - stage.left - stage.width / 2 - prev.x;
  const oy = pointer.y - stage.top - stage.height / 2 - prev.y;
  const factor = deltaY < 0 ? WHEEL_ZOOM_STEP : 1 / WHEEL_ZOOM_STEP;
  const z = clampZoom(prev.z * factor);
  const ratio = z / prev.z - 1;
  return { x: prev.x - ox * ratio, y: prev.y - oy * ratio, z };
}

/** Whether a pointer has moved far enough that a node press counts as a drag. */
export function exceedsDragThreshold(dx: number, dy: number): boolean {
  return Math.hypot(dx, dy) > DRAG_THRESHOLD;
}

/**
 * A dragged node's new offset. Screen deltas are divided by the live zoom so a
 * card tracks the cursor 1:1 at any scale.
 */
export function dragOffset(origin: Point, dx: number, dy: number, zoom: number): Point {
  return { x: origin.x + dx / zoom, y: origin.y + dy / zoom };
}
