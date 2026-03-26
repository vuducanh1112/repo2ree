import type React from "react";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverIf,
  S_ACTION_BUTTON_BASE,
} from "../../constants/theme";

interface NavEntryButtonProps {
  isActive: boolean;
  navCollapsed: boolean;
  title?: string;
  onClick: () => void;
  children: React.ReactNode;
}

export function NavEntryButton({
  isActive,
  navCollapsed,
  title,
  onClick,
  children,
}: NavEntryButtonProps) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: navCollapsed ? 0 : 9,
        padding: navCollapsed ? "8px 0" : "8px 10px",
        justifyContent: navCollapsed ? "center" : "flex-start",
        borderRadius: 7,
        border: "none",
        cursor: "pointer",
        width: "100%",
        background: isActive ? C.accentBg : "transparent",
        borderLeft: !navCollapsed && isActive ? `2px solid ${C.accent}` : "2px solid transparent",
        transition: "all 0.12s",
        textAlign: "left",
      }}
      {...hoverIf(!isActive, hoverBg(C.surfaceAlt, "transparent"))}
    >
      {children}
    </button>
  );
}

interface ActionBtnProps {
  title: string;
  label: string;
  subtitle: string;
  icon: React.ReactNode;
  iconBg: string;
  labelColor: string;
  subtitleColor: string;
  background: string;
  border: string;
  hoverBackground: string;
  hoverBorder: string;
  navCollapsed: boolean;
  onClick: () => void;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function ActionBtn({
  title,
  label,
  subtitle,
  icon,
  iconBg,
  labelColor,
  subtitleColor,
  background,
  border,
  hoverBackground,
  hoverBorder,
  navCollapsed,
  onClick,
}: ActionBtnProps) {
  return (
    <button
      type="button"
      title={navCollapsed ? title : undefined}
      onClick={onClick}
      style={{
        ...actionBtn({
          padding: navCollapsed ? "8px 0" : "9px 10px",
          background,
          border: `1.5px solid ${border}`,
        }),
        display: "flex",
        alignItems: "center",
        gap: navCollapsed ? 0 : 9,
        justifyContent: navCollapsed ? "center" : "flex-start",
        width: "100%",
        cursor: "pointer",
      }}
      {...hoverBg(hoverBackground, background)}
      {...hoverBorderColor(hoverBorder, border)}
    >
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: 6,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: iconBg,
          border: "none",
        }}
      >
        <span style={{ display: "flex", color: "#fff" }}>{icon}</span>
      </div>
      {!navCollapsed && (
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 13,
              fontFamily: F.sans,
              fontWeight: 700,
              color: labelColor,
              whiteSpace: "nowrap",
            }}
          >
            {label}
          </div>
          <div style={{ fontSize: 10, color: subtitleColor, fontFamily: F.sans, marginTop: 1 }}>
            {subtitle}
          </div>
        </div>
      )}
    </button>
  );
}
