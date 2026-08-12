import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import { useEffect, useMemo, useRef, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import styles from "./logPanel.module.css";

const MAX_RENDER_LOG_LINES = 800;
const MAX_COPY_LOG_LINES = 2000;

type LogLineType = LogLine["type"];

// The severity gutter, padded so the lines align. How each severity *reads* is
// in logPanel.module.css, keyed off the same `type` the backend sends.
const LOG_PREFIX: Record<LogLineType, string> = {
  info: "  INFO",
  ok: "    OK",
  warn: "  WARN",
  err: "   ERR",
  out: "      ",
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
        const prefix = LOG_PREFIX[line.type] || LOG_PREFIX.info;
        const ts = formatLineTimestamp(line.ts || log.ts);
        return `${ts} [${prefix.trim() || "OUT"}] ${line.msg}`;
      })
      .join("\n");
  }, [copyLines, log]);

  const renderedEntries = useMemo(() => {
    const seenLines = new Map<string, number>();
    return renderLines.map((line) => {
      const lineSig = `${line.type}:${line.msg}`;
      const occurrence = (seenLines.get(lineSig) ?? 0) + 1;
      seenLines.set(lineSig, occurrence);
      return { key: `${lineSig}::${occurrence}`, line };
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
    <div className={styles.panel}>
      {!log ? (
        <div className={styles.empty}>
          {Ic.terminal()}
          <span className={styles.emptyLabel}>No output yet</span>
        </div>
      ) : (
        <>
          <div className={styles.header}>
            <span>
              Last run:{" "}
              {new Date(log.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
            </span>
            <span className={styles.state} data-running={running || undefined}>
              {running ? "Running" : "Idle"}
            </span>
            <button
              type="button"
              onClick={onCopyLogs}
              className={styles.copy}
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

          <div ref={scrollRef} onScroll={onLogScroll} className={styles.stream}>
            {renderTruncated && (
              <div className={styles.truncation}>
                Showing last {renderLines.length} lines to keep the UI responsive.
              </div>
            )}
            {renderedEntries.map(({ key, line }) => (
              <div key={key} className={styles.line} data-kind={line.type}>
                <span className={styles.severity}>
                  [{LOG_PREFIX[line.type] || LOG_PREFIX.info}]
                </span>
                <span className={styles.timestamp}>{formatLineTimestamp(line.ts || log.ts)}</span>
                <span>{line.msg}</span>
              </div>
            ))}
          </div>
          {copyTruncated && (
            <div className={styles.copyNote}>Copy includes last {copyLines.length} lines.</div>
          )}
        </>
      )}
    </div>
  );
}
