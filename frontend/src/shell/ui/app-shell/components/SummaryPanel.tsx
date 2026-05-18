import type React from "react";
import { lgColors, lgStyles } from "../../theme/lightGlassTheme";

interface SummaryPanelProps {
  title: string;
  icon: React.ReactNode;
  iconColor: string;
  children: React.ReactNode;
}

export function SummaryPanel({ title, icon, iconColor, children }: SummaryPanelProps) {
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ color: iconColor, display: "flex" }}>{icon}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>{title}</h2>
      </div>
      <div style={lgStyles.summaryBox}>{children}</div>
    </section>
  );
}
