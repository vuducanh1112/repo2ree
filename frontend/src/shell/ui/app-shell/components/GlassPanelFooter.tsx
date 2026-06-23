import type React from "react";
import { lgColors, lgStyles } from "../../theme/lightGlassTheme";
import { F } from "../../theme/theme";

// The muted hint bar at the foot of a page. `bar` picks the standalone rounded
// variant (for pages split into separate subpanels); the default welds to the
// bottom of a single glass panel.
export function GlassPanelFooter({
  children,
  bar = false,
}: {
  children: React.ReactNode;
  bar?: boolean;
}) {
  return (
    <div style={bar ? lgStyles.footerBar : lgStyles.footer}>
      <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
        {children}
      </span>
    </div>
  );
}
