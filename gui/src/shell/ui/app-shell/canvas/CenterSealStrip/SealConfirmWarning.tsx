import { lgBackgrounds } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

interface SealConfirmWarningProps {
  missing: { key: string; label: string }[];
}

function WarningGroup({
  headline,
  items,
}: {
  headline: string;
  items: { key: string; text: string }[];
}) {
  return (
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
        {headline}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 3,
        }}
      >
        {items.map((item) => (
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
              {item.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
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
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {missing.length > 0 && (
            <WarningGroup
              headline={`${missing.length} panel${missing.length !== 1 ? "s" : ""} not connected`}
              items={missing.map((item) => ({
                key: item.key,
                text: `${item.label} — not completed`,
              }))}
            />
          )}
        </div>
      </div>
    </div>
  );
}
