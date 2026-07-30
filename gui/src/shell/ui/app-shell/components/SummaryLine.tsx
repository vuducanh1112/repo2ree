import type React from "react";
import { lgColors } from "../../theme/lightGlassTheme";
import { F } from "../../theme/theme";

export function SummaryLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <span style={{ fontSize: 11, color: lgColors.textMuted, fontFamily: F.sans }}>{label}</span>
      <span
        style={{
          fontSize: 13,
          color: lgColors.text,
          fontFamily: F.sans,
          lineHeight: 1.35,
          overflowWrap: "anywhere",
        }}
      >
        {value}
      </span>
    </div>
  );
}
