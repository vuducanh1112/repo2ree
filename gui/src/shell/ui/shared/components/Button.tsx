import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cssVars, cx } from "../../theme/styleVars";
import styles from "./Button.module.css";

type ButtonVariant = "primary" | "secondary" | "danger" | "accent";

type ButtonSize = "medium" | "small" | "tiny";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "style"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  busy?: boolean;
  tint?: string;
  fullWidth?: boolean;
  children: ReactNode;
}

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
