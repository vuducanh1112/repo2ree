import { Ic } from "../../../../../shared/components/Icon";
import { C, hoverBg, hoverBrightness, S_ACTION_BUTTON_BASE } from "../../../../../theme/theme";

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
          fontWeight: 600,
          cursor: "pointer",
          background: C.surfaceAlt,
          color: C.textMid,
          border: `1.5px solid ${C.border}`,
        }}
        {...hoverBg(C.border, C.surfaceAlt)}
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
