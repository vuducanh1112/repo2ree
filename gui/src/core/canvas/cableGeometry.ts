// Cable primitives: the arithmetic that turns measured positions into the
// endpoints and paths a cable overlay draws. Nothing here reads the DOM, and
// nothing here knows what a canvas node is — the hooks measure, `cableScene`
// decides which cables exist, and this file does the geometry for both.

export interface Point {
  x: number;
  y: number;
}

/** A measured element box, in the stage's coordinate space (origin subtracted). */
export interface Rect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** A pod sphere as it appears on screen: centre and radius in stage space. */
export interface PodGeom {
  center: Point;
  radius: number;
}

/**
 * The six numbers of an SVG screen CTM. `DOMMatrix` satisfies this
 * structurally, so `svg.getScreenCTM()` passes straight in with no adapter.
 */
export interface Matrix2D {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
}

// The pod sphere inside PodWidget's 580-unit viewBox (centre + radius). One
// copy: the main canvas pod and the experiment core pod are the same graphic,
// and used to declare these separately under different names.
export const POD_CX = 290;
export const POD_CY = 290;
export const POD_SR = 118;

/**
 * Where a pod's sphere lands on screen, given the SVG's CTM and the stage
 * origin to measure relative to. The radius is derived by transforming a point
 * on the sphere's edge, so it picks up whatever scale the CTM carries.
 */
export function podGeomFromMatrix(ctm: Matrix2D, stageOrigin: Point): PodGeom {
  const at = (vx: number, vy: number): Point => ({
    x: ctm.a * vx + ctm.c * vy + ctm.e - stageOrigin.x,
    y: ctm.b * vx + ctm.d * vy + ctm.f - stageOrigin.y,
  });
  const center = at(POD_CX, POD_CY);
  const edge = at(POD_CX + POD_SR, POD_CY);
  return { center, radius: Math.hypot(edge.x - center.x, edge.y - center.y) };
}

/** The point on a pod's surface along the ray toward (x, y). */
export function intercept(pod: PodGeom, x: number, y: number): Point {
  const dx = x - pod.center.x;
  const dy = y - pod.center.y;
  // A target sitting exactly on the centre gives no ray to follow. The `|| 1`
  // keeps that from dividing by zero; the result is then the centre itself,
  // which is off the surface but finite — a degenerate cable, not a NaN one.
  const len = Math.hypot(dx, dy) || 1;
  return {
    x: pod.center.x + (dx / len) * pod.radius,
    y: pod.center.y + (dy / len) * pod.radius,
  };
}

/**
 * The point on a panel's border along the ray toward (tx, ty): the knob rides
 * the edge that faces whatever the panel is wired to. A degenerate rect, or a
 * target on the panel's own centre, collapses to the centre.
 */
export function edgeToward(rect: Rect, tx: number, ty: number): Point {
  const cx = (rect.left + rect.right) / 2;
  const cy = (rect.top + rect.bottom) / 2;
  const dx = tx - cx;
  const dy = ty - cy;
  const hw = (rect.right - rect.left) / 2;
  const hh = (rect.bottom - rect.top) / 2;
  if ((dx === 0 && dy === 0) || hw === 0 || hh === 0) return { x: cx, y: cy };
  const scale = 1 / Math.max(Math.abs(dx) / hw, Math.abs(dy) / hh);
  return { x: cx + dx * scale, y: cy + dy * scale };
}

/** The centre of a measured box. */
export function rectCenter(rect: Rect): Point {
  return { x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2 };
}

export interface Cable {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  shadow: string;
  connected: boolean;
}

export interface CableGeo {
  cables: Cable[];
  w: number;
  h: number;
}

export function cablePath(x1: number, y1: number, x2: number, y2: number): string {
  const dx = x2 - x1;
  const len = Math.hypot(dx, y2 - y1);
  const droop = len * 0.13;
  const cx1 = x1 + dx * 0.42;
  const cy1 = y1 + droop * 0.6;
  const cx2 = x2 - dx * 0.42;
  const cy2 = y2 + droop * 0.4;
  return `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
}

export function cableHl(x1: number, y1: number, x2: number, y2: number): string {
  const dx = x2 - x1;
  const len = Math.hypot(dx, y2 - y1);
  const droop = len * 0.13;
  const cy1 = y1 + droop * 0.6 - 1.8;
  const cy2 = y2 + droop * 0.4 - 1.8;
  return `M ${x1} ${y1 - 1.4} C ${x1 + dx * 0.42} ${cy1}, ${x2 - dx * 0.42} ${cy2}, ${x2} ${y2 - 1.4}`;
}
