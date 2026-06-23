import type React from "react";
import { C, F } from "../../theme/theme";
import { StatusDot } from "./StatusDot";

interface HudConsoleProps {
  open: boolean;
  onToggle: () => void;
  widthOpen: number;
  widthCollapsed: number;
  /** Outer positioning + any extra card styles (e.g. display/maxHeight for flex-scrollable bodies). */
  outerStyle: React.CSSProperties;
  icon: React.ReactNode;
  iconColor?: string;
  title: string;
  subtitle?: React.ReactNode;
  /** Drives the StatusDot. */
  on: boolean;
  expandLabel: string;
  collapseLabel: string;
  /** When set, the body uses a maxHeight/opacity transition to this height (px) instead of conditional render. */
  bodyMaxHeight?: number;
  /** Extra style on the body content wrapper (e.g. flex/minHeight for scrollable layouts). */
  bodyStyle?: React.CSSProperties;
  children?: React.ReactNode;
}

// Shared chrome for the pinned HUD consoles (FileTreeConsole, BenchConsole): the
// frosted card, the expand/collapse header button, and the collapsible body slot.
export function HudConsole({
  open,
  onToggle,
  widthOpen,
  widthCollapsed,
  outerStyle,
  icon,
  iconColor = C.textMuted,
  title,
  subtitle,
  on,
  expandLabel,
  collapseLabel,
  bodyMaxHeight,
  bodyStyle,
  children,
}: HudConsoleProps) {
  const body =
    bodyMaxHeight != null ? (
      <div
        style={{
          maxHeight: open ? bodyMaxHeight : 0,
          opacity: open ? 1 : 0,
          overflow: "hidden",
          transition: "max-height 0.28s cubic-bezier(0.4,0,0.2,1), opacity 0.2s",
        }}
      >
        <div
          style={{
            padding: "2px 12px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 7,
            borderTop: `1px solid ${C.border}`,
            ...bodyStyle,
          }}
        >
          {children}
        </div>
      </div>
    ) : open ? (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          borderTop: `1px solid ${C.border}`,
          ...bodyStyle,
        }}
      >
        {children}
      </div>
    ) : null;

  return (
    <div
      data-canvas-hud
      style={{
        position: "absolute",
        width: open ? widthOpen : widthCollapsed,
        background: "rgba(255,255,255,0.92)",
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        boxShadow: open ? "0 18px 48px rgba(13,17,23,0.16)" : "0 4px 14px rgba(13,17,23,0.08)",
        backdropFilter: "blur(4px)",
        overflow: "hidden",
        transition: "width 0.26s cubic-bezier(0.4,0,0.2,1), box-shadow 0.26s",
        ...outerStyle,
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-label={open ? collapseLabel : expandLabel}
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          width: "100%",
          padding: "9px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          flexShrink: 0,
        }}
      >
        <span style={{ color: iconColor, display: "flex" }}>{icon}</span>
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            lineHeight: 1.3,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 650, color: C.text }}>{title}</span>
          {subtitle ? (
            <span
              style={{
                fontFamily: F.mono,
                fontSize: 9.5,
                color: C.textMuted,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {subtitle}
            </span>
          ) : null}
        </div>
        <StatusDot on={on} />
        <span
          style={{
            display: "flex",
            color: C.textMuted,
            flexShrink: 0,
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform 0.26s",
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <title>toggle</title>
            <path
              d="M6 15l6-6 6 6"
              stroke="currentColor"
              strokeWidth="2.2"
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
