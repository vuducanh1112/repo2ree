import { Ic } from "../../shared/components/Icon";
import { lgColors } from "../../theme/lightGlassTheme";

export function GlassCancelButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        border: `1px solid ${lgColors.dangerBorder}`,
        background: "rgba(255, 241, 242, 0.82)",
        color: lgColors.danger,
        padding: "8px 14px",
        borderRadius: 8,
        fontWeight: 700,
        cursor: "pointer",
        width: "100%",
      }}
    >
      {Ic.x(14)} Cancel
    </button>
  );
}
