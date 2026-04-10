import { Ic } from "../../components/Icon";
import { LevelBadge } from "../../components/LevelBadge";
import { C, F } from "../../constants/theme";
import type { Level, StepState } from "../../types";
import { PodWidget } from "../overview/PodWidget";
import { REACTIVATION_STEPS } from "./reviewerSupport";

interface PodOrbitControlProps {
  level: number;
  levelMeta: Level;
  stepStates: Record<string, StepState>;
  allDone: boolean;
  isRunningAll: boolean;
  onRunAll: () => void;
}

export function PodOrbitControl({
  level,
  levelMeta,
  stepStates,
  allDone,
  isRunningAll,
  onRunAll,
}: PodOrbitControlProps) {
  const podSize = 300;
  const cx = podSize / 2,
    cy = podSize / 2;
  const ringR = cx - 6;
  const steps = REACTIVATION_STEPS;
  const gapDeg = 7;
  const segDeg = (360 - gapDeg * steps.length) / steps.length;

  const ringPt = (deg: number, r = ringR) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const arcD = (startDeg: number, endDeg: number, r = ringR) => {
    const startPoint = ringPt(startDeg, r),
      endPoint = ringPt(endDeg, r);
    return `M ${startPoint.x} ${startPoint.y} A ${r} ${r} 0 ${endDeg - startDeg > 180 ? 1 : 0} 1 ${endPoint.x} ${endPoint.y}`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 24 }}>
      <div style={{ position: "relative", width: podSize, height: podSize }}>
        <div
          style={{
            position: "absolute",
            top: -14,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 3,
            whiteSpace: "nowrap",
          }}
        >
          <LevelBadge level={level} large />
        </div>
        <svg
          width={podSize}
          height={podSize}
          style={{ position: "absolute", inset: 0, overflow: "visible", zIndex: 2 }}
        >
          <title>Reactivation steps</title>
          <circle
            cx={cx}
            cy={cy}
            r={ringR}
            fill="none"
            stroke={levelMeta.color}
            strokeWidth="1"
            opacity="0.12"
            strokeDasharray="4 6"
          />
          {steps.map((step, i) => {
            const startDeg = i * (segDeg + gapDeg),
              endDeg = startDeg + segDeg;
            const state = stepStates[step.key];
            const isDone = state === "done",
              isRun = state === "loading";
            const color = isDone ? "#22c55e" : isRun ? step.color : `${levelMeta.color}30`;
            const width = isDone ? 9 : isRun ? 10 : 5;
            const midPt = ringPt(startDeg + segDeg / 2, ringR + 20);
            return (
              <g key={step.key}>
                <path
                  d={arcD(startDeg, endDeg)}
                  stroke={`${levelMeta.color}15`}
                  strokeWidth="10"
                  fill="none"
                  strokeLinecap="round"
                />
                <path
                  d={arcD(startDeg, endDeg)}
                  stroke={color}
                  strokeWidth={width}
                  fill="none"
                  strokeLinecap="round"
                  style={{ transition: "stroke 0.4s, stroke-width 0.25s" }}
                />
                {isDone && (
                  <path
                    d={arcD(startDeg, endDeg)}
                    stroke="#22c55e"
                    strokeWidth="18"
                    fill="none"
                    strokeLinecap="round"
                    opacity="0.1"
                  />
                )}
                <circle
                  cx={midPt.x}
                  cy={midPt.y}
                  r={isDone ? 6 : isRun ? 5 : 4}
                  fill={isDone ? "#22c55e" : isRun ? step.color : `${levelMeta.color}50`}
                  style={{ transition: "all 0.3s" }}
                />
                {isDone && <circle cx={midPt.x} cy={midPt.y} r={2.5} fill="white" />}
              </g>
            );
          })}
        </svg>
        <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
          <PodWidget level={level} size={podSize} />
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
          marginTop: 2,
        }}
      >
        <div
          style={{
            width: 2,
            height: 16,
            background: `linear-gradient(to bottom, ${levelMeta.color}60, ${levelMeta.color}20)`,
            borderRadius: 1,
          }}
        />
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: levelMeta.color,
            opacity: 0.35,
            marginTop: -1,
          }}
        />
      </div>

      <button
        type="button"
        onClick={onRunAll}
        disabled={isRunningAll || allDone}
        onMouseEnter={(mouseEvent) => {
          if (!isRunningAll && !allDone)
            mouseEvent.currentTarget.style.transform = "translateY(-1px) scale(1.01)";
        }}
        onMouseLeave={(mouseEvent) => {
          mouseEvent.currentTarget.style.transform = "none";
        }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 40px",
          borderRadius: 14,
          background: allDone
            ? "linear-gradient(135deg, #f0fdf4, #dcfce7)"
            : isRunningAll
              ? `${levelMeta.color}18`
              : `linear-gradient(135deg, ${levelMeta.color} 0%, ${levelMeta.ink} 100%)`,
          color: allDone ? "#16a34a" : isRunningAll ? levelMeta.color : "#fff",
          border: allDone
            ? "1.5px solid #bbf7d0"
            : isRunningAll
              ? `1.5px solid ${levelMeta.color}35`
              : "none",
          fontSize: 15,
          fontWeight: 700,
          fontFamily: F.sans,
          letterSpacing: 0.2,
          cursor: isRunningAll || allDone ? "default" : "pointer",
          boxShadow:
            !allDone && !isRunningAll
              ? `0 6px 28px ${levelMeta.color}45, 0 2px 10px ${levelMeta.color}30, inset 0 1px 0 rgba(255,255,255,0.22)`
              : allDone
                ? "0 3px 14px #22c55e20"
                : "none",
          transition: "all 0.2s",
        }}
      >
        <span
          style={{
            display: "flex",
            animation: isRunningAll ? "spin 0.9s linear infinite" : "none",
          }}
        >
          {allDone ? Ic.check(18) : isRunningAll ? Ic.loader(18) : Ic.play(18)}
        </span>
        {allDone ? "All stages verified" : isRunningAll ? "Reactivating…" : "Run Full Reactivation"}
      </button>

      <div
        style={{
          display: "flex",
          gap: 6,
          marginTop: 12,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {steps.map((step) => {
          const state = stepStates[step.key];
          const isDone = state === "done",
            isRun = state === "loading";
          return (
            <div
              key={step.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 8px",
                borderRadius: 5,
                background: isDone ? "#f0fdf4" : isRun ? `${step.color}12` : C.surfaceAlt,
                border: `1px solid ${isDone ? "#bbf7d0" : isRun ? `${step.color}40` : C.border}`,
                transition: "all 0.3s",
              }}
            >
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: isDone ? "#22c55e" : isRun ? step.color : C.borderMid,
                  boxShadow: isRun ? `0 0 6px ${step.color}` : "none",
                  transition: "all 0.3s",
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  fontWeight: isDone || isRun ? 600 : 400,
                  color: isDone ? "#16a34a" : isRun ? step.color : C.textMuted,
                }}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
