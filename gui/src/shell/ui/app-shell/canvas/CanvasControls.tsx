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
