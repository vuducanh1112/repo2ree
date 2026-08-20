import styles from "./CanvasControls.module.css";

export function CanvasControls({
  onZoomIn,
  onZoomOut,
  onFit,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
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
    </div>
  );
}
