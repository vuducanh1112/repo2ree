import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { cssVars } from "../../theme/styleVars";
import styles from "./InnerShellButton.module.css";

// The inner shell is the execution substrate, so it carries the build stage's
// tone — the same one the runtime pages do. InnerShellButton.module.css reads it.

// Mirrors CoreExperiments' CoreOverviewButton: the inner-shell pod is just a
// graphic, so this is a transparent hit area over it that opens the Build
// Runtime page (the inner shell is the build runtime). Hovering it reports up so
// the parent can make the pod shine and pops a label.
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
  const [_hovered, setHovered] = useState(false);
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
      aria-label="Open build runtime"
      title="Open the build runtime"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      onClick={() => {
        if (wasNodeDragged.current) return;
        onOpenRuntime();
      }}
      className={styles.hit}
      style={cssVars({
        "--shell-x": `${center.x}px`,
        "--shell-y": `${center.y}px`,
        "--shell-size": `${podDiameter}px`,
        "--shell-label": label,
      })}
    >
      <span className={styles.label}>{Ic.cpu(label)} Open build runtime</span>
    </button>
  );
}
