import type React from "react";
import styles from "./GlassPage.module.css";

// The muted hint bar at the foot of a page. `bar` picks the standalone rounded
// variant (for pages split into separate subpanels); the default welds to the
// bottom of a single glass panel.
//
// `action` is the trailing control — the "Next: …" step button most pages end
// with. A named slot rather than a style hole: hint on the left, action on the
// right is the only arrangement any page here wanted.
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
