import type { ReactNode } from "react";
import { type CssVarValues, cssVars } from "../../theme/styleVars";
import styles from "./Badge.module.css";

/** The semantic readings a badge has on its own. A badge whose colour is a
 * domain identity — the stage an outcome belongs to, an archive target — passes
 * `tint` instead, because that identity is not one of three fixed moods. */
type BadgeTone = "success" | "warning" | "info" | "neutral";

interface BadgeProps {
  tone?: BadgeTone;
  /**
   * A domain tone, as the `ink`/`line`/`wash` triple from `theme/appearance`.
   * Typed as custom properties rather than a `style` prop so a caller can tint
   * a badge but cannot restyle it.
   *
   * `ink` is separate from `line` because they answer different questions: the
   * text has to clear 4.5:1 against the wash, while the edge only has to be
   * seen. Passing a mid `line` shade for both is how "Built" ended up at
   * 3.5:1 — a slot named for the rule, filled with the colour of the rule,
   * painting the words.
   */
  tint?: { ink: string; line: string; wash: string };
  icon?: ReactNode;
  /** `code` puts a path or identifier in the monospace face. */
  flavor?: "prose" | "code";
  /** Announce the badge as a live status region rather than plain text. */
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
  // The label rides with the role rather than being applied beside it: on a
  // plain <span> `aria-label` names nothing, so emitting one without the role
  // would be a silent no-op.
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
