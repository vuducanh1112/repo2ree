import { LEVELS } from "../../../../../core/review/levels";
import { F } from "../../../../theme/theme";
import { PodBolt } from "./PodBolt";
import { PodBoltRing } from "./PodBoltRing";
import { PodDepGraph } from "./PodDepGraph";
import { type LevelMeta, POD_M } from "./podWidgetData";

interface PodSphereProps {
  CX: number;
  CY: number;
  SR: number;
  level: number;
}

export function PodSphere({ CX, CY, SR, level }: PodSphereProps) {
  const levelMeta = LEVELS[Math.min(level, 7)] as LevelMeta,
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
