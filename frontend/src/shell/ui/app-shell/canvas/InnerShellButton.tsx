import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { F } from "../../theme/theme";

// The inner shell is the execution substrate, themed cyan like the runtime pages.
const RUNTIME_COLOR = "#0891b2";
const RUNTIME_SHADOW = "#164e63";

// Mirrors CoreExperiments' CoreOverviewButton: the inner-shell pod is just a
// graphic, so this is a transparent hit area over it that opens the Runtime
// environment page. Hovering it reports up so the parent can make the pod shine
// and pops a label.
export function InnerShellButton({
  center,
  podDiameter,
  wasNodeDragged,
  onHoverChange,
  onOpenRuntime,
}: {
  /** World position of the inner column's pod centre. */
  center: { x: number; y: number };
  /** Diameter of the inner pod in world units — sizes the clickable hit area. */
  podDiameter: number;
  wasNodeDragged: React.RefObject<boolean>;
  onHoverChange: (hovered: boolean) => void;
  onOpenRuntime: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const setHover = (next: boolean) => {
    setHovered(next);
    onHoverChange(next);
  };
  // World-unit type sizing: scaled down with the inner column, so it's generous
  // here to stay legible.
  const label = Math.round(podDiameter * 0.11);
  return (
    <button
      type="button"
      data-canvas-node
      aria-label="Open runtime environment"
      title="Open the runtime environment"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      onClick={() => {
        if (wasNodeDragged.current) return;
        onOpenRuntime();
      }}
      style={{
        position: "absolute",
        left: center.x,
        top: center.y,
        width: podDiameter,
        height: podDiameter,
        transform: "translate(-50%,-50%)",
        borderRadius: "50%",
        border: "none",
        background: "transparent",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          position: "absolute",
          left: "50%",
          top: "100%",
          transform: "translate(-50%, 14px)",
          display: "inline-flex",
          alignItems: "center",
          gap: label * 0.4,
          whiteSpace: "nowrap",
          padding: `${label * 0.45}px ${label * 0.9}px`,
          borderRadius: 999,
          background: RUNTIME_COLOR,
          color: "#fff",
          fontFamily: F.sans,
          fontWeight: 700,
          fontSize: label,
          boxShadow: `0 ${label * 0.3}px ${label}px ${RUNTIME_SHADOW}55`,
          opacity: hovered ? 1 : 0,
          transition: "opacity 0.15s",
          pointerEvents: "none",
        }}
      >
        {Ic.cpu(label)} Open runtime
      </span>
    </button>
  );
}
