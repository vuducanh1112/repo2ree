import { axisFraction, axisStandings, bottleneckAxis } from "../../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../../core/review/EvaluationState";
import { F } from "../../../../theme/theme";
import { PodBolt } from "./PodBolt";
import { PodBoltRing } from "./PodBoltRing";
import { PodShellCore } from "./PodShellCore";
import { PodShellInner } from "./PodShellInner";
import { POD_M } from "./podWidgetData";

export type PodShell = "full" | "outer" | "inner" | "core";

interface PodSphereProps {
  CX: number;
  CY: number;
  SR: number;
  evaluation: EvaluationState;
  shell?: PodShell;
  /** Unique suffix for SVG IDs when multiple pods are on the same page. */
  idSuffix?: string;
}

export function PodSphere({
  CX,
  CY,
  SR,
  evaluation,
  shell = "full",
  idSuffix = "",
}: PodSphereProps) {
  // Standalone inner or core: skip the outer mechanics entirely.
  if (shell === "core") {
    return (
      <PodShellCore CX={CX} CY={CY} SR={SR} evaluation={evaluation} idSuffix={`s${idSuffix}`} />
    );
  }
  if (shell === "inner") {
    return (
      <PodShellInner CX={CX} CY={CY} SR={SR} evaluation={evaluation} idSuffix={`s${idSuffix}`} />
    );
  }

  const tint = bottleneckAxis(evaluation).axis;
  const standings = axisStandings(evaluation);

  // Porthole radius — the "window" through the outer shell into the interior.
  const PR = SR * 0.46;

  const oId = `ov${idSuffix}`;

  return (
    <g>
      <defs>
        <radialGradient id={`${oId}PodFace`} cx="36%" cy="30%" r="70%">
          <stop offset="0%" stopColor={POD_M.raised} />
          <stop offset="55%" stopColor={POD_M.face} />
          <stop offset="100%" stopColor={POD_M.shadow} />
        </radialGradient>
        <radialGradient id={`${oId}PortholeGloss`} cx="32%" cy="28%" r="56%">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <clipPath id={`${oId}PortholeClip`}>
          <circle cx={CX} cy={CY} r={PR} />
        </clipPath>
      </defs>

      {/* ── drop shadow ── */}
      <ellipse
        cx={CX + 5}
        cy={CY + SR * 0.85}
        rx={SR * 0.72}
        ry={SR * 0.14}
        fill="#0d1117"
        opacity="0.08"
      />

      {/* ── outer shell body ── */}
      <circle cx={CX} cy={CY} r={SR + 1} fill={POD_M.deep} opacity="0.4" />
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill={`url(#${oId}PodFace)`}
        stroke={POD_M.deep}
        strokeWidth="1.2"
      />

      {/* weld seam lines */}
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

      {/* equatorial belt */}
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

      {/* ── top and bottom pole panels ── */}
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

      {/* ── porthole collar ── */}
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

      {/* ── porthole interior ── */}
      {shell === "full" ? (
        <g clipPath={`url(#${oId}PortholeClip)`}>
          <PodShellInner
            CX={CX}
            CY={CY}
            SR={PR}
            evaluation={evaluation}
            showCore
            idSuffix={`p${idSuffix}`}
          />
        </g>
      ) : (
        /* shell === "outer": sealed porthole, no interior visible */
        <circle cx={CX} cy={CY} r={PR} fill={POD_M.deep} stroke={POD_M.weld} strokeWidth="1" />
      )}

      {/* porthole gloss overlay */}
      <circle cx={CX} cy={CY} r={PR} fill={`url(#${oId}PortholeGloss)`} opacity="0.5" />

      {/* ── outer sphere gloss highlight ── */}
      <ellipse
        cx={CX - SR * 0.14}
        cy={CY - SR * 0.18}
        rx={SR * 0.16}
        ry={SR * 0.08}
        fill="white"
        opacity="0.32"
        transform={`rotate(-22,${CX - SR * 0.14},${CY - SR * 0.18})`}
      />

      {/* ── indicator lights ── one per axis, lit when topped out ── */}
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

      {/* ── model label plate ── */}
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

      {/* ── tint accent ring ── */}
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill="none"
        stroke={tint.color}
        strokeWidth="1.5"
        opacity="0.4"
      />

      {/* outer gloss arc */}
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
