import type { AppShellPage } from "@core/app-shell/pages";
import type { CanvasNode, CanvasNodeOverview } from "@core/canvas/canvasNodes";
import { useId } from "react";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { canvasIcon } from "./canvasIcons";
import styles from "./NodeCard.module.css";

interface NodeCardProps {
  node: CanvasNode;
  setRef: (el: HTMLButtonElement | null) => void;
  setPortRef: (el: HTMLSpanElement | null) => void;
  done: boolean;
  /** Done, but the recorded run's inputs no longer match the workspace. */
  stale?: boolean;
  active: boolean;
  /** A run for this step is in flight right now. */
  running: boolean;
  /** The step the authoring graph says to do next. */
  next?: boolean;
  /** The step has unmet prerequisites in the authoring graph. */
  blocked?: boolean;
  overview: CanvasNodeOverview;
  onNavigate: (page: AppShellPage, originRect?: DOMRect) => void;
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
}: NodeCardProps) {
  // A panel's state — running, or the step to do next — is state, not identity:
  // it rides on the description so the panel's accessible name stays the node's
  // label, which is how every caller — and every navigation selector —
  // addresses it. One note at a time, by the same precedence the badge uses.
  const stateNoteId = useId();
  const position = {
    "--node-x": `${node.x}px`,
    "--node-y": `${node.y}px`,
    "--node-scale": 1,
    "--node-stand-height": `${node.standHeight}px`,
    "--node-tint": stageTone(node.key),
  };
  // What is happening now outranks what the panel has to report: a step that is
  // running is running whether or not it also holds a stale result.
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
            onClick={(e) => {
              onNavigate(node.key, e.currentTarget.getBoundingClientRect());
            }}
            className={styles.card}
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
