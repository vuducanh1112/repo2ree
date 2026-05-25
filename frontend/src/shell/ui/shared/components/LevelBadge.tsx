import { axisStandings, axisStepLabel } from "../../../../core/review/axes";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { F } from "../../theme/theme";

interface AxisBadgesProps {
  evaluation: EvaluationState;
  large?: boolean;
}

/** Compact readout of the three reproducibility axes (replaces the old LevelBadge). */
export function AxisBadges({ evaluation, large = false }: AxisBadgesProps) {
  return (
    <div style={{ display: "inline-flex", flexWrap: "wrap", gap: large ? 8 : 5 }}>
      {axisStandings(evaluation).map(({ axis, level }) => (
        <div
          key={axis.key}
          title={`${axis.label}: ${axisStepLabel(axis, level)}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: large ? 7 : 5,
            padding: large ? "5px 11px" : "3px 8px",
            background: axis.bg,
            border: `1.5px solid ${axis.color}40`,
            borderRadius: large ? 8 : 5,
          }}
        >
          <div
            style={{
              width: large ? 8 : 6,
              height: large ? 8 : 6,
              borderRadius: "50%",
              background: axis.color,
              boxShadow: `0 0 6px ${axis.color}80`,
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: large ? 12 : 10,
              fontWeight: 700,
              fontFamily: F.mono,
              color: axis.ink,
              letterSpacing: 0.3,
            }}
          >
            {axis.short} · {axisStepLabel(axis, level)}
          </span>
        </div>
      ))}
    </div>
  );
}
