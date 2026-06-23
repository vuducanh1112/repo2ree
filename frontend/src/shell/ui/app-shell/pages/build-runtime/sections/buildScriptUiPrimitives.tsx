import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

// A pill marking where the currently selected script lives. Overlay files are
// the REE's editable recipe layer; "source" files come from the immutable
// upstream tree, so editing one writes an overlay copy rather than mutating it.
export function ScriptOriginChip({ overlay }: { overlay: boolean }) {
  const tint = overlay
    ? {
        color: lgColors.primaryDeep,
        border: "rgba(14, 165, 233, 0.4)",
        bg: "rgba(239, 246, 255, 0.9)",
      }
    : {
        color: lgColors.textMid,
        border: "rgba(148, 163, 184, 0.4)",
        bg: "rgba(248, 250, 252, 0.9)",
      };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "4px 10px",
        borderRadius: 999,
        border: `1px solid ${tint.border}`,
        background: tint.bg,
        color: tint.color,
        fontWeight: 700,
        fontSize: 11,
        fontFamily: F.sans,
      }}
    >
      {overlay ? Ic.layers(11) : Ic.file(11)} {overlay ? "Overlay" : "Upstream source"}
    </span>
  );
}

export function ClearScriptButton({ onClear }: { onClear: () => void }) {
  return (
    <button
      type="button"
      onClick={onClear}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        border: `1px solid ${lgColors.dangerBorder}`,
        background: "rgba(255, 241, 242, 0.82)",
        color: lgColors.danger,
        padding: "6px 12px",
        borderRadius: 999,
        fontWeight: 700,
        fontSize: 11,
        cursor: "pointer",
        fontFamily: F.sans,
      }}
    >
      {Ic.x(11)} Clear script
    </button>
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
