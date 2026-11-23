import type { ReactNode } from "react";
import { type CssVarValues, cssVars } from "../../theme/styleVars";
import styles from "./Badge.module.css";

type BadgeTone = "success" | "warning" | "info" | "neutral";

interface BadgeProps {
  tone?: BadgeTone;
  tint?: { ink: string; line: string; wash: string };
  icon?: ReactNode;
  flavor?: "prose" | "code";
  role?: "status";
  "aria-label"?: string;
  children: ReactNode;
}

export function Badge({
  tone = "neutral",
  tint,
  icon,
  flavor,
  role,
  "aria-label": ariaLabel,
  children,
}: BadgeProps) {
  const vars: CssVarValues = tint
    ? { "--badge-ink": tint.ink, "--badge-line": tint.line, "--badge-wash": tint.wash }
    : {};
  const live = role ? { role, "aria-label": ariaLabel } : {};
  return (
    <span
      className={styles.badge}
      data-tone={tint ? undefined : tone}
      data-flavor={flavor}
      style={cssVars(vars)}
      {...live}
    >
      {icon && (
        <span aria-hidden className={styles.icon}>
          {icon}
        </span>
      )}
      {children}
    </span>
  );
}
