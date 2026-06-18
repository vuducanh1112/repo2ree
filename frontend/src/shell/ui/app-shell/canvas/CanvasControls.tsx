import { C } from "../../theme/theme";

export function CanvasControls({
  onZoomIn,
  onZoomOut,
  onReset,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}) {
  const btn: React.CSSProperties = {
    width: 34,
    height: 32,
    border: "none",
    background: C.surface,
    color: C.textMid,
    fontSize: 16,
    cursor: "pointer",
  };
  return (
    <div
      data-canvas-hud
      style={{
        position: "absolute",
        right: 16,
        bottom: 16,
        display: "flex",
        flexDirection: "column",
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
        boxShadow: "0 4px 14px rgba(13,17,23,0.1)",
      }}
    >
      <button type="button" title="Zoom in" onClick={onZoomIn} style={btn}>
        +
      </button>
      <button
        type="button"
        title="Zoom out"
        onClick={onZoomOut}
        style={{ ...btn, borderTop: `1px solid ${C.border}` }}
      >
        −
      </button>
      <button
        type="button"
        title="Reset view"
        onClick={onReset}
        style={{ ...btn, fontSize: 12, borderTop: `1px solid ${C.border}` }}
      >
        ⤢
      </button>
    </div>
  );
}
