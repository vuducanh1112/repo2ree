import type { Point } from "@core/canvas/cableGeometry";
import type { CanvasNode } from "@core/canvas/canvasNodes";
import { DEFAULT_WINDOW_SIZE, type WindowSize } from "@core/canvas/nodeWindowPlacement";
import { type ReactNode, type PointerEvent as ReactPointerEvent, useEffect, useRef } from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import styles from "./CanvasPageWindow.module.css";
import { CanvasWindow, CanvasWindowTitle } from "./CanvasWindow";
import { canvasIcon } from "./canvasIcons";

/**
 * One page, in a window standing at a place on the canvas beside its node.
 *
 * The window lives in the untransformed stage layer, not in the tilted 3D floor
 * the node cards sit on: it never rotates, never takes the floor's perspective
 * projection and never scales with zoom, so page text stays at 100% and
 * `position: fixed` inside a page still means fixed. What it does take from the
 * canvas is its *place* — the caller hands it a screen position derived from a
 * stored camera-local point, so panning carries the window off the stage and
 * back exactly like anything else standing on the canvas.
 */
interface CanvasPageWindowProps {
  node: CanvasNode | undefined;
  /** Longer title when the node's own label is a compact one. */
  title?: string;
  subtitle: string;
  /** Where the whole open set decided this window goes, in stage space. */
  position: Point;
  size?: WindowSize;
  /** Position in the open order, which sets the resting stacking order. */
  depth: number;
  focused: boolean;
  onFocus: () => void;
  onClose: () => void;
  /** Screen-space drag deltas from the title bar, for the caller to store. */
  onMove: (delta: Point) => void;
  /** Screen-space resize deltas from the bottom-right handle. */
  onResize: (delta: Point) => void;
  children: ReactNode;
}

export function CanvasPageWindow({
  node,
  title,
  subtitle,
  position,
  size = DEFAULT_WINDOW_SIZE,
  depth,
  focused,
  onFocus,
  onClose,
  onMove,
  onResize,
  children,
}: CanvasPageWindowProps) {
  const drag = useRef<{
    kind: "move" | "resize";
    pointerId: number;
    x: number;
    y: number;
  } | null>(null);
  // The move handler changes every render as the window moves; a ref keeps the
  // window-level listeners from being torn down and rebuilt mid-drag.
  const onMoveRef = useRef(onMove);
  onMoveRef.current = onMove;
  const onResizeRef = useRef(onResize);
  onResizeRef.current = onResize;

  useEffect(() => {
    const move = (event: PointerEvent) => {
      const active = drag.current;
      if (!active || event.pointerId !== active.pointerId) return;
      const delta = { x: event.clientX - active.x, y: event.clientY - active.y };
      if (active.kind === "move") onMoveRef.current(delta);
      else onResizeRef.current(delta);
      drag.current = { ...active, x: event.clientX, y: event.clientY };
    };
    const stop = (event: PointerEvent) => {
      if (drag.current?.pointerId === event.pointerId) drag.current = null;
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, []);

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary || event.button !== 0) return;
    // The bar also carries the title and the close button; only its bare strip
    // is the handle, so a press on a control is not a drag.
    if (event.target !== event.currentTarget) return;
    event.preventDefault();
    drag.current = {
      kind: "move",
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };
  };

  const startResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!event.isPrimary || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    drag.current = {
      kind: "resize",
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };
  };

  return (
    // Focus on the way down so it lands before anything inside the window
    // handles the same press, and on capture so a click anywhere counts.
    <div
      className={styles.host}
      data-focused={focused || undefined}
      onPointerDownCapture={onFocus}
      style={cssVars({
        "--window-x": `${position.x}px`,
        "--window-y": `${position.y}px`,
        "--window-w": `${size.width}px`,
        "--window-h": `${size.height}px`,
        "--window-depth": depth,
      })}
    >
      <CanvasWindow
        ariaLabel={title ?? node?.label ?? "Workspace page"}
        onClose={onClose}
        // Only the window on top answers Escape; otherwise one press would
        // close every open window at once.
        escapeToClose={focused}
        onBarPointerDown={startDrag}
        className={styles.window}
        headerRight={
          <button
            type="button"
            aria-label={`Resize ${title ?? node?.label ?? "workspace page"}`}
            className={styles.resizeHandle}
            onPointerDown={startResize}
          />
        }
        header={
          <CanvasWindowTitle
            icon={node ? canvasIcon(node.iconKey)(13) : undefined}
            iconTint={node ? stageTone(node.key) : undefined}
            title={title ?? node?.label ?? "Workspace"}
            subtitle={subtitle}
          />
        }
      >
        {children}
      </CanvasWindow>
    </div>
  );
}
