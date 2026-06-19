import { type CableGeo, cableHl, cablePath } from "./cableGeometry";

interface CableOverlaySvgProps {
  geo: CableGeo;
  levelMeta: { bg: string };
}

interface CableStrandProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  outerColor: string;
  outerWidth: number;
  outerOpacity: number;
  midColor: string;
  midWidth: number;
  midOpacity: number;
  innerColor: string;
  innerWidth: number;
  innerOpacity: number;
  knobFill: string;
  knobStroke: string;
}

function CableStrand({
  x1,
  y1,
  x2,
  y2,
  outerColor,
  outerWidth,
  outerOpacity,
  midColor,
  midWidth,
  midOpacity,
  innerColor,
  innerWidth,
  innerOpacity,
  knobFill,
  knobStroke,
}: CableStrandProps) {
  const d = cablePath(x1, y1, x2, y2);
  const dHl = cableHl(x1, y1, x2, y2);
  return (
    <>
      <path
        d={d}
        fill="none"
        stroke={outerColor}
        strokeWidth={outerWidth}
        opacity={outerOpacity}
        strokeLinecap="round"
      />
      <path
        d={d}
        fill="none"
        stroke={midColor}
        strokeWidth={midWidth}
        opacity={midOpacity}
        strokeLinecap="round"
      />
      <path
        d={d}
        fill="none"
        stroke={innerColor}
        strokeWidth={innerWidth}
        opacity={innerOpacity}
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
      <circle cx={x1} cy={y1} r="5.5" fill={knobFill} stroke={knobStroke} strokeWidth="1.3" />
      <circle cx={x1} cy={y1} r="2.4" fill="#fff" opacity="0.85" />
      <circle cx={x2} cy={y2} r="5.5" fill={knobFill} stroke={knobStroke} strokeWidth="1.3" />
      <circle cx={x2} cy={y2} r="2.4" fill="#fff" opacity="0.85" />
    </>
  );
}

export function CableOverlaySvg({ geo, levelMeta }: CableOverlaySvgProps) {
  const { cables, w, h } = geo;

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
      {cables.map((c) => {
        const color = c.connected ? c.color : "#94a3b8";
        const shadow = c.connected ? c.shadow : "#334155";
        const inner = c.connected ? levelMeta.bg : "#e2e8f0";
        return (
          <g key={c.id} opacity={c.connected ? 1 : 0.38}>
            <CableStrand
              x1={c.x1}
              y1={c.y1}
              x2={c.x2}
              y2={c.y2}
              outerColor={shadow}
              outerWidth={14}
              outerOpacity={0.16}
              midColor={color}
              midWidth={9}
              midOpacity={0.55}
              innerColor={inner}
              innerWidth={5}
              innerOpacity={0.8}
              knobFill={color}
              knobStroke={shadow}
            />
          </g>
        );
      })}
    </svg>
  );
}
