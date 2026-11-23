import type { ReactNode } from "react";
import { type CssVarValues, cssVars } from "../../theme/styleVars";
import styles from "./Surface.module.css";

type SurfaceVariant = "card" | "sunken";

type SurfaceSpacing = "flush" | "separated";

interface SurfaceProps {
  variant?: SurfaceVariant;
  spacing?: SurfaceSpacing;
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
