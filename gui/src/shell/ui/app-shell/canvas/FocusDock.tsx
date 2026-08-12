import type { CanvasNode } from "@core/canvas/canvasNodes";
import type { ReactNode } from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { CanvasWindow } from "./CanvasWindow";
import { canvasIcon } from "./canvasIcons";
import styles from "./FocusDock.module.css";

interface FocusDockProps {
  node: CanvasNode | undefined;
  /** Screen rect of the canvas panel that was clicked, so the view grows out of it. */
  originRect: DOMRect | null;
  /** Whether the dock can be dismissed (false while the workbench is unprovisioned). */
  closable: boolean;
  onClose: () => void;
  children: ReactNode;
}

// The panel is position:fixed, so these are measured from the viewport — which
// is also why transformOrigin below subtracts exactly them to map the clicked
// panel's rect into the panel's own box. They mirror FocusDock.module.css.
const TOP = 60; // panel top edge, in viewport px
const SIDE_FRAC = 0.07; // panel inset from each side, as a fraction of viewport width

export function FocusDock({ node, originRect, closable, onClose, children }: FocusDockProps) {
  // Anchor the grow animation on the clicked panel's centre. transform-origin is
  // relative to the panel's own box, so subtract the panel's top-left corner.
  const sidePx = window.innerWidth * SIDE_FRAC;
  const focusOrigin = originRect
    ? `${originRect.left + originRect.width / 2 - sidePx}px ${
        originRect.top + originRect.height / 2 - TOP
      }px`
    : "center";

  return (
    <div className={styles.overlay}>
      <button
        type="button"
        aria-label="Back to constellation"
        onClick={() => closable && onClose()}
        disabled={!closable}
        className={styles.scrim}
      />

      <CanvasWindow
        ariaLabel={node?.label ?? "Step page"}
        onClose={onClose}
        closable={closable}
        escapeToClose
        className={styles.dock}
        vars={{ "--focus-origin": focusOrigin }}
        header={
          node && (
            <span className={styles.nodeTitle}>
              <span
                aria-hidden
                className={styles.nodeIcon}
                style={cssVars({ "--node-tint": stageTone(node.key) })}
              >
                {canvasIcon(node.iconKey)(13)}
              </span>
              {node.label}
            </span>
          )
        }
      >
        {children}
      </CanvasWindow>
    </div>
  );
}
