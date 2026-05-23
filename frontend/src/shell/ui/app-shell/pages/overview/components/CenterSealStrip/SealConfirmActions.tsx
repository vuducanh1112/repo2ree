import { Ic } from "../../../../../shared/components/Icon";
import { lgBackgrounds, lgColors } from "../../../../../theme/lightGlassTheme";
import { hoverBg, hoverBrightness, S_ACTION_BUTTON_BASE } from "../../../../../theme/theme";

interface SealConfirmActionsProps {
  onClose: () => void;
  onConfirm: () => void;
  confirmLabel: string;
  confirmColor: string;
}

export function SealConfirmActions({
  onClose,
  onConfirm,
  confirmLabel,
  confirmColor,
}: SealConfirmActionsProps) {
  return (
    <div
      style={{
        padding: "0 20px 16px",
        display: "flex",
        gap: 8,
        justifyContent: "flex-end",
      }}
    >
      <button
        type="button"
        onClick={onClose}
        style={{
          ...S_ACTION_BUTTON_BASE,
          padding: "8px 16px",
          borderRadius: 7,
          fontSize: 12,
          fontWeight: 700,
          cursor: "pointer",
          background: lgBackgrounds.glassStrong,
          color: lgColors.textMid,
          border: "1px solid rgba(148, 163, 184, 0.34)",
        }}
        {...hoverBg("rgba(241, 245, 249, 0.9)", lgBackgrounds.glassStrong)}
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={onConfirm}
        style={{
          ...{
            ...S_ACTION_BUTTON_BASE,
            display: "flex",
            alignItems: "center",
            gap: 7,
            padding: "8px 18px",
            borderRadius: 7,
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            color: "#fff",
          },
          background: confirmColor,
          border: `1.5px solid ${confirmColor}`,
          boxShadow: `0 2px 8px ${confirmColor}50`,
        }}
        {...hoverBrightness(90)}
      >
        <span style={{ display: "flex" }}>{Ic.lock(12)}</span>
        {confirmLabel}
      </button>
    </div>
  );
}
