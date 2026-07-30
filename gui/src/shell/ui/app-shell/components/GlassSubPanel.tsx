import type React from "react";
import { lgStyles } from "../../theme/lightGlassTheme";

// Wraps a single major section (header + content) in an inset card so the
// sections of a page read as distinct subpanels instead of one continuous glass
// surface. Stack several inside a page's gap'd column.
export function GlassSubPanel({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return <div style={{ ...lgStyles.subPanel, ...style }}>{children}</div>;
}
