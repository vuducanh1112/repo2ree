import type { AppShellPage } from "@core/app-shell/pages";
import { type NodeOffset, nodeOffsetAfterDrag } from "@core/canvas/canvasLayout";
import { type CanvasNode, type CanvasNodeOverview, nodeScale } from "@core/canvas/canvasNodes";
import { useCallback, useId, useRef, useState } from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { canvasIcon } from "./canvasIcons";
import styles from "./NodeCard.module.css";

interface NodeCardProps {
  node: CanvasNode;
  setRef: (el: HTMLButtonElement | null) => void;
  setPortRef: (el: HTMLSpanElement | null) => void;
  done: boolean;
  stale?: boolean;
  active: boolean;
  running: boolean;
  next?: boolean;
  blocked?: boolean;
  overview: CanvasNodeOverview;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
  offset: NodeOffset;
  zoom: number;
  onMove: (key: string, offset: NodeOffset) => void;
  onDraggingChange: (key: string, dragging: boolean) => void;
}

export function NodeCard({
  node,
  setRef,
  setPortRef,
  done,
  stale = false,
  active,
  running,
  next = false,
  blocked = false,
  overview,
  onNavigate,
  offset,
  zoom,
  onMove,
  onDraggingChange,
}: NodeCardProps) {
  const stateNoteId = useId();
  const { placed, dragging, onPointerDown, onKeyDown, suppressClick } = useNodeDrag({
    node,
    offset,
    zoom,
    onMove,
    onDraggingChange,
  });
  const position = {
    "--node-x": `${placed.x}px`,
    "--node-y": `${placed.y}px`,
    "--node-scale": nodeScale(placed),
    "--node-stand-height": `${node.standHeight}px`,
    "--node-tint": stageTone(node.key),
  };
  const state = running
    ? "running"
    : stale
      ? "stale"
      : done
        ? "complete"
        : next
          ? "next"
          : blocked
            ? "blocked"
            : "idle";
  const stateLabel = {
    running: "RUNNING",
    stale: "STALE",
    complete: "DONE",
    next: "NEXT",
    blocked: "BLOCKED",
    idle: "READY",
  }[state];
  const visibleScripts = overview.scripts.slice(0, 2);
  const hiddenScriptCount = overview.scripts.length - visibleScripts.length;

  return (
    <>
      <span aria-hidden className={styles.floorShadow} data-visible style={cssVars(position)} />
      <div className={styles.anchor} data-floor style={cssVars(position)}>
        <span aria-hidden className={styles.foot} />
        <div className={styles.billboard}>
          <span aria-hidden className={styles.post} />
          <button
            type="button"
            data-canvas-node
            aria-label={node.label}
            aria-describedby={running || next ? stateNoteId : undefined}
            ref={setRef}
            onPointerDown={onPointerDown}
            onKeyDown={onKeyDown}
            onClick={(e) => {
              if (suppressClick()) return;
              onNavigate(node.key, e.currentTarget.getBoundingClientRect());
            }}
            className={styles.card}
            data-dragging={dragging || undefined}
            data-done={done || undefined}
            data-stale={stale || undefined}
            data-next={next || undefined}
            data-active={active || undefined}
            data-running={running || undefined}
          >
            <span aria-hidden className={styles.shell} />
            {(running || next) && (
              <span id={stateNoteId} className={styles.stateNote}>
                {running ? "Running" : "Next step"}
              </span>
            )}
            <div className={styles.head}>
              <span aria-hidden className={styles.glyph}>
                {canvasIcon(node.iconKey)(14)}
              </span>
              <div className={styles.titleBox}>
                <div className={styles.title}>{node.label}</div>
              </div>
              <span className={styles.state} data-state={state}>
                <span aria-hidden className={styles.stateLamp} />
                {stateLabel}
              </span>
            </div>

            <div className={styles.screen}>
              {running && <span aria-hidden className={styles.scan} />}
              {overview.facts.length > 0 && (
                <div className={styles.facts}>
                  {overview.facts.map((row) => (
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
                </div>
              )}

              {visibleScripts.map((script) => (
                <div
                  key={script.key}
                  className={styles.script}
                  data-missing={!script.available || undefined}
                >
                  <div className={styles.scriptHead}>
                    <span className={styles.scriptLabel}>{script.label}</span>
                    <span title={script.path || undefined} className={styles.scriptPath}>
                      {script.path ? script.path.split("/").at(-1) : "NOT CONFIGURED"}
                    </span>
                  </div>
                  <code className={styles.scriptCode}>
                    {script.lines.length > 0
                      ? script.lines.map((line, index) => (
                          // biome-ignore lint/suspicious/noArrayIndexKey: the saved source line's ordinal is its stable identity
                          <span key={`${script.key}-${index}`}>
                            <i aria-hidden>{String(index + 1).padStart(2, "0")}</i>
                            {line || " "}
                          </span>
                        ))
                      : `> ${script.path ? "FILE UNAVAILABLE" : "AWAITING SCRIPT"}`}
                  </code>
                </div>
              ))}

              {hiddenScriptCount > 0 && (
                <div className={styles.moreScripts}>+{hiddenScriptCount} MORE SCRIPTS</div>
              )}
            </div>

            {overview.evidenceExpected && (
              <div
                className={styles.evidence}
                data-state={stale ? "stale" : overview.receipt ? "recorded" : "empty"}
              >
                <span aria-hidden className={styles.evidenceLamp} />
                <span className={styles.evidenceLabel}>
                  {stale
                    ? "RECEIPT · INPUTS CHANGED"
                    : (overview.receipt?.label.toUpperCase() ?? "NO RECEIPT")}
                </span>
                {overview.receipt?.duration && (
                  <span className={styles.evidenceMeta}>{overview.receipt.duration}</span>
                )}
                {overview.receipt?.scriptDigest && (
                  <span title={overview.receipt.scriptDigest} className={styles.digest}>
                    {overview.receipt.scriptDigest}
                  </span>
                )}
              </div>
            )}
            <span ref={setPortRef} aria-hidden className={styles.port} />
          </button>
        </div>
      </div>
    </>
  );
}

const DRAG_THRESHOLD_PX = 4;
const NUDGE_STEP = 16;
const NUDGE_STEP_LARGE = 96;

interface NodeDragOptions {
  node: CanvasNode;
  offset: NodeOffset;
  zoom: number;
  onMove: (key: string, offset: NodeOffset) => void;
  onDraggingChange: (key: string, dragging: boolean) => void;
}

function useNodeDrag({ node, offset, zoom, onMove, onDraggingChange }: NodeDragOptions) {
  const [liveOffset, setLiveOffset] = useState<NodeOffset | null>(null);
  const gesture = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    from: NodeOffset;
    moved: boolean;
  } | null>(null);
  const swallowClick = useRef(false);

  const effective = liveOffset ?? offset;
  const placed =
    effective.dx === 0 && effective.dy === 0
      ? node
      : { ...node, x: node.x + effective.dx, y: node.y + effective.dy };

  const finish = useCallback(
    (commit: NodeOffset | null) => {
      const active = gesture.current;
      gesture.current = null;
      if (!active) return;
      if (active.moved) {
        swallowClick.current = true;
        onDraggingChange(node.key, false);
        if (commit) onMove(node.key, commit);
      }
      setLiveOffset(null);
    },
    [node.key, onMove, onDraggingChange],
  );

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      if (!event.isPrimary || event.button !== 0) return;
      const target = event.currentTarget;
      gesture.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        from: offset,
        moved: false,
      };

      const onMoveEvent = (move: PointerEvent) => {
        const active = gesture.current;
        if (!active || move.pointerId !== active.pointerId) return;
        const dx = move.clientX - active.startX;
        const dy = move.clientY - active.startY;
        if (!active.moved) {
          if (Math.hypot(dx, dy) < DRAG_THRESHOLD_PX) return;
          active.moved = true;
          target.setPointerCapture?.(active.pointerId);
          onDraggingChange(node.key, true);
        }
        setLiveOffset(nodeOffsetAfterDrag(node, active.from, { dx: dx / zoom, dy: dy / zoom }));
      };
      const onUp = (up: PointerEvent) => {
        const active = gesture.current;
        if (!active || up.pointerId !== active.pointerId) return;
        const dx = up.clientX - active.startX;
        const dy = up.clientY - active.startY;
        detach();
        finish(
          active.moved
            ? nodeOffsetAfterDrag(node, active.from, { dx: dx / zoom, dy: dy / zoom })
            : null,
        );
      };
      const onCancel = () => {
        detach();
        finish(null);
      };
      function detach() {
        window.removeEventListener("pointermove", onMoveEvent);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onCancel);
      }
      window.addEventListener("pointermove", onMoveEvent);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onCancel);
    },
    [node, offset, zoom, finish, onDraggingChange],
  );

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>) => {
      const step = event.shiftKey ? NUDGE_STEP_LARGE : NUDGE_STEP;
      const delta = {
        ArrowLeft: { dx: -step, dy: 0 },
        ArrowRight: { dx: step, dy: 0 },
        ArrowUp: { dx: 0, dy: -step },
        ArrowDown: { dx: 0, dy: step },
      }[event.key];
      if (!delta) return;
      event.preventDefault();
      onMove(node.key, nodeOffsetAfterDrag(node, offset, delta));
    },
    [node, offset, onMove],
  );

  const suppressClick = useCallback(() => {
    if (!swallowClick.current) return false;
    swallowClick.current = false;
    return true;
  }, []);

  return { placed, dragging: liveOffset !== null, onPointerDown, onKeyDown, suppressClick };
}
