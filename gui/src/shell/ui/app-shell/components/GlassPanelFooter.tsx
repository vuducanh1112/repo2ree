import type React from "react";
import styles from "./GlassPage.module.css";

export function GlassPanelFooter({
  children,
  action,
  bar = false,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
  bar?: boolean;
}) {
  return (
    <div className={styles.footer} data-shape={bar ? "bar" : undefined}>
      <span className={styles.footerText}>{children}</span>
      {action}
    </div>
  );
}
