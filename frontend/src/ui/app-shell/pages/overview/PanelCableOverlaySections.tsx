import { type CableGeo, cableHl, cablePath } from "./PanelCableOverlayHelpers";

interface CableOverlaySvgProps {
  geo: CableGeo;
  levelMeta: { bg: string };
}

export function CableOverlaySvg({ geo, levelMeta }: CableOverlaySvgProps) {
  const { cables, decoCables, w, h } = geo;

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        overflow: "visible",
        zIndex: 0,
      }}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
    >
      <title>Panel connections</title>
      <defs>
        {decoCables.map((dc) => (
          <linearGradient
            key={dc.id}
            id={`oDecoFade_${dc.id}`}
            gradientUnits="userSpaceOnUse"
            x1={dc.x1}
            y1={dc.y1}
            x2={dc.x2}
            y2={dc.y2}
          >
            <stop offset="0%" stopColor="white" stopOpacity="1" />
            <stop offset="60%" stopColor="white" stopOpacity="1" />
            <stop offset="85%" stopColor="white" stopOpacity="0.35" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </linearGradient>
        ))}
        {decoCables.map((dc) => (
          <mask key={dc.id} id={`oDecoMask_${dc.id}`}>
            <rect x="0" y="0" width={w} height={h} fill={`url(#oDecoFade_${dc.id})`} />
          </mask>
        ))}
      </defs>
      {decoCables.map((dc) => {
        const d = cablePath(dc.x1, dc.y1, dc.x2, dc.y2);
        const dHl = cableHl(dc.x1, dc.y1, dc.x2, dc.y2);
        return (
          <g key={dc.id} opacity="0.32" mask={`url(#oDecoMask_${dc.id})`}>
            <path
              d={d}
              fill="none"
              stroke="#334155"
              strokeWidth="12"
              opacity="0.12"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke="#94a3b8"
              strokeWidth="8"
              opacity="0.5"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="4"
              opacity="0.75"
              strokeLinecap="round"
            />
            <path
              d={dHl}
              fill="none"
              stroke="#ffffff"
              strokeWidth="1.5"
              opacity="0.55"
              strokeLinecap="round"
            />
          </g>
        );
      })}
      {cables.map((c) => {
        const color = c.connected ? c.color : "#94a3b8";
        const shadow = c.connected ? c.shadow : "#334155";
        const inner = c.connected ? levelMeta.bg : "#e2e8f0";
        const d = cablePath(c.x1, c.y1, c.x2, c.y2);
        const dHl = cableHl(c.x1, c.y1, c.x2, c.y2);
        return (
          <g key={c.id} opacity={c.connected ? 1 : 0.38}>
            <path
              d={d}
              fill="none"
              stroke={shadow}
              strokeWidth="14"
              opacity="0.16"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke={color}
              strokeWidth="9"
              opacity="0.55"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke={inner}
              strokeWidth="5"
              opacity="0.80"
              strokeLinecap="round"
            />
            <path
              d={dHl}
              fill="none"
              stroke="#ffffff"
              strokeWidth="1.8"
              opacity="0.60"
              strokeLinecap="round"
            />
            <circle cx={c.x1} cy={c.y1} r="5.5" fill={color} stroke={shadow} strokeWidth="1.3" />
            <circle cx={c.x1} cy={c.y1} r="2.4" fill="#fff" opacity="0.85" />
            <circle cx={c.x2} cy={c.y2} r="5.5" fill={color} stroke={shadow} strokeWidth="1.3" />
            <circle cx={c.x2} cy={c.y2} r="2.4" fill="#fff" opacity="0.85" />
          </g>
        );
      })}
    </svg>
  );
}
