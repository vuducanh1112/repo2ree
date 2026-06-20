import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import { useEffect, useMemo, useRef, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import {
  WORKFLOW_LOG_EMPTY_STYLE,
  WORKFLOW_LOG_PANEL_HEADER_STYLE,
  WORKFLOW_LOG_PANEL_ROOT_STYLE,
} from "./statusUiStyles";

const MAX_RENDER_LOG_LINES = 800;
const MAX_COPY_LOG_LINES = 2000;

type LogLineType = LogLine["type"];

interface LogStyleEntry {
  pre: string;
  color: string;
  bg: string;
}
const LOG_STYLE: Record<LogLineType, LogStyleEntry> = {
  info: { pre: "  INFO", color: "#475569", bg: "transparent" },
  ok: { pre: "    OK", color: "#16a34a", bg: "#f0fdf4" },
  warn: { pre: "  WARN", color: "#d97706", bg: "#fef3c7" },
  err: { pre: "   ERR", color: "#dc2626", bg: "#fef2f2" },
  out: { pre: "      ", color: "#1e293b", bg: "transparent" },
};

interface LogPanelProps {
  log: LogEntry | null;
  running?: boolean;
}

function formatLineTimestamp(ts?: string): string {
  if (!ts) return "--:--:--";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function LogPanel({ log, running = false }: LogPanelProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  // Tail the log as new lines stream in. We "stick" to the bottom unless the
  // user scrolls up to read history, then resume sticking once they return
  // near the bottom. Without this the panel stays pinned at the first lines.
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  const onLogScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  };

  const renderLines = useMemo(() => {
    if (!log) return [];
    if (log.lines.length <= MAX_RENDER_LOG_LINES) return log.lines;
    return log.lines.slice(log.lines.length - MAX_RENDER_LOG_LINES);
  }, [log]);

  const copyLines = useMemo(() => {
    if (!log) return [];
    if (log.lines.length <= MAX_COPY_LOG_LINES) return log.lines;
    return log.lines.slice(log.lines.length - MAX_COPY_LOG_LINES);
  }, [log]);

  const renderTruncated = !!log && log.lines.length > renderLines.length;
  const copyTruncated = !!log && log.lines.length > copyLines.length;

  const copyText = useMemo(() => {
    if (!log) return "";
    return copyLines
      .map((line) => {
        const s = LOG_STYLE[line.type] || LOG_STYLE.info;
        const ts = formatLineTimestamp(line.ts || log.ts);
        return `${ts} [${s.pre.trim() || "OUT"}] ${line.msg}`;
      })
      .join("\n");
  }, [copyLines, log]);

  const renderedEntries = useMemo(() => {
    const seenLines = new Map<string, number>();
    return renderLines.map((line) => {
      const lineSig = `${line.type}:${line.msg}`;
      const occurrence = (seenLines.get(lineSig) ?? 0) + 1;
      seenLines.set(lineSig, occurrence);
      return {
        key: `${lineSig}::${occurrence}`,
        line,
        style: LOG_STYLE[line.type] || LOG_STYLE.info,
      };
    });
  }, [renderLines]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: line count is the re-run trigger; the body only touches the scroll node
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [renderedEntries.length]);

  const onCopyLogs = async () => {
    if (!copyText) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(copyText);
      } else {
        const ta = document.createElement("textarea");
        ta.value = copyText;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1500);
    } catch {
      setCopyState("error");
      window.setTimeout(() => setCopyState("idle"), 2000);
    }
  };

  return (
    <div style={WORKFLOW_LOG_PANEL_ROOT_STYLE}>
      {!log ? (
        <div style={WORKFLOW_LOG_EMPTY_STYLE}>
          {Ic.terminal()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>No output yet</span>
        </div>
      ) : (
        <>
          <div style={WORKFLOW_LOG_PANEL_HEADER_STYLE}>
            <span>
              Last run:{" "}
              {new Date(log.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
            </span>
            <span style={{ color: running ? C.accent : C.textMuted, marginLeft: "auto" }}>
              {running ? "Running" : "Idle"}
            </span>
            <button
              type="button"
              onClick={onCopyLogs}
              style={{
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                background: C.surface,
                color: C.text,
                fontFamily: F.sans,
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 8px",
                cursor: copyText ? "pointer" : "not-allowed",
                opacity: copyText ? 1 : 0.65,
              }}
              disabled={!copyText}
              aria-label="Copy logs"
            >
              {copyState === "copied"
                ? "Copied"
                : copyState === "error"
                  ? "Copy failed"
                  : "Copy logs"}
            </button>
          </div>

          <div
            ref={scrollRef}
            onScroll={onLogScroll}
            style={{
              overflowY: "auto",
              overflowX: "hidden",
              flex: 1,
              padding: "8px 0",
            }}
          >
            {renderTruncated && (
              <div
                style={{
                  margin: "0 14px 8px",
                  padding: "7px 10px",
                  borderRadius: 6,
                  border: `1px solid ${C.border}`,
                  background: C.surfaceAlt,
                  color: C.textMuted,
                  fontSize: 11,
                  fontFamily: F.sans,
                }}
              >
                Showing last {renderLines.length} lines to keep the UI responsive.
              </div>
            )}
            {renderedEntries.map(({ key, line, style: s }) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  padding: "3px 14px",
                  background: s.bg,
                  fontFamily: F.mono,
                  fontSize: 13,
                  lineHeight: 1.75,
                }}
              >
                <span
                  style={{
                    color: s.color,
                    fontWeight: 600,
                    marginRight: 14,
                    flexShrink: 0,
                    fontSize: 11,
                    opacity: 0.75,
                    minWidth: 52,
                  }}
                >
                  [{s.pre}]
                </span>
                <span
                  style={{
                    color: C.textMuted,
                    marginRight: 10,
                    flexShrink: 0,
                    fontSize: 11,
                    minWidth: 58,
                  }}
                >
                  {formatLineTimestamp(line.ts || log.ts)}
                </span>
                <span style={{ color: s.color }}>{line.msg}</span>
              </div>
            ))}
          </div>
          {copyTruncated && (
            <div
              style={{
                padding: "6px 14px 9px",
                borderTop: `1px solid ${C.border}`,
                color: C.textMuted,
                fontSize: 10.5,
                fontFamily: F.sans,
                background: C.surface,
              }}
            >
              Copy includes last {copyLines.length} lines.
            </div>
          )}
        </>
      )}
    </div>
  );
}
