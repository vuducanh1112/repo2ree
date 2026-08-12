import type { CSSProperties, ReactNode } from "react";
import { CanvasWindow } from "./CanvasWindow";
import styles from "./HubPanel.module.css";

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
      className={styles.panel}
      bodyClassName={styles.body}
      vars={{
        "--hub-panel-width": `${width}px`,
        "--hub-panel-align": typeof align === "string" ? align : undefined,
      }}
    >
      {children}
    </CanvasWindow>
  );
}
