import { lgBackgrounds } from "../../../../../theme/lightGlassTheme";
import { F } from "../../../../../theme/theme";

interface SealConfirmWarningProps {
  missing: { key: string; label: string }[];
}

export function SealConfirmWarning({ missing }: SealConfirmWarningProps) {
  return (
    <div
      style={{
        margin: "12px 20px 0",
        padding: "10px 12px",
        borderRadius: 8,
        background: lgBackgrounds.draft,
        border: "1px solid rgba(245, 158, 11, 0.45)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
        }}
      >
        <span
          style={{
            fontSize: 15,
            flexShrink: 0,
            lineHeight: 1.2,
          }}
        >
          ⚠️
        </span>
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              fontFamily: F.sans,
              color: "#92400e",
              marginBottom: 5,
            }}
          >
            {missing.length} panel{missing.length !== 1 ? "s" : ""} not connected
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 3,
            }}
          >
            {missing.map((item) => (
              <div
                key={item.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <div
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: "#f59e0b",
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: F.sans,
                    color: "#92400e",
                  }}
                >
                  {item.label} — not completed
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
