import { Ic } from "../../../shared/components/Icon";
import { C, S_SECTION_LABEL, S_TEXT_MUTED_11 } from "../../../theme/theme";
import { actionBtn } from "./shared";

interface AssemblyActionSectionProps {
  color: string;
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  idleLabel: string;
  runningLabel: string;
  doneLabel?: string;
  helperText: string;
  onRun: () => void;
  onCancel?: () => void;
}
export function AssemblyRunActionSection({
  color,
  running,
  runDone,
  disabled,
  idleLabel,
  runningLabel,
  doneLabel = "Re-run",
  helperText,
  onRun,
  onCancel,
}: AssemblyActionSectionProps) {
  const buttonLabel = running ? runningLabel : runDone ? doneLabel : idleLabel;
  return (
    <div
      style={{ padding: "20px 24px 16px", flexShrink: 0, borderBottom: `1px solid ${C.border}` }}
    >
      <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Action</div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          style={{
            ...actionBtn({
              border: "none",
              borderRadius: 8,
              padding: "8px 18px",
              fontWeight: 700,
            }),
            display: "flex",
            alignItems: "center",
            gap: 7,
            background: disabled ? `${color}22` : color,
            cursor: disabled ? "default" : "pointer",
            color: disabled ? color : "#fff",
          }}
        >
          <span
            style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
          >
            {running ? Ic.loader(14) : Ic.play(14)}
          </span>
          {buttonLabel}
        </button>
        {running && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            style={{
              ...actionBtn({
                borderRadius: 8,
                padding: "8px 14px",
                fontWeight: 700,
              }),
              display: "flex",
              alignItems: "center",
              gap: 7,
              background: "#fff1f2",
              border: "1.5px solid #fecdd3",
              color: "#be123c",
              cursor: "pointer",
            }}
          >
            {Ic.x(14)} Cancel
          </button>
        )}
        <div style={S_TEXT_MUTED_11}>{helperText}</div>
      </div>
    </div>
  );
}
