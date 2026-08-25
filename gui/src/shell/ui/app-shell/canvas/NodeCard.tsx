import type { AppShellPage } from "@core/app-shell/pages";
import type { CanvasNode, SummaryRow } from "@core/canvas/canvasNodes";
import { useId } from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { canvasIcon } from "./canvasIcons";
import styles from "./NodeCard.module.css";
import { StatusDot } from "./StatusDot";

interface NodeCardProps {
  node: CanvasNode;
  setRef: (el: HTMLButtonElement | null) => void;
  setPortRef: (el: HTMLSpanElement | null) => void;
  done: boolean;
  /** Done, but the recorded run's inputs no longer match the workspace. */
  stale?: boolean;
  locked: boolean;
  active: boolean;
  /** The step the authoring graph says to do next. */
  next?: boolean;
  rows: SummaryRow[];
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
}

export function NodeCard({
  node,
  setRef,
  setPortRef,
  done,
  stale = false,
  locked,
  active,
  next = false,
  rows,
  onNavigate,
}: NodeCardProps) {
  // "Next" is state, not identity: it rides on the description so the panel's
  // accessible name stays the node's label, which is how every caller — and
  // every navigation selector — addresses it.
  const nextNoteId = useId();
  const position = {
    "--node-x": `${node.x}px`,
    "--node-y": `${node.y}px`,
    "--node-scale": 1,
    "--node-stand-height": `${node.standHeight}px`,
    "--node-tint": stageTone(node.key),
  };

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
            aria-describedby={next ? nextNoteId : undefined}
            ref={setRef}
            disabled={locked}
            onClick={(e) => {
              onNavigate(node.key, e.currentTarget.getBoundingClientRect());
            }}
            className={styles.card}
            data-done={done || undefined}
            data-next={next || undefined}
            data-active={active || undefined}
          >
            <span aria-hidden className={styles.cap} />
            {next && (
              <span id={nextNoteId} className={styles.nextNote}>
                Next step
              </span>
            )}
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
            <span ref={setPortRef} aria-hidden className={styles.port} />
          </button>
        </div>
      </div>
    </>
  );
}
