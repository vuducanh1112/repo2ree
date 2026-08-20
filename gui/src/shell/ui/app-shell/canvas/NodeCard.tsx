import type { AppShellPage } from "@core/app-shell/pages";
import type { CanvasNode, NodeProjection, SummaryRow } from "@core/canvas/canvasNodes";
import type React from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { canvasIcon } from "./canvasIcons";
import styles from "./NodeCard.module.css";
import { StatusDot } from "./StatusDot";

interface NodeCardProps {
  node: CanvasNode;
  offsetX: number;
  offsetY: number;
  setRef: (el: HTMLButtonElement | null) => void;
  done: boolean;
  /** Done, but the recorded run's inputs no longer match the workspace. */
  stale?: boolean;
  locked: boolean;
  active: boolean;
  rows: SummaryRow[];
  /** Where the card sits in the decomposed view (identity when assembled). */
  projection: NodeProjection;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
  onStartDrag: (key: string, event: React.PointerEvent) => void;
  wasNodeDragged: React.RefObject<boolean>;
}

export function NodeCard({
  node,
  offsetX,
  offsetY,
  setRef,
  done,
  stale = false,
  locked,
  active,
  rows,
  projection,
  onNavigate,
  onStartDrag,
  wasNodeDragged,
}: NodeCardProps) {
  return (
    <button
      type="button"
      data-canvas-node
      aria-label={node.label}
      ref={setRef}
      disabled={locked}
      onPointerDown={(event) => {
        if (!locked) onStartDrag(node.key, event);
      }}
      onClick={(e) => {
        if (wasNodeDragged.current) return;
        onNavigate(node.key, e.currentTarget.getBoundingClientRect());
      }}
      className={styles.card}
      data-done={done || undefined}
      data-active={active || undefined}
      style={cssVars({
        "--node-x": `${node.x + offsetX}px`,
        "--node-y": `${node.y + offsetY}px`,
        "--node-dx": `${projection.dx}px`,
        "--node-dy": `${projection.dy}px`,
        "--node-scale": projection.scale,
        "--node-tint": stageTone(node.key),
      })}
    >
      <div className={styles.head} data-with-rows={rows.length ? true : undefined}>
        <span aria-hidden className={styles.glyph}>
          {canvasIcon(node.iconKey)(14)}
        </span>
        <div className={styles.titleBox}>
          <div className={styles.title}>{node.label}</div>
        </div>
        <StatusDot on={done} stale={stale} />
      </div>

      {rows.map((row) => (
        <div key={row.label} className={styles.row}>
          <span className={styles.rowLabel}>{row.label}</span>
          <span
            title={row.title}
            className={styles.rowValue}
            data-empty={row.value ? undefined : true}
          >
            {row.value ?? "—"}
          </span>
        </div>
      ))}
    </button>
  );
}
