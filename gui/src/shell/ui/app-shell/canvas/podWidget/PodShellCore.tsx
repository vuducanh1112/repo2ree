import { DEPENDENCY_AXIS } from "@core/evaluate/axes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import { axisTone } from "../../../theme/appearance";
import { PodDepGraph } from "./PodDepGraph";

interface PodShellCoreProps {
  CX: number;
  CY: number;
  SR: number;
  evaluation: EvaluationState;
  /** Unique suffix for SVG IDs when multiple pods are on the same page. */
  idSuffix?: string;
}

export function PodShellCore({ CX, CY, SR, evaluation, idSuffix = "" }: PodShellCoreProps) {
  const depLevel = Math.max(evaluation.dependencyLevel ?? 0, 2);
  const color = axisTone(DEPENDENCY_AXIS.key);
  // PodDepGraph largest node extent ≈ 50px from center at level 7
  const graphScale = SR / 50;

  const gId = `core${idSuffix}`;

  return (
    <g>
      <defs>
        <radialGradient id={`${gId}Bg`} cx="45%" cy="38%" r="66%">
          <stop offset="0%" stopColor="#1a0838" />
          <stop offset="55%" stopColor="#08071a" />
          <stop offset="100%" stopColor="#030612" />
        </radialGradient>
        <radialGradient id={`${gId}Glow`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={color} stopOpacity="0.65" />
          <stop offset="55%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </radialGradient>
        <filter id={`${gId}Blur`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={Math.max(SR * 0.1, 2)} />
        </filter>
        <clipPath id={`${gId}Clip`}>
          <circle cx={CX} cy={CY} r={SR} />
        </clipPath>
      </defs>

      {/* ambient halo */}
      <circle cx={CX} cy={CY} r={SR * 1.08} fill={color} opacity="0.06" />

      {/* deep dark sphere */}
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill={`url(#${gId}Bg)`}
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity="0.4"
      />

      {/* nebula bloom */}
      <circle cx={CX} cy={CY} r={SR * 0.72} fill={`url(#${gId}Glow)`} filter={`url(#${gId}Blur)`} />

      {/* neural graph scaled to fill the core */}
      <g clipPath={`url(#${gId}Clip)`}>
        <g transform={`translate(${CX},${CY}) scale(${graphScale})`}>
          <PodDepGraph level={depLevel} color={color} />
        </g>
      </g>

      {/* rim ring */}
      <circle cx={CX} cy={CY} r={SR} fill="none" stroke={color} strokeWidth="1.5" opacity="0.35" />

      {/* central spark */}
      <circle cx={CX} cy={CY} r={Math.max(SR * 0.07, 3)} fill="white" opacity="0.9" />
      <circle
        cx={CX}
        cy={CY}
        r={Math.max(SR * 0.16, 6)}
        fill={color}
        opacity="0.3"
        filter={`url(#${gId}Blur)`}
      />
    </g>
  );
}
