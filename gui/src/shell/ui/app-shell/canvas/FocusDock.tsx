import type { CanvasNode } from "@core/canvas/canvasNodes";
import type { ReactNode } from "react";
import { C, F } from "../../theme/theme";
import { CanvasWindow } from "./CanvasWindow";
import { canvasIcon } from "./canvasIcons";

interface FocusDockProps {
  node: CanvasNode | undefined;
  /** Screen rect of the canvas panel that was clicked, so the view grows out of it. */
  originRect: DOMRect | null;
  /** Whether the dock can be dismissed (false while the workbench is unprovisioned). */
  closable: boolean;
  onClose: () => void;
  children: ReactNode;
}

// The enlarged panel sits below the header, inset from the canvas edges so the
// constellation stays visible around it. The panel is position:fixed, so TOP and
// SIDE are measured from the viewport — which is also why transformOrigin below
// subtracts exactly these to map the clicked panel's rect into the panel's box.
const HEADER = 48; // app header height; the dimming backdrop starts just below it
const TOP = 60; // panel top edge, in viewport px
const BOTTOM = 24; // gap from the viewport bottom
const SIDE_FRAC = 0.07; // panel inset from each side, as a fraction of viewport width
const SIDE = `${SIDE_FRAC * 100}%`;

export function FocusDock({ node, originRect, closable, onClose, children }: FocusDockProps) {
  // Anchor the grow animation on the clicked panel's centre. transform-origin is
  // relative to the panel's own box, so subtract the panel's top-left corner.
  const sidePx = window.innerWidth * SIDE_FRAC;
  const transformOrigin = originRect
    ? `${originRect.left + originRect.width / 2 - sidePx}px ${
        originRect.top + originRect.height / 2 - TOP
      }px`
    : "center";

  return (
    <div style={{ position: "fixed", top: HEADER, left: 0, right: 0, bottom: 0, zIndex: 90 }}>
      <button
        type="button"
        aria-label="Back to constellation"
        onClick={() => closable && onClose()}
        style={{
          position: "absolute",
          inset: 0,
          border: "none",
          background: "rgba(225,230,238,0.45)",
          cursor: closable ? "pointer" : "default",
        }}
      />

      <CanvasWindow
        ariaLabel={node?.label ?? "Step page"}
        onClose={onClose}
        closable={closable}
        escapeToClose
        header={
          node && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontFamily: F.mono,
                fontSize: 11,
                letterSpacing: 0.4,
                textTransform: "uppercase",
                color: C.textMuted,
              }}
            >
              <span style={{ display: "flex", color: node.color }}>
                {canvasIcon(node.iconKey)(13)}
              </span>
              {node.label}
            </span>
          )
        }
        outerStyle={{
          position: "fixed",
          top: TOP,
          left: SIDE,
          right: SIDE,
          bottom: BOTTOM,
          borderRadius: 16,
          boxShadow: "0 24px 60px rgba(13,17,23,0.22)",
          transformOrigin,
          animation: "growIn 0.4s cubic-bezier(0.34,1.1,0.5,1)",
        }}
      >
        {children}
      </CanvasWindow>
    </div>
  );
}
