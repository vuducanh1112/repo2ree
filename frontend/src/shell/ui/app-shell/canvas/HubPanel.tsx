import type { CSSProperties, ReactNode } from "react";
import { CanvasWindow } from "./CanvasWindow";

interface HubPanelProps {
  /** Accessible region name; tests select the panel by this (role=region). */
  ariaLabel: string;
  onClose: () => void;
  /** Max panel width in px (clamped to the viewport). */
  width?: number;
  /** Cross-axis alignment of children (Seal centres its content). */
  align?: CSSProperties["alignItems"];
  /** Title-bar content, usually a `CanvasWindowTitle`. */
  header: ReactNode;
  /** Trailing title-bar slot (run button, status badge, …) before the X. */
  headerRight?: ReactNode;
  children: ReactNode;
}

/**
 * The floating glass panel docked at the bottom of the constellation hub
 * (Source, SBOM, Seal): a CanvasWindow with the hub's placement — bottom
 * centre, translucent, dock-in animation. The frame owns the title bar,
 * pinned X, Escape-to-close, and body scrolling.
 */
export function HubPanel({
  ariaLabel,
  onClose,
  width = 460,
  align,
  header,
  headerRight,
  children,
}: HubPanelProps) {
  return (
    <CanvasWindow
      ariaLabel={ariaLabel}
      onClose={onClose}
      escapeToClose
      header={header}
      headerRight={headerRight}
      scrollBody
      outerStyle={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 20,
        margin: "0 auto",
        zIndex: 20,
        width: `min(${width}px, calc(100% - 32px))`,
        maxHeight: "calc(100% - 88px)",
        background: "rgba(255,255,255,0.82)",
        borderRadius: 16,
        backdropFilter: "blur(8px)",
        boxShadow: "0 18px 44px rgba(13,17,23,0.16)",
        animation: "dockIn 0.3s cubic-bezier(0.4,0,0.2,1)",
      }}
      bodyStyle={{ alignItems: align, gap: 12, padding: "14px 18px 18px" }}
    >
      {children}
    </CanvasWindow>
  );
}
