import { type ReactNode, useEffect } from "react";
import { Ic } from "../../shared/components/Icon";
import { type CssVarValues, cssVars, cx } from "../../theme/styleVars";
import styles from "./CanvasWindow.module.css";

interface CanvasWindowProps {
  /** Accessible region name; tests select the window by this (role=region). */
  ariaLabel: string;
  onClose: () => void;
  /** Hide the X and ignore Escape while the window must stay open. */
  closable?: boolean;
  /** Close on Escape. Off for windows whose parent owns the Escape key. */
  escapeToClose?: boolean;
  /** Left side of the title bar (icon + title, tab strip, …). */
  header: ReactNode;
  /** Trailing title-bar slot rendered between the header and the X. */
  headerRight?: ReactNode;
  /**
   * Placement: the class from the caller's own module that positions, sizes and
   * animates this window. The frame itself is not the caller's business — the
   * `outerStyle` prop this replaces let every caller re-decide the border, the
   * radius and the shadow, and they had drifted.
   */
  className?: string;
  bodyClassName?: string;
  /** Measured geometry the placement class reads. */
  vars?: CssVarValues;
  /** True to let the frame scroll the body; false when children scroll themselves. */
  scrollBody?: boolean;
  children: ReactNode;
}

/**
 * The one window frame for everything floating over the canvas (docked pages,
 * hub panels, the file viewer): a desktop-style title bar — header content on
 * the left, actions and a pinned X on the right — above a separate content
 * area. The bar never scrolls; the body does, so the X is always reachable.
 */
export function CanvasWindow({
  ariaLabel,
  onClose,
  closable = true,
  escapeToClose = false,
  header,
  headerRight,
  className,
  bodyClassName,
  vars,
  scrollBody = false,
  children,
}: CanvasWindowProps) {
  useEffect(() => {
    if (!closable || !escapeToClose) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closable, escapeToClose, onClose]);

  return (
    <section
      aria-label={ariaLabel}
      data-canvas-hud
      className={cx(styles.window, className)}
      style={cssVars(vars ?? {})}
    >
      <div className={styles.bar}>
        <div className={styles.barMain}>{header}</div>
        {headerRight}
        {closable && (
          <button type="button" aria-label="Close" onClick={onClose} className={styles.close}>
            {Ic.x(14)}
          </button>
        )}
      </div>

      <div className={cx(styles.body, bodyClassName)} data-scroll={scrollBody || undefined}>
        {children}
      </div>
    </section>
  );
}

interface CanvasWindowTitleProps {
  /** Accent-coloured leading icon, e.g. `Ic.package(16)`. */
  icon?: ReactNode;
  /** The icon's tone, as a `var(--…)` reference. */
  iconTint?: string;
  title: string;
  subtitle?: string;
}

/** The standard single-line title-bar content: icon, bold title, mono subtitle. */
export function CanvasWindowTitle({ icon, iconTint, title, subtitle }: CanvasWindowTitleProps) {
  return (
    <>
      {icon && (
        <span
          aria-hidden
          className={styles.titleIcon}
          style={cssVars(iconTint ? { "--window-title-tint": iconTint } : {})}
        >
          {icon}
        </span>
      )}
      <span className={styles.title}>{title}</span>
      {subtitle && <span className={styles.subtitle}>{subtitle}</span>}
    </>
  );
}
