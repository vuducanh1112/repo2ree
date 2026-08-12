import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import type { ReeRunFailure, ReeRunSummary } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { runFailurePresentation } from "@core/runs/runFailurePresentation";
import {
  activeRunCount,
  formatRunDuration,
  hudTabActivity,
  newestActiveRun,
  newestRun,
  RUN_HUD_TABS,
  type RunHudTabKey,
  runHudTabForOperation,
  runsForHudTab,
} from "@core/runs/runHud";
import { useReeRunLogsQuery, useReeRunQuery, useReeRunsQuery } from "@shell/data/runs/queries";
import { useEffect, useRef, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { useCornerResize } from "../../shared/hooks/useCornerResize";
import { failureTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import { LogPanel } from "../components/logPanel";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";
import styles from "./RunHud.module.css";

type StreamKey = "stdout" | "stderr" | "system";
const STREAMS: StreamKey[] = ["stdout", "stderr", "system"];

function tabLabel(key: RunHudTabKey): string {
  return RUN_HUD_TABS.find((tab) => tab.key === key)?.label ?? key;
}

function formatStartTime(run: ReeRunSummary): string {
  const date = new Date(run.startedAt ?? run.createdAt);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit" });
}

/**
 * The logs HUD: one always-available console collecting every run of the
 * open REE, split into one tab per pipeline step. Auto-follows new runs (also
 * ones started outside this tab, e.g. by an agent) until the user picks a tab.
 */
export function RunHud() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<RunHudTabKey>("source");
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [streams, setStreams] = useState<Set<StreamKey>>(() => new Set(STREAMS));
  // Logs get arbitrarily long; a top-left grip lets the console grow up/left
  // from its bottom-right anchor.
  const { size, resizing, startResize } = useCornerResize({
    defaultWidth: 480,
    defaultHeight: 460,
    minWidth: 480,
    minHeight: 280,
  });

  const runsQuery = useReeRunsQuery();
  const runs = runsQuery.data ?? [];

  // Follow each newly observed active run: switch to its tab and expand it.
  // A manual tab click overrides this until the next run starts.
  const followedRunIdRef = useRef<string | null>(null);
  const active = newestActiveRun(runs);
  useEffect(() => {
    if (!active || followedRunIdRef.current === active.runId) return;
    followedRunIdRef.current = active.runId;
    setTab(runHudTabForOperation(active.operation));
    setExpandedRunId(active.runId);
  }, [active]);

  const activeCount = activeRunCount(runs);
  const latest = newestRun(runs);
  const tabRuns = runsForHudTab(runs, tab);

  const toggleStream = (stream: StreamKey) => {
    setStreams((prev) => {
      const next = new Set(prev);
      if (next.has(stream)) next.delete(stream);
      else next.add(stream);
      // An empty filter shows nothing and looks broken; snap back to "all".
      return next.size === 0 ? new Set(STREAMS) : next;
    });
  };

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((v) => !v)}
      widthOpen={size.width}
      widthCollapsed={264}
      // Docked bottom-right, beside the zoom controls that own the corner.
      className={hud.logsPlacement}
      resizing={resizing}
      icon={Ic.terminal(16)}
      iconTint={activeCount > 0 ? "var(--chrome-accent)" : undefined}
      title="Logs"
      subtitle={
        latest
          ? `${tabLabel(runHudTabForOperation(latest.operation))} · ${latest.status}`
          : "No runs yet"
      }
      on={runs.length > 0}
      expandLabel="Expand logs console"
      collapseLabel="Collapse logs console"
      bodyClassName={hud.logsBody}
      vars={{ "--hud-logs-height": `${size.height}px` }}
      resizeGrip={
        open && (
          <button
            type="button"
            aria-label="Resize logs console"
            title="Drag to resize"
            onMouseDown={startResize}
            className={styles.resizeGrip}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
              <title>resize</title>
              <path
                d="M2 8V2h6M2 5V2h3"
                stroke="currentColor"
                strokeWidth="1.5"
                fill="none"
                strokeLinecap="round"
              />
            </svg>
          </button>
        )
      }
    >
      <div role="tablist" aria-label="Run log steps" className={styles.tabs}>
        {RUN_HUD_TABS.map((t) => (
          <HudTab
            key={t.key}
            abbrev={t.abbrev}
            label={t.label}
            selected={t.key === tab}
            activity={hudTabActivity(runs, t.key)}
            onSelect={() => setTab(t.key)}
          />
        ))}
      </div>

      <div className={styles.runs}>
        <div className={styles.runsHead}>
          <span className={styles.runsTitle}>{tabLabel(tab)}</span>
          {STREAMS.map((stream) => (
            <button
              key={stream}
              type="button"
              aria-pressed={streams.has(stream)}
              onClick={() => toggleStream(stream)}
              className={styles.stream}
            >
              {stream}
            </button>
          ))}
        </div>

        {tabRuns.length === 0 ? (
          <div className={styles.empty}>No {tabLabel(tab).toLowerCase()} runs yet</div>
        ) : (
          <div className={styles.runList}>
            {tabRuns.map((run) => (
              <RunRow
                key={run.runId}
                run={run}
                expanded={run.runId === expandedRunId}
                streams={streams}
                // Leave headroom for the console header, tab strip, and run
                // rows so the expanded log scrolls inside the resized body.
                logMaxHeight={Math.max(260, size.height - 200)}
                onToggle={() =>
                  setExpandedRunId((current) => (current === run.runId ? null : run.runId))
                }
              />
            ))}
          </div>
        )}
      </div>
    </HudConsole>
  );
}

function HudTab({
  abbrev,
  label,
  selected,
  activity,
  onSelect,
}: {
  abbrev: string;
  label: string;
  selected: boolean;
  activity: { active: boolean; failed: boolean };
  onSelect: () => void;
}) {
  // The resting strip shows abbreviations so all steps fit; hovering a tab
  // expands it to its full name in place.
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      aria-label={label}
      title={label}
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={styles.tab}
    >
      <span>{hovered ? label.toUpperCase() : abbrev}</span>
      {activity.active && <span aria-hidden className={styles.tabDot} data-kind="active" />}
      {activity.failed && <span aria-hidden className={styles.tabDot} data-kind="failed" />}
    </button>
  );
}

function RunRow({
  run,
  expanded,
  streams,
  logMaxHeight,
  onToggle,
}: {
  run: ReeRunSummary;
  expanded: boolean;
  streams: Set<StreamKey>;
  logMaxHeight: number;
  onToggle: () => void;
}) {
  const duration = formatRunDuration(run);
  return (
    <div className={styles.run}>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
        className={styles.runHeader}
      >
        <span aria-hidden className={styles.runChevron}>
          {Ic.chevR(12)}
        </span>
        <span className={styles.runId}>{run.runId}</span>
        <span className={styles.runWhen}>
          {formatStartTime(run)}
          {duration ? ` · ${duration}` : ""}
        </span>
        <span
          role="status"
          aria-label={`Run ${run.status}`}
          className={styles.runStatus}
          data-status={run.status}
        >
          {run.status.toUpperCase()}
        </span>
      </button>
      {run.failure && <RunFailureNote failure={run.failure} />}
      {expanded && <RunLogView run={run} streams={streams} maxHeight={logMaxHeight} />}
    </div>
  );
}

// The typed reason a run failed, shown at a glance under its row: a category
// label, a retryable hint, and the underlying message. Surfaces the failure
// contract so a client need not open the log stream to learn why a run failed.
function RunFailureNote({ failure }: { failure: ReeRunFailure }) {
  const view = runFailurePresentation(failure);
  const color = failureTone(view.tone);
  return (
    <div className={styles.failure} style={cssVars({ "--failure-ink": color })}>
      <span className={styles.failureLabel}>{view.label}</span>
      {view.retryable && (
        <span className={styles.failureRetryable} title="Safe to retry">
          retryable
        </span>
      )}
      <span className={styles.failureMessage} title={view.message}>
        {view.message}
      </span>
    </div>
  );
}

// Mounted only while its run row is expanded, so only one run's log feed is
// polled at a time. The run query alongside stops the log poll once terminal.
function RunLogView({
  run,
  streams,
  maxHeight,
}: {
  run: ReeRunSummary;
  streams: Set<StreamKey>;
  maxHeight: number;
}) {
  const runQuery = useReeRunQuery(undefined, run.runId);
  const logsQuery = useReeRunLogsQuery(undefined, run.runId);
  const status = runQuery.data?.status ?? run.status;
  const running = !isTerminalReeRunStatus(status);

  const lines: LogLine[] = (logsQuery.data?.lines ?? []).filter(
    (line) => !line.stream || streams.has(line.stream),
  );
  const log: LogEntry | null =
    logsQuery.data == null ? null : { lines, ts: run.startedAt ?? run.createdAt };

  return (
    <div className={styles.logView} style={cssVars({ "--run-log-height": `${maxHeight}px` })}>
      <LogPanel log={log} running={running} />
    </div>
  );
}
