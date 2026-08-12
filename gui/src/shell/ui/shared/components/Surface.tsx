import type { ReactNode } from "react";
import { type CssVarValues, cssVars } from "../../theme/styleVars";
import styles from "./Surface.module.css";

type SurfaceVariant = "card" | "sunken";

/** Whether the surface sits flush against what precedes it or stands apart.
 * These are the only two spacings the glass pages actually use — `lgContentCard`
 * took a pixel count, and every call site passed 0 or 12. */
type SurfaceSpacing = "flush" | "separated";

interface SurfaceProps {
  variant?: SurfaceVariant;
  spacing?: SurfaceSpacing;
  /**
   * Runtime geometry only — a measured max-height, for instance. Custom
   * properties rather than a style prop, so a caller can size a surface but
   * cannot re-skin it.
   */
  vars?: CssVarValues;
  children: ReactNode;
}

export function Surface({ variant = "card", spacing = "separated", vars, children }: SurfaceProps) {
  return (
    <div
      className={styles.surface}
      data-variant={variant}
      data-spacing={spacing}
      style={cssVars(vars ?? {})}
    >
      {children}
    </div>
  );
}
