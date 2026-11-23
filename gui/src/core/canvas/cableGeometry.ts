import type { AppShellPage } from "@core/app-shell/pages";

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export interface PodGeom {
  center: Point;
  radius: number;
}

export interface Matrix2D {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
}

export const POD_CX = 290;
export const POD_CY = 290;
export const POD_SR = 118;

export function podGeomFromMatrix(ctm: Matrix2D, stageOrigin: Point): PodGeom {
  const at = (vx: number, vy: number): Point => ({
    x: ctm.a * vx + ctm.c * vy + ctm.e - stageOrigin.x,
    y: ctm.b * vx + ctm.d * vy + ctm.f - stageOrigin.y,
  });
  const center = at(POD_CX, POD_CY);
  const edge = at(POD_CX + POD_SR, POD_CY);
  return { center, radius: Math.hypot(edge.x - center.x, edge.y - center.y) };
}

export function intercept(pod: PodGeom, x: number, y: number): Point {
  const dx = x - pod.center.x;
  const dy = y - pod.center.y;
  const len = Math.hypot(dx, dy) || 1;
  return {
    x: pod.center.x + (dx / len) * pod.radius,
    y: pod.center.y + (dy / len) * pod.radius,
  };
}

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

export function rectCenter(rect: Rect): Point {
  return { x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2 };
}

export interface Cable {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  stageKey: AppShellPage;
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
