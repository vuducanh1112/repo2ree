import type React from "react";
import styles from "./GlassPage.module.css";

// Wraps a single major section (header + content) in an inset card so the
// sections of a page read as distinct subpanels instead of one continuous glass
// surface. Stack several inside a page's gap'd column.
//
// The `style` escape hatch is gone: no caller ever passed one.
export function GlassSubPanel({ children }: { children: React.ReactNode }) {
  return <div className={styles.subPanel}>{children}</div>;
}
