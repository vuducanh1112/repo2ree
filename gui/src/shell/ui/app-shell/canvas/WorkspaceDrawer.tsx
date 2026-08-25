import type { CanvasNode } from "@core/canvas/canvasNodes";
import {
  type KeyboardEvent,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { CanvasWindow, CanvasWindowTitle } from "./CanvasWindow";
import { canvasIcon } from "./canvasIcons";
import styles from "./WorkspaceDrawer.module.css";

interface WorkspaceDrawerProps {
  node: CanvasNode | undefined;
  /** Optional longer page title when the canvas node uses a compact label. */
  title?: string;
  onClose: () => void;
  children: ReactNode;
}

const DEFAULT_WIDTH = 760;
const MIN_WIDTH = 440;
const VIEWPORT_MARGIN = 24;
const KEYBOARD_STEP = 24;

function clampWidth(width: number) {
  const viewportWidth = Math.max(MIN_WIDTH, window.innerWidth - VIEWPORT_MARGIN);
  return Math.min(viewportWidth, Math.max(MIN_WIDTH, width));
}

/**
 * A persistent, non-modal page surface over the right side of the canvas.
 * Unlike a modal surface it keeps the constellation visible and interactive, making
 * it useful for short authoring forms that benefit from spatial context.
 */
export function WorkspaceDrawer({ node, title, onClose, children }: WorkspaceDrawerProps) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [resizing, setResizing] = useState(false);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const startResize = useCallback(
    (event: ReactPointerEvent<HTMLHRElement>) => {
      if (!event.isPrimary || event.button !== 0) return;
      event.preventDefault();
      dragRef.current = { startX: event.clientX, startWidth: width };
      setResizing(true);
    },
    [width],
  );

  useEffect(() => {
    if (!resizing) return;

    const move = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      setWidth(clampWidth(drag.startWidth + drag.startX - event.clientX));
    };
    const stop = () => {
      dragRef.current = null;
      setResizing(false);
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, [resizing]);

  const resizeWithKeyboard = (event: KeyboardEvent<HTMLHRElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setWidth((current) =>
      clampWidth(current + (event.key === "ArrowLeft" ? KEYBOARD_STEP : -KEYBOARD_STEP)),
    );
  };

  return (
    <div
      className={styles.host}
      data-canvas-hud
      data-resizing={resizing || undefined}
      style={cssVars({ "--drawer-width": `${width}px` })}
    >
      <hr
        aria-label={`Resize ${title ?? node?.label ?? "workspace"} panel`}
        aria-orientation="vertical"
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={Math.max(MIN_WIDTH, window.innerWidth - VIEWPORT_MARGIN)}
        aria-valuenow={width}
        tabIndex={0}
        className={styles.resizeRail}
        onPointerDown={startResize}
        onKeyDown={resizeWithKeyboard}
      />

      <CanvasWindow
        ariaLabel={title ?? node?.label ?? "Workspace page"}
        onClose={onClose}
        escapeToClose
        className={styles.drawer}
        header={
          <CanvasWindowTitle
            icon={node ? canvasIcon(node.iconKey)(13) : undefined}
            iconTint={node ? stageTone(node.key) : undefined}
            title={title ?? node?.label ?? "Workspace"}
            subtitle="Authoring"
          />
        }
      >
        {children}
      </CanvasWindow>
    </div>
  );
}
