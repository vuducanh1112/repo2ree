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
  const drag = useRef<{
    pointerId: number;
    sx: number;
    sy: number;
    w0: number;
    h0: number;
  } | null>(null);

  const startResize = (e: React.PointerEvent) => {
    if (!e.isPrimary || e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    drag.current = {
      pointerId: e.pointerId,
      sx: e.clientX,
      sy: e.clientY,
      w0: size.width,
      h0: size.height,
    };
    setResizing(true);
    const onMove = (ev: PointerEvent) => {
      const d = drag.current;
      if (!d || ev.pointerId !== d.pointerId) return;
      const maxWidth = Math.max(minWidth, window.innerWidth - viewportMargin);
      const maxHeight = Math.max(minHeight, window.innerHeight - viewportMargin);
      setSize({
        width: Math.min(maxWidth, Math.max(minWidth, d.w0 + (d.sx - ev.clientX))),
        height: Math.min(maxHeight, Math.max(minHeight, d.h0 + (d.sy - ev.clientY))),
      });
    };
    const onUp = (ev: PointerEvent) => {
      if (drag.current && ev.pointerId !== drag.current.pointerId) return;
      drag.current = null;
      setResizing(false);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  };

  return { size, resizing, startResize };
}
