import { type ReactNode, useEffect } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import type { CanvasNode } from "./canvasNodes";

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
  useEffect(() => {
    if (!closable) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closable, onClose]);

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

      <div
        style={{
          position: "fixed",
          top: TOP,
          left: SIDE,
          right: SIDE,
          bottom: BOTTOM,
          display: "flex",
          minWidth: 0,
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 16,
          overflow: "hidden",
          boxShadow: "0 24px 60px rgba(13,17,23,0.22)",
          transformOrigin,
          animation: "growIn 0.4s cubic-bezier(0.34,1.1,0.5,1)",
        }}
      >
        {node && (
          <div
            style={{
              position: "absolute",
              top: 14,
              left: 18,
              zIndex: 2,
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontFamily: F.mono,
              fontSize: 11,
              letterSpacing: 0.4,
              textTransform: "uppercase",
              color: C.textMuted,
              pointerEvents: "none",
            }}
          >
            <span style={{ display: "flex", color: node.color }}>{node.icon(13)}</span>
            {node.label}
          </div>
        )}
        {closable && (
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              position: "absolute",
              top: 12,
              right: 12,
              zIndex: 2,
              width: 30,
              height: 30,
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
            {Ic.x(15)}
          </button>
        )}
        {children}
      </div>
    </div>
  );
}
