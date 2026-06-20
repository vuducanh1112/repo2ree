import { type CSSProperties, type ReactNode, useEffect } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";

interface HubPanelProps {
  /** Accessible region name; tests select the panel by this (role=region). */
  ariaLabel: string;
  onClose: () => void;
  /** Max panel width in px (clamped to the viewport). */
  width?: number;
  /** Cross-axis alignment of children (Seal centres its content). */
  align?: CSSProperties["alignItems"];
  children: ReactNode;
}

/**
 * The floating glass panel docked at the bottom of the constellation hub
 * (Source, SBOM, Seal). Owns the shared shell, the dock-in animation, the
 * Escape-to-close handler, and the corner close button so each panel only has
 * to supply its own header + body.
 */
export function HubPanel({ ariaLabel, onClose, width = 460, align, children }: HubPanelProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <section
      aria-label={ariaLabel}
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 20,
        margin: "0 auto",
        zIndex: 20,
        width: `min(${width}px, calc(100% - 32px))`,
        maxHeight: "calc(100% - 88px)",
        display: "flex",
        flexDirection: "column",
        alignItems: align,
        gap: 12,
        overflowY: "auto",
        padding: "16px 18px 18px",
        background: "rgba(255,255,255,0.82)",
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        backdropFilter: "blur(8px)",
        boxShadow: "0 18px 44px rgba(13,17,23,0.16)",
        animation: "dockIn 0.3s cubic-bezier(0.4,0,0.2,1)",
      }}
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          width: 28,
          height: 28,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          background: C.surface,
          color: C.textMuted,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {Ic.x(14)}
      </button>

      {children}
    </section>
  );
}

interface HubPanelHeaderProps {
  /** Accent-coloured leading icon, e.g. `Ic.package(18)`. */
  icon: ReactNode;
  iconColor: string;
  title: string;
  subtitle: string;
  /** Optional trailing slot (run button, status badge, …). */
  right?: ReactNode;
}

/** The shared title row for hub panels: accent icon, title, mono subtitle, and
 * an optional trailing action/status slot. paddingRight clears the close button. */
export function HubPanelHeader({ icon, iconColor, title, subtitle, right }: HubPanelHeaderProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, paddingRight: 40 }}>
      <span style={{ color: iconColor, display: "flex" }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          {title}
        </div>
        <div style={{ fontSize: 11.5, fontFamily: F.mono, color: C.textMuted, marginTop: 2 }}>
          {subtitle}
        </div>
      </div>
      {right}
    </div>
  );
}
