import styles from "./CanvasControls.module.css";

export function CanvasControls({
  onZoomIn,
  onZoomOut,
  onReset,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
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
        title="Reset view"
        onClick={onReset}
        className={styles.button}
        data-glyph="reset"
      >
        ⤢
      </button>
    </div>
  );
}
