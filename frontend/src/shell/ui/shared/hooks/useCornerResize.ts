import { useRef, useState } from "react";

interface CornerResizeOptions {
  defaultWidth: number;
  defaultHeight: number;
  minWidth: number;
  minHeight: number;
  /** Margin kept between the panel and the viewport edges when clamping. */
  viewportMargin?: number;
}

/**
 * Drag-to-resize for a corner grip on a panel anchored at its bottom-right:
 * dragging the top-left grip away from the anchor grows the panel. Sizes are
 * clamped to [min, viewport - margin] on every move, so a drag can never push
 * the panel off screen. Session-scoped state — nothing is persisted.
 */
export function useCornerResize({
  defaultWidth,
  defaultHeight,
  minWidth,
  minHeight,
  viewportMargin = 120,
}: CornerResizeOptions) {
  const [size, setSize] = useState({ width: defaultWidth, height: defaultHeight });
  // Grip drags must not animate: width transitions would make the panel lag
  // behind the cursor, so the consumer disables them while this is true.
  const [resizing, setResizing] = useState(false);
  const drag = useRef<{ sx: number; sy: number; w0: number; h0: number } | null>(null);

  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    drag.current = { sx: e.clientX, sy: e.clientY, w0: size.width, h0: size.height };
    setResizing(true);
    const onMove = (ev: MouseEvent) => {
      const d = drag.current;
      if (!d) return;
      const maxWidth = Math.max(minWidth, window.innerWidth - viewportMargin);
      const maxHeight = Math.max(minHeight, window.innerHeight - viewportMargin);
      setSize({
        width: Math.min(maxWidth, Math.max(minWidth, d.w0 + (d.sx - ev.clientX))),
        height: Math.min(maxHeight, Math.max(minHeight, d.h0 + (d.sy - ev.clientY))),
      });
    };
    const onUp = () => {
      drag.current = null;
      setResizing(false);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return { size, resizing, startResize };
}
