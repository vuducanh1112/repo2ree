import type React from "react";
import { lgColors, lgReadout, lgStyles } from "../../theme/lightGlassTheme";
import { F } from "../../theme/theme";

interface ReadinessPanelProps {
  title: string;
  percent: number;
  done: number;
  total: number;
  children: React.ReactNode;
}

export function ReadinessPanel({ title, percent, done, total, children }: ReadinessPanelProps) {
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={lgStyles.readinessHeader}>
        <span>{title}</span>
        <span style={{ color: lgColors.blue, fontFamily: F.mono }}>{percent}%</span>
      </div>
      <div style={lgStyles.progressTrack}>
        <div style={{ ...lgStyles.progressFill, width: `${percent}%` }} />
      </div>
      <div style={lgStyles.statGrid}>
        {children}
        <div style={lgReadout(lgStyles.statReadout)}>
          <span style={{ color: lgColors.textMuted, fontSize: 11 }}>Checks</span>
          <strong style={{ color: lgColors.text, fontSize: 18 }}>
            {done}/{total}
          </strong>
        </div>
      </div>
    </section>
  );
}
