import type { RequirementsBannerProps } from "../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../shared/components/Icon";
import { C, F, S_ACTION_BUTTON_BASE } from "../../theme/theme";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function RequirementsBanner({
  status,
  items = [],
  onAction,
  actionLabel,
}: RequirementsBannerProps) {
  const isMissing = status === "missing";

  return (
    <div
      style={{
        background: isMissing ? "#fef2f2" : "#f0fdf4",
        border: `1px solid ${isMissing ? "#fecaca" : "#bbf7d0"}`,
        borderRadius: 10,
        padding: "12px 16px",
        marginBottom: 20,
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
      }}
    >
      <span
        style={{
          color: isMissing ? "#dc2626" : "#16a34a",
          flexShrink: 0,
          marginTop: 1,
          display: "flex",
        }}
      >
        {isMissing ? Ic.info() : Ic.check()}
      </span>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: isMissing ? "#dc2626" : "#16a34a",
            marginBottom: items.length > 0 ? 5 : 0,
          }}
        >
          {isMissing ? "Missing required fields" : "All required fields set"}
        </div>

        {items.length > 0 && (
          <div
            style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: onAction ? 8 : 0 }}
          >
            {items.map((item) => (
              <span
                key={item.field}
                style={{
                  fontSize: 12,
                  fontFamily: F.sans,
                  color: isMissing ? "#dc2626" : "#16a34a",
                  background: isMissing ? "#fff" : "#dcfce7",
                  border: `1px solid ${isMissing ? "#fecaca" : "#bbf7d0"}`,
                  borderRadius: 4,
                  padding: "2px 8px",
                }}
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {onAction && actionLabel && (
          <button
            type="button"
            onClick={onAction}
            style={{
              ...actionBtn({
                border: `1px solid ${C.accentBorder}`,
                borderRadius: 6,
                padding: "4px 10px",
                background: "transparent",
                color: C.accent,
              }),
              cursor: "pointer",
            }}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
