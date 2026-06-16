import { useCallback, useEffect, useRef, useState } from "react";
import type { Badges } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../core/review/axes";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { C, F } from "../../theme/theme";
import type { CableGeo } from "../pages/overview/PanelCableOverlayHelpers";
import { CableOverlaySvg } from "../pages/overview/PanelCableOverlaySections";
import { PodWidget } from "../pages/overview/PodWidget";
import type { AppShellPage } from "../state/pages";
import { PAGE } from "../state/pages";
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

const DONE = "#10b981";
const ZOOM_MIN = 0.45;
const ZOOM_MAX = 1.7;
// Pod sphere geometry inside PodWidget's 580-unit viewBox (centre + radius).
const POD_CX = 290;
const POD_CY = 290;
const POD_SR = 118;

interface Transform {
  x: number;
  y: number;
  z: number;
}

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
  const podSvgRef = useRef<SVGSVGElement>(null);
  const nodeEls = useRef<Record<string, HTMLButtonElement | null>>({});
  const [tf, setTf] = useState<Transform>({ x: 0, y: 0, z: 1 });
  const [animate, setAnimate] = useState(false);
  const [geo, setGeo] = useState<CableGeo | null>(null);
  const drag = useRef<{ sx: number; sy: number; x0: number; y0: number } | null>(null);

  // Measure cable endpoints in the stage's screen space (so pan/zoom transforms
  // on the world layer are absorbed), then feed the shared Overview cable look.
  const measure = useCallback(() => {
    const stage = stageRef.current;
    const podSvg = podSvgRef.current;
    if (!stage || !podSvg) return;
    const ctm = podSvg.getScreenCTM();
    if (!ctm) return;
    const cRect = stage.getBoundingClientRect();
    const toStage = (px: number, py: number) => ({
      x: ctm.a * px + ctm.c * py + ctm.e - cRect.left,
      y: ctm.b * px + ctm.d * py + ctm.f - cRect.top,
    });
    const center = toStage(POD_CX, POD_CY);
    const edge = toStage(POD_CX + POD_SR, POD_CY);
    const radius = Math.hypot(edge.x - center.x, edge.y - center.y);
    const intercept = (x: number, y: number) => {
      const dx = x - center.x;
      const dy = y - center.y;
      const len = Math.hypot(dx, dy) || 1;
      return { x: center.x + (dx / len) * radius, y: center.y + (dy / len) * radius };
    };

    const cables = CANVAS_NODES.flatMap((node) => {
      if (node.key === PAGE.FILES) return [];
      const el = nodeEls.current[node.key];
      if (!el) return [];
      const r = el.getBoundingClientRect();
      const left = r.left - cRect.left;
      const right = r.right - cRect.left;
      const top = r.top - cRect.top;
      const bottom = r.bottom - cRect.top;
      let px = (left + right) / 2;
      let py = (top + bottom) / 2;
      if (node.x <= -60) px = right;
      else if (node.x >= 60) px = left;
      else if (node.y < 0) py = bottom;
      else py = top;
      const pod = intercept(px, py);
      return [
        {
          id: node.key,
          x1: px,
          y1: py,
          x2: pod.x,
          y2: pod.y,
          color: node.color,
          shadow: node.shadow,
          connected: isNodeDone(node, ree, badges, provisioned),
        },
      ];
    });
    setGeo({ cables, decoCables: [], w: cRect.width, h: cRect.height });
  }, [ree, badges, provisioned]);

  // Re-measure after every transform/data change (and on resize).
  // biome-ignore lint/correctness/useExhaustiveDependencies: tf re-measures cables on pan/zoom
  useEffect(() => {
    const id = requestAnimationFrame(measure);
    return () => cancelAnimationFrame(id);
  }, [measure, tf]);
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const ro = new ResizeObserver(() => requestAnimationFrame(measure));
    ro.observe(stage);
    return () => ro.disconnect();
  }, [measure]);

  // Wheel-to-zoom toward the cursor. Attached natively so preventDefault works.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = stage.getBoundingClientRect();
      setAnimate(false);
      setTf((prev) => {
        const ox = event.clientX - rect.left - rect.width / 2 - prev.x;
        const oy = event.clientY - rect.top - rect.height / 2 - prev.y;
        const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
        const z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, prev.z * factor));
        const ratio = z / prev.z - 1;
        return { x: prev.x - ox * ratio, y: prev.y - oy * ratio, z };
      });
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const d = drag.current;
      if (!d) return;
      setTf((prev) => ({
        ...prev,
        x: d.x0 + (event.clientX - d.sx),
        y: d.y0 + (event.clientY - d.sy),
      }));
    };
    const onUp = () => {
      drag.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const startPan = (event: React.MouseEvent) => {
    if ((event.target as HTMLElement).closest("[data-canvas-node]")) return;
    setAnimate(false);
    drag.current = { sx: event.clientX, sy: event.clientY, x0: tf.x, y0: tf.y };
  };
  const resetView = () => {
    setAnimate(true);
    setTf({ x: 0, y: 0, z: 1 });
  };
  const zoomBy = (factor: number) => {
    setAnimate(true);
    setTf((prev) => ({ ...prev, z: Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, prev.z * factor)) }));
  };

  const { completed, total } = lifecycleProgress(ree, badges, provisioned);
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
        cursor: drag.current ? "grabbing" : "grab",
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
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          transformOrigin: "0 0",
          transform: `translate(${tf.x}px, ${tf.y}px) scale(${tf.z})`,
          transition: animate ? "transform 0.4s cubic-bezier(0.4,0,0.2,1)" : "none",
        }}
      >
        <div style={{ position: "absolute", left: 0, top: 0, transform: "translate(-50%,-50%)" }}>
          <PodWidget evaluation={evaluation} svgRef={podSvgRef} size={300} />
        </div>

        <nav aria-label="Workspace pages">
          {CANVAS_NODES.map((node) => (
            <NodeCard
              key={node.key}
              node={node}
              setRef={(el) => {
                nodeEls.current[node.key] = el;
              }}
              done={isNodeDone(node, ree, badges, provisioned)}
              locked={isNodeLocked(node, provisioned)}
              active={isNodeActive(node, page)}
              rows={nodeSummary(node, ree, provisioned)}
              onNavigate={onNavigate}
            />
          ))}
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
  setRef: (el: HTMLButtonElement | null) => void;
  done: boolean;
  locked: boolean;
  active: boolean;
  rows: SummaryRow[];
  onNavigate: (page: AppShellPage) => void;
}

function NodeCard({ node, setRef, done, locked, active, rows, onNavigate }: NodeCardProps) {
  return (
    <button
      type="button"
      data-canvas-node
      aria-label={node.label}
      ref={setRef}
      disabled={locked}
      onClick={() => onNavigate(node.key)}
      style={{
        position: "absolute",
        left: node.x,
        top: node.y,
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
