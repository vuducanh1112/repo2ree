import { axisFraction, axisStandings } from "@core/evaluate/axes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import { axisTone } from "../../../theme/appearance";
import styles from "../PodWidget.module.css";
import { PodShellCore } from "./PodShellCore";

interface PodShellInnerProps {
  CX: number;
  CY: number;
  SR: number;
  evaluation: EvaluationState;
  /** When true (standalone view), renders the core nested inside. */
  showCore?: boolean;
  /** Work is running on the inner shell — the runtime is being assembled. */
  active?: boolean;
  /** Work is running in the core, when the core is shown here. */
  coreActive?: boolean;
  idSuffix?: string;
}

export function PodShellInner({
  CX,
  CY,
  SR,
  evaluation,
  showCore = false,
  active = false,
  coreActive = false,
  idSuffix = "",
}: PodShellInnerProps) {
  const standings = axisStandings(evaluation);
  const iId = `inner${idSuffix}`;

  return (
    <g>
      <defs>
        <radialGradient id={`${iId}Grad`} cx="38%" cy="30%" r="68%">
          <stop offset="0%" stopColor="var(--pod-glow-near)" stopOpacity="0.9" />
          <stop offset="25%" stopColor="var(--pod-glow-mid)" stopOpacity="0.75" />
          <stop offset="62%" stopColor="var(--pod-glow-far)" stopOpacity="0.84" />
          <stop offset="100%" stopColor="var(--pod-glow-deep)" stopOpacity="0.94" />
        </radialGradient>
        <radialGradient id={`${iId}CenterGlow`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--pod-rim)" stopOpacity="0.5" />
          <stop offset="100%" stopColor="var(--ink-accent)" stopOpacity="0" />
        </radialGradient>
        <filter id={`${iId}Blur`} x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation={Math.max(SR * 0.09, 2)} />
        </filter>
      </defs>

      {/* outer ambient glow — breathes while the shell is working */}
      <g className={active ? styles.breathe : undefined}>
        <circle
          cx={CX}
          cy={CY}
          r={SR * 1.1}
          fill="var(--pod-glow-mid)"
          opacity="0.07"
          filter={`url(#${iId}Blur)`}
        />
      </g>

      {/* the glass sphere body */}
      <circle
        cx={CX}
        cy={CY}
        r={SR}
        fill={`url(#${iId}Grad)`}
        stroke="var(--pod-rim)"
        strokeWidth="1.5"
        strokeOpacity="0.55"
      />

      {/* inner bloom */}
      <g className={active ? styles.breathe : undefined}>
        <circle
          cx={CX}
          cy={CY}
          r={SR * 0.68}
          fill={`url(#${iId}CenterGlow)`}
          filter={`url(#${iId}Blur)`}
        />
      </g>

      {/* orbital rings — they turn, counter to each other, while work runs */}
      <ellipse
        className={active ? styles.orbitForward : undefined}
        cx={CX}
        cy={CY}
        rx={SR}
        ry={SR * 0.22}
        fill="none"
        stroke="var(--pod-glow-mid)"
        strokeWidth="0.9"
        opacity="0.35"
      />
      <ellipse
        className={active ? styles.orbitReverse : undefined}
        cx={CX}
        cy={CY}
        rx={SR * 0.22}
        ry={SR}
        fill="none"
        stroke="var(--pod-rim)"
        strokeWidth="0.6"
        opacity="0.22"
      />

      {/* progress arcs orbiting the sphere surface */}
      {standings.map(({ axis, level }, idx) => {
        const frac = axisFraction(axis, level);
        if (frac <= 0) return null;
        const r = SR * (0.9 - idx * 0.08);
        if (frac >= 1) {
          return (
            <circle
              key={axis.key}
              cx={CX}
              cy={CY}
              r={r}
              fill="none"
              stroke={axisTone(axis.key)}
              strokeWidth="2.5"
              opacity="0.72"
            />
          );
        }
        const ang = frac * 2 * Math.PI;
        const x2 = CX + r * Math.sin(ang);
        const y2 = CY - r * Math.cos(ang);
        return (
          <path
            key={axis.key}
            d={`M ${CX} ${CY - r} A ${r} ${r} 0 ${frac > 0.5 ? 1 : 0} 1 ${x2} ${y2}`}
            fill="none"
            stroke={axisTone(axis.key)}
            strokeWidth="2.5"
            opacity="0.72"
            strokeLinecap="round"
          />
        );
      })}

      {/* the sweep: a bright arc running the sphere's rim while work is in
       * flight. It is the one cue that still reads at porthole size. */}
      {active && (
        <circle
          className={styles.sweep}
          cx={CX}
          cy={CY}
          r={SR * 0.94}
          fill="none"
          stroke="var(--pod-rim)"
          strokeWidth={Math.max(SR * 0.05, 1.5)}
          strokeLinecap="round"
          pathLength={100}
        />
      )}

      {/* core visible inside the sphere */}
      {showCore && (
        <PodShellCore
          CX={CX}
          CY={CY}
          SR={SR * 0.56}
          evaluation={evaluation}
          active={coreActive}
          idSuffix={`${iId}c`}
        />
      )}

      {/* glass sheen highlights */}
      <ellipse
        cx={CX - SR * 0.17}
        cy={CY - SR * 0.23}
        rx={SR * 0.28}
        ry={SR * 0.12}
        fill="white"
        opacity="0.38"
        transform={`rotate(-26,${CX - SR * 0.17},${CY - SR * 0.23})`}
      />
      <ellipse
        cx={CX - SR * 0.04}
        cy={CY - SR * 0.56}
        rx={SR * 0.11}
        ry={SR * 0.045}
        fill="white"
        opacity="0.52"
        transform={`rotate(-10,${CX - SR * 0.04},${CY - SR * 0.56})`}
      />
    </g>
  );
}
