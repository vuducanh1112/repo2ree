import type { LogLine } from "../../../domain/ree/ReeTypes";
import { AssemblyRunLogSection } from "../../app-shell/components/assemblyRunPanels";
import { Ic } from "../../shared/components/Icon";
import { actionBtn } from "./RvStepShared";
import type { ReactivationStep } from "./reactivationSteps";

interface RvStepActionsProps {
  step: ReactivationStep;
  running: boolean;
  done: boolean;
  log: LogLine[] | null;
  onRun: () => void;
  onCancel?: () => void;
}

export function RvStepActions({ step, running, done, log, onRun, onCancel }: RvStepActionsProps) {
  return (
    <>
      <button
        type="button"
        onClick={onRun}
        disabled={running}
        style={{
          ...actionBtn({
            padding: "9px 14px",
            borderRadius: 8,
            border: done ? "1.5px solid #bbf7d0" : "none",
            background: running ? `${step.color}20` : done ? "#f0fdf4" : step.color,
            color: running ? step.color : done ? "#16a34a" : "#fff",
            fontWeight: 600,
          }),
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 7,
          width: "100%",
          cursor: running ? "wait" : "pointer",
          marginBottom: log ? 12 : 0,
          boxShadow: !done && !running ? `0 2px 10px ${step.color}35` : "none",
        }}
      >
        <span
          style={{
            display: "flex",
            animation: running ? "spin 0.9s linear infinite" : "none",
          }}
        >
          {running ? Ic.loader(13) : done ? Ic.refresh(13) : Ic.play(13)}
        </span>
        {running ? "Running…" : done ? "Re-run" : `Run ${step.label}`}
      </button>
      {running && onCancel && (
        <button
          type="button"
          onClick={onCancel}
          style={{
            ...actionBtn({
              padding: "8px 12px",
              borderRadius: 8,
              background: "#fff1f2",
              border: "1.5px solid #fecdd3",
              color: "#be123c",
              fontWeight: 700,
            }),
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            width: "100%",
            marginBottom: log ? 12 : 0,
          }}
        >
          {Ic.x(13)} Cancel
        </button>
      )}
      {log && (
        <AssemblyRunLogSection
          log={{ lines: log, ts: log[log.length - 1]?.ts || new Date().toISOString() }}
          running={running}
          title="Output"
        />
      )}
    </>
  );
}
