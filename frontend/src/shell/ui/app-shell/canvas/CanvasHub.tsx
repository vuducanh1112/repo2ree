import { useRef } from "react";
import type { Badges } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../core/review/axes";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { C, F } from "../../theme/theme";
import { CableOverlaySvg } from "../pages/overview/PanelCableOverlaySections";
import { PodWidget } from "../pages/overview/PodWidget";
import type { AppShellPage } from "../state/pages";
import { BenchConsole } from "./BenchConsole";
import {
  CANVAS_NODES,
  type CanvasNode,
  isNodeActive,
  isNodeDone,
  isNodeLocked,
  lifecycleProgress,
  nodeSummary,
  type SummaryRow,
} from "./canvasNodes";
import { useCableGeometry } from "./useCableGeometry";
import { useCanvasViewport } from "./useCanvasViewport";

const DONE = "#10b981";

interface CanvasHubProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  evaluation: EvaluationState;
  badges: Badges;
  provisioned: boolean;
  dimmed: boolean;
  onNavigate: (page: AppShellPage) => void;
}

export function CanvasHub({
  page,
  ree,
  evaluation,
  badges,
  provisioned,
  dimmed,
  onNavigate,
}: CanvasHubProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});

  const {
    tf,
    animate,
    nodeOffsets,
    wasNodeDragged,
    isPanning,
    startPan,
    startNodeDrag,
    resetView,
    zoomBy,
  } = useCanvasViewport(stageRef);

  const geo = useCableGeometry({
    stageRef,
    podSvgRef,
    worldRef,
    nodeEls,
    ree,
    badges,
    tf,
    nodeOffsets,
    animate,
  });

  const { completed, total } = lifecycleProgress(ree, badges);
  const ready = completed >= total;
  const levelMeta = standingMeta(evaluation);

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: pannable canvas surface; nodes inside are buttons
    <div
      ref={stageRef}
      onMouseDown={startPan}
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        cursor: isPanning ? "grabbing" : "grab",
        opacity: dimmed ? 0.4 : 1,
        transition: "opacity 0.3s",
        background: `
          radial-gradient(circle at 50% 46%, #ffffff 0%, ${C.bg} 60%),
          linear-gradient(${C.border} 1px, transparent 1px) 0 0 / 26px 26px,
          linear-gradient(90deg, ${C.border} 1px, transparent 1px) 0 0 / 26px 26px`,
      }}
    >
      {geo && <CableOverlaySvg geo={geo} levelMeta={levelMeta} />}

      <div
        ref={worldRef}
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          transformOrigin: "0 0",
          transform: `translate(${tf.x}px, ${tf.y}px) scale(${tf.z})`,
          transition: animate ? "transform 0.4s cubic-bezier(0.4,0,0.2,1)" : "none",
        }}
      >
        {/* cradle socket: the pod is seated in the bench, not floating */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 96,
            width: 320,
            height: 96,
            transform: "translate(-50%,-50%)",
            borderRadius: "50%",
            background:
              "radial-gradient(ellipse at center, rgba(100,116,139,0.14) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />
        <div style={{ position: "absolute", left: 0, top: 0, transform: "translate(-50%,-50%)" }}>
          <PodWidget evaluation={evaluation} svgRef={podSvgRef} size={380} />
        </div>

        <nav aria-label="Workspace pages">
          {CANVAS_NODES.map((node) => {
            const off = nodeOffsets[node.key] ?? { x: 0, y: 0 };
            return (
              <NodeCard
                key={node.key}
                node={node}
                offsetX={off.x}
                offsetY={off.y}
                setRef={(el) => {
                  nodeEls.current[node.key] = el;
                }}
                done={isNodeDone(node, ree, badges)}
                locked={isNodeLocked(node, provisioned)}
                active={isNodeActive(node, page)}
                rows={nodeSummary(node, ree)}
                onNavigate={onNavigate}
                onStartDrag={startNodeDrag}
                wasNodeDragged={wasNodeDragged}
              />
            );
          })}
        </nav>
      </div>

      <div
        style={{
          position: "absolute",
          top: 16,
          left: "50%",
          transform: "translateX(-50%)",
          fontFamily: F.mono,
          fontSize: 11.5,
          color: ready ? DONE : C.textMid,
          background: "rgba(255,255,255,0.8)",
          border: `1px solid ${C.border}`,
          borderRadius: 99,
          padding: "6px 14px",
          backdropFilter: "blur(4px)",
        }}
      >
        {ready ? (
          <b style={{ color: DONE }}>● archive-ready</b>
        ) : (
          <>
            <b style={{ color: C.text }}>{completed}</b>
            <span style={{ color: C.textMuted }}> / {total} stages connected</span>
          </>
        )}
      </div>

      <BenchConsole provisioned={provisioned} reeName={ree.name} />

      <CanvasControls
        onZoomIn={() => zoomBy(1.2)}
        onZoomOut={() => zoomBy(1 / 1.2)}
        onReset={resetView}
      />
    </div>
  );
}

interface NodeCardProps {
  node: CanvasNode;
  offsetX: number;
  offsetY: number;
  setRef: (el: HTMLButtonElement | null) => void;
  done: boolean;
  locked: boolean;
  active: boolean;
  rows: SummaryRow[];
  onNavigate: (page: AppShellPage) => void;
  onStartDrag: (key: string, sx: number, sy: number) => void;
  wasNodeDragged: React.RefObject<boolean>;
}

function NodeCard({
  node,
  offsetX,
  offsetY,
  setRef,
  done,
  locked,
  active,
  rows,
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
      onClick={() => {
        if (wasNodeDragged.current) return;
        onNavigate(node.key);
      }}
      style={{
        position: "absolute",
        left: node.x + offsetX,
        top: node.y + offsetY,
        transform: "translate(-50%,-50%)",
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
        transition: "box-shadow 0.15s, border-color 0.15s, opacity 0.35s",
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
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 8,
              letterSpacing: 1,
              color: C.textMuted,
              textTransform: "uppercase",
            }}
          >
            {node.kind}
          </div>
        </div>
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            flexShrink: 0,
            background: done ? DONE : C.borderMid,
            boxShadow: done ? `0 0 7px ${DONE}88` : "none",
          }}
        />
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

function CanvasControls({
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
