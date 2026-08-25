import type React from "react";
import { type CssVarValues, cssVars, cx } from "../../theme/styleVars";
import styles from "./HudConsole.module.css";
import { StatusDot } from "./StatusDot";

interface HudConsoleProps {
  open: boolean;
  onToggle: () => void;
  widthOpen: number;
  widthCollapsed: number;
  /** The class from the caller's own module that places this console. */
  className?: string;
  bodyClassName?: string;
  /** Measured geometry the placement class reads. */
  vars?: CssVarValues;
  /** True while a resize drag owns the width, so the easing stands down. */
  resizing?: boolean;
  icon: React.ReactNode;
  /** The icon's tone, as a `var(--…)` reference. */
  iconTint?: string;
  title: string;
  subtitle?: React.ReactNode;
  /** Drives the StatusDot. */
  on: boolean;
  expandLabel: string;
  collapseLabel: string;
  /** When set, the body animates its max-height to this many px instead of
   * being conditionally rendered. */
  bodyMaxHeight?: number;
  /** Optional resize grip, absolutely positioned by the caller. */
  resizeGrip?: React.ReactNode;
  children?: React.ReactNode;
}

// Shared chrome for the pinned HUD consoles (FileTreeConsole, BenchConsole): the
// frosted card, the expand/collapse header button, and the collapsible body slot.
export function HudConsole({
  open,
  onToggle,
  widthOpen,
  widthCollapsed,
  className,
  bodyClassName,
  vars,
  resizing = false,
  icon,
  iconTint,
  title,
  subtitle,
  on,
  expandLabel,
  collapseLabel,
  bodyMaxHeight,
  resizeGrip,
  children,
}: HudConsoleProps) {
  const body =
    bodyMaxHeight != null ? (
      <div className={styles.collapse} aria-hidden={!open}>
        <div className={cx(styles.collapseBody, bodyClassName)}>{children}</div>
      </div>
    ) : open ? (
      <div className={cx(styles.body, bodyClassName)}>{children}</div>
    ) : null;

  return (
    <div
      data-canvas-hud
      className={cx(styles.console, className)}
      data-open={open || undefined}
      data-resizing={resizing || undefined}
      style={cssVars({
        "--hud-width-open": `${widthOpen}px`,
        "--hud-width-collapsed": `${widthCollapsed}px`,
        "--hud-body-height": bodyMaxHeight == null ? undefined : `${bodyMaxHeight}px`,
        "--hud-icon-tint": iconTint,
        ...vars,
      })}
    >
      {resizeGrip}
      <button
        type="button"
        aria-expanded={open}
        aria-label={open ? collapseLabel : expandLabel}
        onClick={onToggle}
        className={styles.header}
      >
        <span aria-hidden className={styles.icon}>
          {icon}
        </span>
        <div className={styles.labels}>
          <span className={styles.title}>{title}</span>
          {subtitle ? <span className={styles.subtitle}>{subtitle}</span> : null}
        </div>
        <StatusDot on={on} />
        <span aria-hidden className={styles.chevron}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <title>toggle</title>
            <path
              d="M6 15l6-6 6 6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>
      {body}
    </div>
  );
}
