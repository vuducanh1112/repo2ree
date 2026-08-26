import styles from "./CanvasControls.module.css";

export function CanvasControls({
  onZoomIn,
  onZoomOut,
  onFit,
  onResetLayout,
  layoutIsDefault,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onResetLayout: () => void;
  /** Whether the panels are still where the ring puts them. */
  layoutIsDefault: boolean;
}) {
  return (
    <div data-canvas-hud className={styles.controls}>
      <button type="button" title="Zoom in" onClick={onZoomIn} className={styles.button}>
        +
      </button>
      <button type="button" title="Zoom out" onClick={onZoomOut} className={styles.button}>
        −
      </button>
      <button
        type="button"
        title="Fit view"
        aria-label="Fit canvas to viewport"
        onClick={onFit}
        className={styles.button}
        data-glyph="reset"
      >
        ⤢
      </button>
      {/* Deliberately always enabled. This is the way back from an arrangement
       * someone regrets, and a disabled escape hatch is worse than a click
       * that turns out to have been unnecessary. `data-arranged` only marks
       * that there is something to undo. */}
      <button
        type="button"
        title="Reset panel layout"
        aria-label="Reset panel layout to default"
        onClick={onResetLayout}
        className={styles.button}
        data-glyph="layout"
        data-arranged={!layoutIsDefault || undefined}
      >
        ⌂
      </button>
    </div>
  );
}
