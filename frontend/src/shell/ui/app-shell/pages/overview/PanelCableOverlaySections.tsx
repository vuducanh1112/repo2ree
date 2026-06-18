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
      {decoCables.map((dc) => {
        const d = cablePath(dc.x1, dc.y1, dc.x2, dc.y2);
        const dHl = cableHl(dc.x1, dc.y1, dc.x2, dc.y2);
        return (
          <g key={dc.id} opacity="0.5">
            <path
              d={d}
              fill="none"
              stroke="#334155"
              strokeWidth="12"
              opacity="0.14"
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
            <circle
              cx={dc.x1}
              cy={dc.y1}
              r="5.5"
              fill="#94a3b8"
              stroke="#334155"
              strokeWidth="1.3"
            />
            <circle cx={dc.x1} cy={dc.y1} r="2.4" fill="#fff" opacity="0.85" />
            <circle
              cx={dc.x2}
              cy={dc.y2}
              r="5.5"
              fill="#94a3b8"
              stroke="#334155"
              strokeWidth="1.3"
            />
            <circle cx={dc.x2} cy={dc.y2} r="2.4" fill="#fff" opacity="0.85" />
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
