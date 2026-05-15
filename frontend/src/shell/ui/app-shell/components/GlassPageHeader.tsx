import type React from "react";
import { lgStyles } from "../../theme/lightGlassTheme";

interface GlassIconTint {
  color: string;
  border: string;
  shadow: string;
}

interface GlassPageHeaderProps {
  icon: React.ReactNode;
  iconTint?: GlassIconTint;
  title: string;
  badges?: React.ReactNode;
  subtitle: React.ReactNode;
  right?: React.ReactNode;
}

export function GlassPageHeader({
  icon,
  iconTint,
  title,
  badges,
  subtitle,
  right,
}: GlassPageHeaderProps) {
  const iconStyle: React.CSSProperties = iconTint
    ? {
        ...lgStyles.headerIcon,
        color: iconTint.color,
        border: `1px solid ${iconTint.border}`,
        boxShadow: `0 14px 30px ${iconTint.shadow}`,
      }
    : lgStyles.headerIcon;

  return (
    <div style={lgStyles.pageHeader}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
        <div style={iconStyle}>{icon}</div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
              marginBottom: 4,
            }}
          >
            <h1 style={lgStyles.title}>{title}</h1>
            {badges}
          </div>
          <p style={lgStyles.subtitle}>{subtitle}</p>
        </div>
      </div>
      {right}
    </div>
  );
}
