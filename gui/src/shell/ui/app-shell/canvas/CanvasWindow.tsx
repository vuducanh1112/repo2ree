import {
  type KeyboardEventHandler,
  type PointerEventHandler,
  type ReactNode,
  useEffect,
} from "react";
import { Ic } from "../../shared/components/Icon";
import { type CssVarValues, cssVars, cx } from "../../theme/styleVars";
import styles from "./CanvasWindow.module.css";

interface CanvasWindowProps {
  ariaLabel: string;
  onClose: () => void;
  closable?: boolean;
  escapeToClose?: boolean;
  modal?: boolean;
  onKeyDown?: KeyboardEventHandler<HTMLElement>;
  onBarPointerDown?: PointerEventHandler<HTMLDivElement>;
  header: ReactNode;
  headerRight?: ReactNode;
  className?: string;
  bodyClassName?: string;
  vars?: CssVarValues;
  scrollBody?: boolean;
  children: ReactNode;
}

export function CanvasWindow({
  ariaLabel,
  onClose,
  closable = true,
  escapeToClose = false,
  modal = false,
  onKeyDown,
  onBarPointerDown,
  header,
  headerRight,
  className,
  bodyClassName,
  vars,
  scrollBody = false,
  children,
}: CanvasWindowProps) {
  const modalAttributes = modal ? ({ role: "dialog", "aria-modal": true } as const) : {};

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
      {...modalAttributes}
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      data-canvas-hud
      className={cx(styles.window, className)}
      style={cssVars(vars ?? {})}
    >
      <div
        className={styles.bar}
        data-draggable={onBarPointerDown ? "" : undefined}
        onPointerDown={onBarPointerDown}
      >
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
  icon?: ReactNode;
  iconTint?: string;
  title: string;
  subtitle?: string;
}

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
