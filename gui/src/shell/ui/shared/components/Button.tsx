import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cssVars, cx } from "../../theme/styleVars";
import styles from "./Button.module.css";

/** What the button is for, not what it looks like.
 *
 * `primary` commits the page's main action, `secondary` is every other glass
 * control, `danger` cancels or destroys, and `accent` is a primary tinted by a
 * domain identity rather than the shared blue. A fifth reading has to earn
 * itself: the point of the primitive is that hover, focus, active and disabled
 * are decided once, and a variant per call site puts that back where it was.
 */
type ButtonVariant = "primary" | "secondary" | "danger" | "accent";

type ButtonSize = "medium" | "small" | "tiny";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "style"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /**
   * Leading glyph. Rendered `aria-hidden` because every icon in this codebase
   * carries a `<title>` for standalone use, and that title would otherwise be
   * concatenated into the button's accessible name.
   */
  icon?: ReactNode;
  /** Spins the icon and marks the control busy for assistive tech. */
  busy?: boolean;
  /**
   * The domain tone this control belongs to, as a `var(--…)` reference from
   * `theme/appearance`. Required by `accent`; on `secondary` it produces the
   * same control washed in that tone.
   */
  tint?: string;
  fullWidth?: boolean;
  children: ReactNode;
}

/**
 * The one button. It owns hover, focus-visible, active, disabled and
 * reduced-motion so no caller has to reproduce them, and it is always
 * `type="button"` unless a caller genuinely submits a form — a bare `<button>`
 * inside a form defaults to submit and navigates the page away.
 */
export function Button({
  variant = "secondary",
  size = "medium",
  icon,
  busy = false,
  tint,
  fullWidth = false,
  type = "button",
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(styles.button)}
      data-variant={variant}
      data-size={size}
      data-full-width={fullWidth || undefined}
      data-tinted={tint ? true : undefined}
      aria-busy={busy || undefined}
      disabled={disabled}
      style={cssVars(tint ? { "--control-line": tint } : {})}
      {...rest}
    >
      {icon && (
        <span aria-hidden className={styles.icon}>
          {icon}
        </span>
      )}
      {children}
    </button>
  );
}
