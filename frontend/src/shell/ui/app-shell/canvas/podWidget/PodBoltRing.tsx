import { PodBolt } from "./PodBolt";

interface PodBoltRingProps {
  cx: number;
  cy: number;
  r: number;
  n?: number;
  bR?: number;
}

export function PodBoltRing({ cx, cy, r, n = 8, bR = 4.5 }: PodBoltRingProps) {
  return Array.from({ length: n }).map((_, i) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    return <PodBolt key={`bolt-${a}`} cx={cx + r * Math.cos(a)} cy={cy + r * Math.sin(a)} r={bR} />;
  });
}
