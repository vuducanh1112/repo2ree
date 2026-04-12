import type React from "react";
import { LEVELS } from "../../constants/levels";
import { C, F } from "../../constants/theme";

interface LevelMeta {
  color: string;
  bg: string;
  ink: string;
  short: string;
}

const POD_M: Record<string, string> = {
  face: "#e8edf4",
  raised: "#f2f5f9",
  shadow: "#c8d0dc",
  deep: "#a8b4c4",
  bolt: "#cdd5e0",
  boltC: "#9aa5b4",
  weld: "#b8c4d4",
};

interface PodBoltProps {
  cx: number;
  cy: number;
  r?: number;
}
function PodBolt({ cx, cy, r = 5 }: PodBoltProps) {
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
interface PodBoltRingProps {
  cx: number;
  cy: number;
  r: number;
  n?: number;
  bR?: number;
}
function PodBoltRing({ cx, cy, r, n = 8, bR = 4.5 }: PodBoltRingProps) {
  return Array.from({ length: n }).map((_, i) => {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    return <PodBolt key={`bolt-${a}`} cx={cx + r * Math.cos(a)} cy={cy + r * Math.sin(a)} r={bR} />;
  });
}

interface PodGraphNode {
  x: number;
  y: number;
  r: number;
  root?: boolean;
}
interface PodGraph {
  nodes: PodGraphNode[];
  edges: [number, number][];
}
const POD_GRAPHS: (PodGraph | null)[] = [
  null,
  { nodes: [{ x: 0, y: 0, r: 7, root: true }], edges: [] },
  {
    nodes: [
      { x: 0, y: -20, r: 7, root: true },
      { x: -17, y: 13, r: 5 },
      { x: 17, y: 13, r: 5 },
    ],
    edges: [
      [0, 1],
      [0, 2],
    ],
  },
  {
    nodes: [
      { x: 0, y: -24, r: 7, root: true },
      { x: -21, y: 0, r: 5 },
      { x: 21, y: 0, r: 5 },
      { x: -12, y: 21, r: 4 },
      { x: 12, y: 21, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 4],
    ],
  },
  {
    nodes: [
      { x: 0, y: -26, r: 7, root: true },
      { x: -23, y: -7, r: 5 },
      { x: 23, y: -7, r: 5 },
      { x: -26, y: 13, r: 4 },
      { x: 0, y: 19, r: 5 },
      { x: 26, y: 13, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 5],
      [1, 4],
      [2, 4],
    ],
  },
  {
    nodes: [
      { x: 0, y: -28, r: 7, root: true },
      { x: -24, y: -11, r: 5 },
      { x: 24, y: -11, r: 5 },
      { x: -30, y: 7, r: 4 },
      { x: -10, y: 15, r: 4 },
      { x: 10, y: 15, r: 4 },
      { x: 30, y: 7, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 4],
      [5, 6],
    ],
  },
  {
    nodes: [
      { x: 0, y: -30, r: 7, root: true },
      { x: -25, y: -13, r: 5 },
      { x: 25, y: -13, r: 5 },
      { x: -32, y: 4, r: 4 },
      { x: -13, y: 9, r: 4 },
      { x: 13, y: 9, r: 4 },
      { x: 32, y: 4, r: 4 },
      { x: 0, y: 26, r: 5 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 7],
      [6, 7],
      [4, 7],
      [5, 7],
    ],
  },
  {
    nodes: [
      { x: 0, y: -32, r: 7, root: true },
      { x: -26, y: -15, r: 5 },
      { x: 26, y: -15, r: 5 },
      { x: -34, y: 2, r: 4 },
      { x: -14, y: 7, r: 4 },
      { x: 14, y: 7, r: 4 },
      { x: 34, y: 2, r: 4 },
      { x: -21, y: 22, r: 4 },
      { x: 0, y: 28, r: 5 },
      { x: 21, y: 22, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 7],
      [6, 9],
      [4, 8],
      [5, 8],
      [7, 8],
      [8, 9],
      [3, 4],
      [5, 6],
    ],
  },
];

interface PodDepGraphProps {
  level: number;
  levelMeta: LevelMeta;
}
function PodDepGraph({ level, levelMeta }: PodDepGraphProps) {
  if (level === 0)
    return (
      <g opacity="0.3">
        <circle
          cx="0"
          cy="0"
          r="7"
          fill="none"
          stroke={POD_M.shadow}
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />
      </g>
    );
  const cfg = POD_GRAPHS[level];
  if (!cfg) return null;
  return (
    <g>
      {cfg.edges.map(([a, b]) => {
        const na = cfg.nodes[a],
          nb = cfg.nodes[b];
        return (
          <line
            key={`${a}-${b}`}
            x1={na.x}
            y1={na.y}
            x2={nb.x}
            y2={nb.y}
            stroke={levelMeta.color}
            strokeWidth="1.6"
            opacity="0.38"
          />
        );
      })}
      {cfg.nodes.map((graphNode) => (
        <g key={`${graphNode.x}-${graphNode.y}-${graphNode.r}`}>
          <circle
            cx={graphNode.x}
            cy={graphNode.y}
            r={graphNode.r}
            fill={graphNode.root ? levelMeta.color : C.surface}
            stroke={levelMeta.color}
            strokeWidth={graphNode.root ? 0 : 1.8}
          />
          {graphNode.root && (
            <circle
              cx={graphNode.x}
              cy={graphNode.y}
              r={graphNode.r * 0.38}
              fill="#fff"
              opacity="0.75"
            />
          )}
        </g>
      ))}
    </g>
  );
}

interface PodSphereProps {
  CX: number;
  CY: number;
  SR: number;
  level: number;
}
function PodSphere({ CX, CY, SR, level }: PodSphereProps) {
  const levelMeta = LEVELS[Math.min(level, 7)],
    frac = level / 7;
  return (
    <g>
      <defs>
        <radialGradient id="ovPodFace" cx="36%" cy="30%" r="70%">
          <stop offset="0%" stopColor={POD_M.raised} />
          <stop offset="55%" stopColor={POD_M.face} />
          <stop offset="100%" stopColor={POD_M.shadow} />
        </radialGradient>
        <radialGradient id="ovPortholeBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={levelMeta.bg} />
          <stop offset="100%" stopColor={levelMeta.bg} stopOpacity="0.55" />
        </radialGradient>
        <radialGradient id="ovPortholeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={levelMeta.color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={levelMeta.color} stopOpacity="0" />
        </radialGradient>
        <radialGradient id="ovPortholeGloss" cx="32%" cy="28%" r="56%">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <clipPath id="ovPortholeClip">
          <circle cx={CX} cy={CY} r={SR * 0.46} />
        </clipPath>
      </defs>
      <ellipse
        cx={CX + 5}
        cy={CY + SR * 0.85}
        rx={SR * 0.72}
        ry={SR * 0.14}
        fill="#0d1117"
        opacity="0.08"
      />
      <circle cx={CX} cy={CY} r={SR + 1} fill={POD_M.deep} opacity="0.4" />
      <circle cx={CX} cy={CY} r={SR} fill="url(#ovPodFace)" stroke={POD_M.deep} strokeWidth="1.2" />
      <ellipse
        cx={CX}
        cy={CY}
        rx={SR}
        ry={SR * 0.28}
        fill="none"
        stroke={POD_M.weld}
        strokeWidth="0.9"
        opacity="0.7"
      />
      <ellipse
        cx={CX}
        cy={CY}
        rx={SR * 0.28}
        ry={SR}
        fill="none"
        stroke={POD_M.weld}
        strokeWidth="0.9"
        opacity="0.5"
      />
      <ellipse
        cx={CX}
        cy={CY}
        rx={SR}
        ry={SR * 0.18}
        fill={POD_M.shadow}
        stroke={POD_M.deep}
        strokeWidth="1"
        opacity="0.55"
      />
      {Array.from({ length: 10 }).map((_, i) => {
        const a = (i / 10) * Math.PI * 2;
        return Math.abs(Math.cos(a)) < 0.92 ? (
          <PodBolt
            key={`outer-bolt-${a}`}
            cx={CX + (SR - 5) * Math.cos(a)}
            cy={CY + SR * 0.13 * Math.sin(a)}
            r={3.8}
          />
        ) : null;
      })}
      <ellipse
        cx={CX}
        cy={CY - SR * 0.72}
        rx={SR * 0.52}
        ry={SR * 0.22}
        fill={POD_M.face}
        stroke={POD_M.weld}
        strokeWidth="0.8"
        opacity="0.8"
      />
      <PodBoltRing cx={CX} cy={CY - SR * 0.72} r={SR * 0.36} n={6} bR={3.5} />
      <ellipse
        cx={CX}
        cy={CY + SR * 0.72}
        rx={SR * 0.52}
        ry={SR * 0.22}
        fill={POD_M.shadow}
        stroke={POD_M.weld}
        strokeWidth="0.8"
        opacity="0.7"
      />
      <PodBoltRing cx={CX} cy={CY + SR * 0.72} r={SR * 0.36} n={6} bR={3.5} />
      <circle
        cx={CX}
        cy={CY}
        r={SR * 0.58}
        fill={POD_M.shadow}
        stroke={POD_M.deep}
        strokeWidth="1.5"
      />
      <PodBoltRing cx={CX} cy={CY} r={SR * 0.53} n={12} bR={3.8} />
      <circle cx={CX} cy={CY} r={SR * 0.48} fill={POD_M.deep} stroke={POD_M.weld} strokeWidth="2" />
      <circle cx={CX} cy={CY} r={SR * 0.46} fill="#050e1a" stroke={POD_M.deep} strokeWidth="1" />
      <circle cx={CX} cy={CY} r={SR * 0.45} fill="url(#ovPortholeBg)" />
      {level > 0 &&
        (() => {
          const progressRadius = SR * 0.43,
            ang = frac * 2 * Math.PI,
            x2 = CX + progressRadius * Math.sin(ang),
            y2 = CY - progressRadius * Math.cos(ang);
          return (
            <path
              d={`M ${CX} ${CY - progressRadius} A ${progressRadius} ${progressRadius} 0 ${frac > 0.5 ? 1 : 0} 1 ${x2} ${y2}`}
              fill="none"
              stroke={levelMeta.color}
              strokeWidth="3.5"
              opacity="0.5"
              strokeLinecap="round"
            />
          );
        })()}
      <circle cx={CX} cy={CY} r={SR * 0.44} fill="url(#ovPortholeGlow)" />
      <g transform={`translate(${CX},${CY})`} clipPath="url(#ovPortholeClip)">
        <PodDepGraph level={level} levelMeta={levelMeta} />
      </g>
      <circle cx={CX} cy={CY} r={SR * 0.45} fill="url(#ovPortholeGloss)" opacity="0.5" />
      <ellipse
        cx={CX - SR * 0.14}
        cy={CY - SR * 0.18}
        rx={SR * 0.16}
        ry={SR * 0.08}
        fill="white"
        opacity="0.32"
        transform={`rotate(-22,${CX - SR * 0.14},${CY - SR * 0.18})`}
      />
      {[
        { a: -55, col: "#16a34a" },
        { a: 55, col: level >= 4 ? "#0ea5e9" : POD_M.shadow },
        { a: 125, col: level >= 7 ? "#059669" : POD_M.shadow },
        { a: 235, col: POD_M.shadow },
      ].map((indicator) => {
        const px = CX + SR * 0.82 * Math.cos((indicator.a * Math.PI) / 180),
          py = CY + SR * 0.82 * Math.sin((indicator.a * Math.PI) / 180);
        return (
          <g key={indicator.a}>
            <rect
              x={px - 5}
              y={py - 5}
              width="10"
              height="10"
              rx="2"
              fill={POD_M.face}
              stroke={POD_M.deep}
              strokeWidth="0.8"
            />
            <circle cx={px} cy={py} r="3" fill={indicator.col} opacity="0.9" />
          </g>
        );
      })}
      <rect
        x={CX - 36}
        y={CY + SR - 26}
        width="72"
        height="14"
        rx="2"
        fill={POD_M.face}
        stroke={POD_M.weld}
        strokeWidth="0.8"
      />
      <text
        x={CX}
        y={CY + SR - 16}
        textAnchor="middle"
        fontSize="7"
        fontFamily={F.mono}
        fill={levelMeta.ink}
        letterSpacing="1.5"
      >
        {levelMeta.short}
      </text>
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill="none"
        stroke={levelMeta.color}
        strokeWidth="1.5"
        opacity="0.4"
      />
      <path
        d={`M ${CX - SR * 0.68} ${CY - SR * 0.28} A ${SR} ${SR} 0 0 1 ${CX - SR * 0.28} ${CY - SR * 0.68}`}
        fill="none"
        stroke="white"
        strokeWidth="2"
        opacity="0.3"
        strokeLinecap="round"
      />
    </g>
  );
}

interface PodWidgetProps {
  level: number;
  svgRef?: React.RefObject<SVGSVGElement>;
  size?: number;
  compact?: boolean;
}
export function PodWidget({ level, svgRef, size = 480, compact = false }: PodWidgetProps) {
  const levelMeta = LEVELS[Math.min(level, 7)];
  const W = 580,
    H = 580,
    Cx = 290,
    Cy = 290,
    Sr = 118;
  const shadow = compact
    ? `drop-shadow(0 1px 4px ${levelMeta.color}20)`
    : `drop-shadow(0 4px 24px ${levelMeta.color}28) drop-shadow(0 2px 8px ${POD_M.shadow})`;
  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      viewBox={`0 0 ${W} ${H}`}
      style={{
        flexShrink: 0,
        overflow: "visible",
        filter: shadow,
      }}
    >
      <title>Specimen Pod</title>
      <PodSphere CX={Cx} CY={Cy} SR={Sr} level={level} />
    </svg>
  );
}
