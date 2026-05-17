import type React from "react";
import {
  type BuildScriptMode,
  type BuildScriptSource,
  provenanceLabel,
} from "../../../../../../core/ree-assembly/buildRuntimeUiState";
import { Ic } from "../../../../shared/components/Icon";
import { lgColors, lgPillChip } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

export function ProvenanceChip({ source }: { source: BuildScriptSource | null }) {
  return <span style={lgPillChip(!!source)}>{provenanceLabel(source)}</span>;
}

export function ModeSegmentedControl({
  mode,
  onChange,
}: {
  mode: BuildScriptMode;
  onChange: (next: BuildScriptMode) => void;
}) {
  const options: Array<{ key: BuildScriptMode; label: string; icon: React.ReactNode }> = [
    { key: "pick", label: "Pick existing", icon: Ic.file(13) },
    { key: "write", label: "Write", icon: Ic.terminal(13) },
    { key: "generate", label: "Generate", icon: Ic.layers(13) },
  ];
  return (
    <div
      style={{
        display: "inline-flex",
        gap: 4,
        padding: 4,
        background: "rgba(241, 245, 249, 0.78)",
        border: "1px solid rgba(148, 163, 184, 0.32)",
        borderRadius: 999,
      }}
    >
      {options.map((option) => {
        const active = option.key === mode;
        return (
          <button
            key={option.key}
            type="button"
            onClick={() => onChange(option.key)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: 999,
              border: "none",
              background: active ? "rgba(255, 255, 255, 0.95)" : "transparent",
              color: active ? lgColors.primaryDeep : lgColors.textMid,
              fontWeight: 700,
              fontSize: 12,
              cursor: "pointer",
              boxShadow: active ? "0 6px 14px rgba(14, 165, 233, 0.16)" : "none",
              fontFamily: F.sans,
            }}
          >
            <span style={{ display: "flex" }}>{option.icon}</span>
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function BaseChip({
  active,
  label,
  hint,
  onClick,
}: {
  active: boolean;
  label: string;
  hint?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 2,
        padding: "9px 12px",
        borderRadius: 10,
        border: active
          ? "1px solid rgba(14, 165, 233, 0.5)"
          : "1px solid rgba(148, 163, 184, 0.34)",
        background: active ? "rgba(239, 246, 255, 0.95)" : "rgba(255, 255, 255, 0.7)",
        cursor: "pointer",
        textAlign: "left",
        boxShadow: active
          ? "0 6px 18px rgba(14, 165, 233, 0.18)"
          : "inset 0 1px 0 rgba(255, 255, 255, 0.88)",
        minWidth: 160,
      }}
    >
      <span
        style={{
          fontSize: 12,
          fontWeight: 800,
          color: active ? lgColors.primaryDeep : lgColors.text,
          fontFamily: F.sans,
        }}
      >
        {label}
      </span>
      {hint && (
        <span style={{ fontSize: 11, color: lgColors.textMuted, fontFamily: F.sans }}>{hint}</span>
      )}
    </button>
  );
}
