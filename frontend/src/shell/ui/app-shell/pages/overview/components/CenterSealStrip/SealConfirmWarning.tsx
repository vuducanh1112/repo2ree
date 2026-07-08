import type { StaleSealItem } from "@core/ree-assembly/sealConsistency";
import { lgBackgrounds } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

interface SealConfirmWarningProps {
  missing: { key: string; label: string }[];
  /** Steps whose recorded run no longer matches the tree being sealed. */
  stale?: StaleSealItem[];
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

export function SealConfirmWarning({ missing, stale = [] }: SealConfirmWarningProps) {
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
          {stale.length > 0 && (
            <WarningGroup
              headline={`${stale.length} result${stale.length !== 1 ? "s" : ""} stale — inputs changed since the recorded run`}
              items={stale.map((item) => ({
                key: item.key,
                text: `${item.label} — ${item.detail}`,
              }))}
            />
          )}
        </div>
      </div>
    </div>
  );
}
