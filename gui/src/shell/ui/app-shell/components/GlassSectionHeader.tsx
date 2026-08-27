import type React from "react";
import { cssVars } from "../../theme/styleVars";
import styles from "./GlassPage.module.css";

interface GlassSectionHeaderProps {
  /** Omitted by a page whose section has no siblings to be told apart from. */
  icon?: React.ReactNode;
  /** The section's tone, as a `var(--…)` reference. Defaults to the page's. */
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
