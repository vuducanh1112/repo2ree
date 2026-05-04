import { POD_M } from "./podWidgetData";

interface PodBoltProps {
  cx: number;
  cy: number;
  r?: number;
}

export function PodBolt({ cx, cy, r = 5 }: PodBoltProps) {
  const pts = Array.from({ length: 6 })
    .map((_, i) => {
      const a = (i / 6) * Math.PI * 2 - Math.PI / 6;
      return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
    })
    .join(" ");
  return (
    <g>
      <polygon points={pts} fill={POD_M.bolt} stroke={POD_M.deep} strokeWidth="0.7" />
      <circle cx={cx} cy={cy} r={r * 0.38} fill={POD_M.boltC} />
      <polygon
        points={pts}
        fill="none"
        stroke={POD_M.raised}
        strokeWidth="0.4"
        opacity="0.8"
        transform="translate(-0.4,-0.4)"
      />
    </g>
  );
}
