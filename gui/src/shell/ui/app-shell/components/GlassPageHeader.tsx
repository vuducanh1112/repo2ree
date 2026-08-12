import type React from "react";
import { cssVars } from "../../theme/styleVars";
import styles from "./GlassPage.module.css";

interface GlassPageHeaderProps {
  icon: React.ReactNode;
  /**
   * The page's own tone, as a `var(--…)` reference. The icon's edge and glow
   * are derived from it, which is what the three-field `iconTint` object used
   * to spell out at every call site.
   */
  tint?: string;
  title: string;
  badges?: React.ReactNode;
  subtitle: React.ReactNode;
  right?: React.ReactNode;
}

export function GlassPageHeader({
  icon,
  tint,
  title,
  badges,
  subtitle,
  right,
}: GlassPageHeaderProps) {
  return (
    <div className={styles.pageHeader}>
      <div className={styles.identity}>
        <div
          className={styles.pageIcon}
          data-tinted={tint ? true : undefined}
          style={cssVars(tint ? { "--page-tint": tint } : {})}
        >
          {icon}
        </div>
        <div className={styles.headings}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>{title}</h1>
            {badges}
          </div>
          <p className={styles.subtitle}>{subtitle}</p>
        </div>
      </div>
      {right}
    </div>
  );
}
