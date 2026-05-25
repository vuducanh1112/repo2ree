import {
  axisFraction,
  axisStandings,
  bottleneckAxis,
  DEPENDENCY_AXIS,
} from "../../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import { F } from "../../../../theme/theme";
import { PodBolt } from "./PodBolt";
import { PodBoltRing } from "./PodBoltRing";
import { PodDepGraph } from "./PodDepGraph";
import { POD_M } from "./podWidgetData";

interface PodSphereProps {
  CX: number;
  CY: number;
  SR: number;
  evaluation: EvaluationState;
}

export function PodSphere({ CX, CY, SR, evaluation }: PodSphereProps) {
  const tint = bottleneckAxis(evaluation).axis;
  const standings = axisStandings(evaluation);
  const depLevel = evaluation.dependencyLevel ?? 0;
  return (
    <g>
      <defs>
        <radialGradient id="ovPodFace" cx="36%" cy="30%" r="70%">
          <stop offset="0%" stopColor={POD_M.raised} />
          <stop offset="55%" stopColor={POD_M.face} />
          <stop offset="100%" stopColor={POD_M.shadow} />
        </radialGradient>
        <radialGradient id="ovPortholeBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={tint.bg} />
          <stop offset="100%" stopColor={tint.bg} stopOpacity="0.55" />
        </radialGradient>
        <radialGradient id="ovPortholeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={tint.color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={tint.color} stopOpacity="0" />
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
      {/* One progress arc per reproducibility axis, concentric. */}
      {standings.map(({ axis, level }, idx) => {
        const frac = axisFraction(axis, level);
        if (frac <= 0) return null;
        const progressRadius = SR * (0.43 - idx * 0.07);
        const ang = frac * 2 * Math.PI;
        const x2 = CX + progressRadius * Math.sin(ang);
        const y2 = CY - progressRadius * Math.cos(ang);
        return (
          <path
            key={axis.key}
            d={`M ${CX} ${CY - progressRadius} A ${progressRadius} ${progressRadius} 0 ${frac > 0.5 ? 1 : 0} 1 ${x2} ${y2}`}
            fill="none"
            stroke={axis.color}
            strokeWidth="3.5"
            opacity="0.85"
            strokeLinecap="round"
          />
        );
      })}
      <circle cx={CX} cy={CY} r={SR * 0.44} fill="url(#ovPortholeGlow)" />
      <g transform={`translate(${CX},${CY})`} clipPath="url(#ovPortholeClip)">
        <PodDepGraph level={depLevel} color={DEPENDENCY_AXIS.color} />
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
      {/* One indicator light per axis: lit in its accent color once the axis is topped out. */}
      {standings.map(({ axis, level }, idx) => {
        const angle = -55 + idx * 90;
        const px = CX + SR * 0.82 * Math.cos((angle * Math.PI) / 180);
        const py = CY + SR * 0.82 * Math.sin((angle * Math.PI) / 180);
        const lit = axisFraction(axis, level) >= 1;
        return (
          <g key={axis.key}>
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
            <circle cx={px} cy={py} r="3" fill={lit ? axis.color : POD_M.shadow} opacity="0.9" />
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
        fill={tint.ink}
        letterSpacing="1.5"
      >
        {tint.short}
      </text>
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill="none"
        stroke={tint.color}
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
