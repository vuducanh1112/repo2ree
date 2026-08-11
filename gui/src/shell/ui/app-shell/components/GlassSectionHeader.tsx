import type React from "react";
import { translucent } from "../../theme/appearance";
import { lgStyles } from "../../theme/lightGlassTheme";

interface GlassSectionHeaderProps {
  icon: React.ReactNode;
  color: string;
  title: string;
  subtitle: string;
}

export function GlassSectionHeader({ icon, color, title, subtitle }: GlassSectionHeaderProps) {
  return (
    <div style={lgStyles.sectionHeader}>
      <div
        style={{ ...lgStyles.sectionIcon, color, border: `1px solid ${translucent(color, 28)}` }}
      >
        {icon}
      </div>
      <div>
        <h2 style={lgStyles.sectionTitle}>{title}</h2>
        <div style={lgStyles.sectionSubtitle}>{subtitle}</div>
      </div>
    </div>
  );
}
