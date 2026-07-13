import { type CSSProperties, type ReactNode, useEffect } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";

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
  /** Position, size, and entry animation — the caller owns placement. */
  outerStyle?: CSSProperties;
  /** True to let the frame scroll the body; false when children scroll themselves. */
  scrollBody?: boolean;
  bodyStyle?: CSSProperties;
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
  outerStyle,
  scrollBody = false,
  bodyStyle,
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
      style={{
        display: "flex",
        flexDirection: "column",
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 14,
        overflow: "hidden",
        boxShadow: "0 24px 60px rgba(13,17,23,0.2)",
        ...outerStyle,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexShrink: 0,
          minHeight: 40,
          padding: "0 8px 0 14px",
          borderBottom: `1px solid ${C.border}`,
          background: C.surfaceAlt,
        }}
      >
        <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 8 }}>
          {header}
        </div>
        {headerRight}
        {closable && (
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              flexShrink: 0,
              border: "none",
              borderRadius: 7,
              background: "transparent",
              color: C.textMuted,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {Ic.x(14)}
          </button>
        )}
      </div>

      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
          overflowY: scrollBody ? "auto" : "hidden",
          ...bodyStyle,
        }}
      >
        {children}
      </div>
    </section>
  );
}

interface CanvasWindowTitleProps {
  /** Accent-coloured leading icon, e.g. `Ic.package(16)`. */
  icon?: ReactNode;
  iconColor?: string;
  title: string;
  subtitle?: string;
}

/** The standard single-line title-bar content: icon, bold title, mono subtitle. */
export function CanvasWindowTitle({ icon, iconColor, title, subtitle }: CanvasWindowTitleProps) {
  return (
    <>
      {icon && <span style={{ color: iconColor, display: "flex", flexShrink: 0 }}>{icon}</span>}
      <span
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: C.text,
          letterSpacing: -0.2,
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        {title}
      </span>
      {subtitle && (
        <span
          style={{
            fontSize: 11,
            fontFamily: F.mono,
            color: C.textMuted,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {subtitle}
        </span>
      )}
    </>
  );
}
