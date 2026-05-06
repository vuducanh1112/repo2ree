import { Ic } from "../../shared/components/Icon";
import { C } from "../../theme/theme";
import type { ReactivationStep } from "./reactivationSteps";

interface RvStepIndicatorProps {
  step: ReactivationStep;
  done: boolean;
  running: boolean;
  locked: boolean;
  isLast: boolean;
}

export function RvStepIndicator({ step, done, running, locked, isLast }: RvStepIndicatorProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        flexShrink: 0,
        width: 28,
      }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          flexShrink: 0,
          background: done ? "#22c55e" : locked ? C.surfaceAlt : `${step.color}18`,
          border: `2px solid ${done ? "#22c55e" : locked ? C.borderMid : step.color}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: done ? "#fff" : locked ? C.textMuted : step.color,
          transition: "all 0.3s",
          boxShadow: done ? "0 0 0 3px #22c55e20" : running ? `0 0 0 3px ${step.color}25` : "none",
        }}
      >
        {done ? (
          Ic.check(11)
        ) : (
          <span
            style={{ animation: running ? "spin 0.9s linear infinite" : "none", display: "flex" }}
          >
            {running ? Ic.loader(11) : step.icon(11)}
          </span>
        )}
      </div>
      {!isLast && (
        <div
          style={{
            flex: 1,
            width: 2,
            minHeight: 20,
            marginTop: 4,
            background: done ? "#22c55e" : C.border,
            transition: "background 0.4s",
            borderRadius: 1,
          }}
        />
      )}
    </div>
  );
}
