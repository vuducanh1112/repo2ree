import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import type { ReactivationStep } from "./reactivationSteps";

interface RvStepHeaderProps {
  step: ReactivationStep;
  index: number;
  done: boolean;
  running: boolean;
  locked: boolean;
  expanded: boolean;
  onToggle: () => void;
}

export function RvStepHeader({
  step,
  index,
  done,
  running,
  locked,
  expanded,
  onToggle,
}: RvStepHeaderProps) {
  const col = done ? "#22c55e" : locked ? C.textMuted : step.color;

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={locked}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 9,
        padding: "11px 14px",
        background: "transparent",
        border: "none",
        cursor: locked ? "default" : "pointer",
        textAlign: "left",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 1 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              fontFamily: F.mono,
              letterSpacing: 0.6,
              color: col,
              background: `${col}15`,
              border: `1px solid ${col}30`,
              borderRadius: 3,
              padding: "0 5px",
            }}
          >
            {String(index + 1).padStart(2, "0")}
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: locked ? C.textMuted : C.text,
              fontFamily: F.sans,
            }}
          >
            {step.label}
          </span>
          {done && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#16a34a",
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: 4,
                padding: "1px 6px",
              }}
            >
              ✓ passed
            </span>
          )}
          {running && (
            <span
              style={{
                fontSize: 11,
                color: step.color,
                background: `${step.color}12`,
                border: `1px solid ${step.color}30`,
                borderRadius: 4,
                padding: "1px 6px",
              }}
            >
              running…
            </span>
          )}
        </div>
        <span style={{ fontSize: 12, color: locked ? C.textMuted : C.textMid, fontFamily: F.sans }}>
          {step.desc}
        </span>
      </div>
      {!locked && (
        <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
          {expanded ? Ic.chevD(12) : Ic.chevR(12)}
        </span>
      )}
    </button>
  );
}
