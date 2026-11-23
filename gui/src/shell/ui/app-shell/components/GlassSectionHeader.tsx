import type React from "react";
import { cssVars } from "../../theme/styleVars";
import styles from "./GlassPage.module.css";

interface GlassSectionHeaderProps {
  icon?: React.ReactNode;
  tint?: string;
  title: string;
  subtitle?: string;
}

export function GlassSectionHeader({ icon, tint, title, subtitle }: GlassSectionHeaderProps) {
  return (
    <div className={styles.sectionHeader}>
      {icon && (
        <div
          className={styles.sectionIcon}
          data-tinted={tint ? true : undefined}
          style={cssVars(tint ? { "--section-tint": tint } : {})}
        >
          {icon}
        </div>
      )}
      <div>
        <h2 className={styles.sectionTitle}>{title}</h2>
        {subtitle && <div className={styles.sectionSubtitle}>{subtitle}</div>}
      </div>
    </div>
  );
}
