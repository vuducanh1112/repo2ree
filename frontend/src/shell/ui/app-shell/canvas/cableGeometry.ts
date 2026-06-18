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
  decoCables: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }>;
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
