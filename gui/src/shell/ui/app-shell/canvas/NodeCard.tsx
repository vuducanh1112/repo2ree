import type React from "react";
import { C, F } from "../../theme/theme";
import type { AppShellPage } from "../state/pages";
import type { CanvasNode, NodeProjection, SummaryRow } from "./canvasNodes";
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
  onStartDrag: (key: string, sx: number, sy: number) => void;
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
      onMouseDown={(e) => {
        if (!locked) onStartDrag(node.key, e.clientX, e.clientY);
      }}
      onClick={(e) => {
        if (wasNodeDragged.current) return;
        onNavigate(node.key, e.currentTarget.getBoundingClientRect());
      }}
      style={{
        position: "absolute",
        left: node.x + offsetX,
        top: node.y + offsetY,
        transform: `translate(-50%,-50%) translate(${projection.dx}px,${projection.dy}px) scale(${projection.scale})`,
        width: 176,
        textAlign: "left",
        background: C.surface,
        border: active ? `1px solid ${C.accent}` : `1px solid ${done ? "#bbf0d8" : C.border}`,
        borderRadius: 13,
        padding: "11px 13px",
        cursor: locked ? "default" : "pointer",
        opacity: locked ? 0.34 : 1,
        boxShadow: active
          ? `0 0 0 3px ${C.accentBg}, 0 10px 28px rgba(37,99,235,0.22)`
          : "0 4px 16px rgba(13,17,23,0.07)",
        transition:
          "transform 0.4s cubic-bezier(0.4,0,0.2,1), box-shadow 0.15s, border-color 0.15s, opacity 0.35s",
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: rows.length ? 9 : 0 }}
      >
        <span
          style={{
            width: 26,
            height: 26,
            borderRadius: 7,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: done ? "#e7f9f1" : C.surfaceAlt,
            border: `1px solid ${done ? "#bbf0d8" : C.border}`,
            color: done ? node.color : C.textMuted,
          }}
        >
          {node.icon(14)}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 650, color: C.text, letterSpacing: -0.1 }}>
            {node.label}
          </div>
        </div>
        <StatusDot on={done} stale={stale} />
      </div>

      {rows.map((row) => (
        <div
          key={row.label}
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 8,
            padding: "2px 0",
            fontFamily: F.mono,
            fontSize: 10.5,
          }}
        >
          <span style={{ color: C.textMuted }}>{row.label}</span>
          <span
            title={row.title}
            style={{
              color: row.value ? C.textMid : C.borderMid,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              maxWidth: 104,
            }}
          >
            {row.value ?? "—"}
          </span>
        </div>
      ))}
    </button>
  );
}
