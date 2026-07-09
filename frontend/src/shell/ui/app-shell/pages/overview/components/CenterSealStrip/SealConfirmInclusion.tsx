import { Toggle } from "@shell/ui/shared/components/Toggle";
import { lgColors, lgStage } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

interface InclusionRow {
  label: string;
  available: boolean;
  included: boolean;
  tintLine: string;
  tintInk: string;
  onToggle: () => void;
}

interface SealConfirmInclusionProps {
  sourceAvailable: boolean;
  runtimeAvailable: boolean;
  resultsAvailable: boolean;
  includeSource: boolean;
  includeRuntime: boolean;
  includeResults: boolean;
  onToggleSource: () => void;
  onToggleRuntime: () => void;
  onToggleResults: () => void;
}

function Row({ label, available, included, tintLine, tintInk, onToggle }: InclusionRow) {
  const on = available && included;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        opacity: available ? 1 : 0.45,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <span style={{ fontSize: 12, fontFamily: F.sans, fontWeight: 700, color: lgColors.text }}>
          {label}
        </span>
        <span style={{ fontSize: 10, fontFamily: F.sans, color: lgColors.textMuted }}>
          {!available ? "Not in workspace" : on ? "Bundled into the archive" : "Excluded"}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontSize: 10,
            fontFamily: F.sans,
            fontWeight: 700,
            color: on ? tintInk : lgColors.textMuted,
          }}
        >
          {on ? "Included" : "Include"}
        </span>
        <Toggle on={on} disabled={!available} color={tintLine} onChange={onToggle} />
      </div>
    </div>
  );
}

export function SealConfirmInclusion({
  sourceAvailable,
  runtimeAvailable,
  resultsAvailable,
  includeSource,
  includeRuntime,
  includeResults,
  onToggleSource,
  onToggleRuntime,
  onToggleResults,
}: SealConfirmInclusionProps) {
  return (
    <div
      style={{
        margin: "0 20px 4px",
        padding: "12px 14px",
        borderRadius: 10,
        background: "rgba(248, 250, 252, 0.7)",
        border: "1px solid rgba(148, 163, 184, 0.28)",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <span
        style={{
          fontSize: 10,
          fontFamily: F.sans,
          fontWeight: 800,
          letterSpacing: 0.5,
          color: lgColors.textMuted,
          textTransform: "uppercase",
        }}
      >
        Bundle contents
      </span>
      <Row
        label="Source"
        available={sourceAvailable}
        included={includeSource}
        tintLine={lgStage.source.line}
        tintInk={lgStage.source.ink}
        onToggle={onToggleSource}
      />
      <Row
        label="Runtime"
        available={runtimeAvailable}
        included={includeRuntime}
        tintLine={lgStage.runtime.line}
        tintInk={lgStage.runtime.ink}
        onToggle={onToggleRuntime}
      />
      <Row
        label="Results"
        available={resultsAvailable}
        included={includeResults}
        tintLine={lgStage.experiments.line}
        tintInk={lgStage.experiments.ink}
        onToggle={onToggleResults}
      />
    </div>
  );
}
