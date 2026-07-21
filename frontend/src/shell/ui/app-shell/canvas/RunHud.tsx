import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import type { ReeRunFailure, ReeRunSummary } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { type ReeRunFailureTone, runFailurePresentation } from "@core/runs/runFailurePresentation";
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
import { C, F } from "../../theme/theme";
import { LogPanel } from "../components/logPanel";
import { HudConsole } from "./HudConsole";

const STATUS_COLOR: Record<ReeRunSummary["status"], string> = {
  created: C.accent,
  queued: C.accent,
  provisioning: C.accent,
  running: C.accent,
  canceling: "#d97706",
  succeeded: "#16a34a",
  failed: "#dc2626",
  canceled: "#d97706",
};

type StreamKey = "stdout" | "stderr" | "system";
const STREAMS: StreamKey[] = ["stdout", "stderr", "system"];

// Tone-driven accent for the failure note, so a retryable outage reads
// differently from a rejected request or a genuine fault.
const FAILURE_TONE_COLOR: Record<ReeRunFailureTone, string> = {
  transient: "#d97706",
  rejected: "#ca8a04",
  fault: "#dc2626",
};

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
      outerStyle={{
        right: 60,
        bottom: 16,
        zIndex: 40,
        display: "flex",
        flexDirection: "column",
        ...(resizing ? { transition: "none" } : null),
      }}
      icon={Ic.terminal(16)}
      iconColor={activeCount > 0 ? C.accent : "#64748b"}
      title="Logs"
      subtitle={
        latest
          ? `${tabLabel(runHudTabForOperation(latest.operation))} · ${latest.status}`
          : "No runs yet"
      }
      on={runs.length > 0}
      expandLabel="Expand logs console"
      collapseLabel="Collapse logs console"
      bodyStyle={{ maxHeight: size.height }}
      resizeGrip={
        open && (
          <button
            type="button"
            aria-label="Resize logs console"
            title="Drag to resize"
            onMouseDown={startResize}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: 18,
              height: 18,
              zIndex: 2,
              border: "none",
              background: "transparent",
              cursor: "nwse-resize",
              padding: 0,
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "flex-start",
              color: C.borderMid,
            }}
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
      <div
        role="tablist"
        aria-label="Run log steps"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          padding: "7px 10px 6px",
          borderBottom: `1px solid ${C.border}`,
          flexShrink: 0,
          overflowX: "auto",
        }}
      >
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

      <div style={{ overflowY: "auto", minHeight: 0, padding: "8px 10px 10px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 8,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 650, color: C.text, flex: 1 }}>
            {tabLabel(tab)}
          </span>
          {STREAMS.map((stream) => (
            <button
              key={stream}
              type="button"
              aria-pressed={streams.has(stream)}
              onClick={() => toggleStream(stream)}
              style={{
                border: `1px solid ${streams.has(stream) ? C.accent : C.border}`,
                borderRadius: 999,
                background: streams.has(stream) ? "rgba(3, 105, 161, 0.08)" : C.surface,
                color: streams.has(stream) ? C.accent : C.textMuted,
                fontFamily: F.mono,
                fontSize: 9.5,
                fontWeight: 600,
                padding: "2px 8px",
                cursor: "pointer",
              }}
            >
              {stream}
            </button>
          ))}
        </div>

        {tabRuns.length === 0 ? (
          <div
            style={{
              padding: "18px 0 12px",
              textAlign: "center",
              color: C.textMuted,
              fontSize: 12,
              fontFamily: F.sans,
            }}
          >
            No {tabLabel(tab).toLowerCase()} runs yet
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
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
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        border: "none",
        borderRadius: 6,
        background: selected ? "rgba(3, 105, 161, 0.1)" : "transparent",
        color: selected ? C.accent : C.textMuted,
        fontFamily: F.mono,
        fontSize: 9.5,
        fontWeight: 700,
        letterSpacing: 0.4,
        padding: "4px 6px",
        cursor: "pointer",
        whiteSpace: "nowrap",
        flexShrink: 0,
        transition: "background 0.12s, color 0.12s",
      }}
    >
      <span>{hovered ? label.toUpperCase() : abbrev}</span>
      {activity.active && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: C.accent,
            boxShadow: `0 0 6px ${C.accent}88`,
            flexShrink: 0,
          }}
        />
      )}
      {activity.failed && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#dc2626",
            flexShrink: 0,
          }}
        />
      )}
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
  const statusColor = STATUS_COLOR[run.status] ?? C.textMuted;
  return (
    <div
      style={{
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        background: C.surface,
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "7px 10px",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span
          style={{
            display: "flex",
            color: C.textMuted,
            flexShrink: 0,
            transform: expanded ? "rotate(90deg)" : "none",
            transition: "transform 0.15s",
          }}
        >
          {Ic.chevR(12)}
        </span>
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 11,
            color: C.textMid,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            flex: 1,
            minWidth: 0,
          }}
        >
          {run.runId}
        </span>
        <span style={{ fontFamily: F.mono, fontSize: 10, color: C.textMuted, flexShrink: 0 }}>
          {formatStartTime(run)}
          {duration ? ` · ${duration}` : ""}
        </span>
        <span
          role="status"
          aria-label={`Run ${run.status}`}
          style={{
            fontFamily: F.mono,
            fontSize: 9.5,
            fontWeight: 700,
            color: statusColor,
            flexShrink: 0,
            minWidth: 56,
            textAlign: "right",
          }}
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
  const color = FAILURE_TONE_COLOR[view.tone];
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 8,
        padding: "6px 10px 8px 30px",
        borderTop: `1px solid ${C.border}`,
        fontFamily: F.mono,
        fontSize: 10.5,
      }}
    >
      <span style={{ color, fontWeight: 700, flexShrink: 0 }}>{view.label}</span>
      {view.retryable && (
        <span style={{ color: C.textMuted, flexShrink: 0 }} title="Safe to retry">
          retryable
        </span>
      )}
      <span
        style={{
          color: C.textMid,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          minWidth: 0,
        }}
        title={view.message}
      >
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
    <div
      style={{
        borderTop: `1px solid ${C.border}`,
        padding: 8,
        display: "flex",
        flexDirection: "column",
        maxHeight,
      }}
    >
      <LogPanel log={log} running={running} />
    </div>
  );
}
