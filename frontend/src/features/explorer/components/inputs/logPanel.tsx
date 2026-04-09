import { useMemo, useState } from "react";
import { Ic } from "../../../../components/Icon";
import { C, F } from "../../../../constants/theme";
import type { LogEntry, LogLine } from "../../../../types";

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

export function LogPanel({ log }: LogPanelProps) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

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
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "#f8fafc",
        borderRadius: 10,
        border: `1px solid ${C.border}`,
        minHeight: 200,
        maxHeight: 360,
      }}
    >
      {!log ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            minHeight: 200,
            gap: 8,
            color: C.textMuted,
          }}
        >
          {Ic.terminal()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>No output yet</span>
        </div>
      ) : (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
              padding: "10px 14px",
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.mono,
              borderBottom: `1px solid ${C.border}`,
              background: C.surface,
              boxShadow: "0 1px 0 rgba(15, 23, 42, 0.04)",
              flexShrink: 0,
            }}
          >
            <span>
              Last run:{" "}
              {new Date(log.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
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
            {(() => {
              const seenLines = new Map<string, number>();
              return renderLines.map((line) => {
                const lineSig = `${line.type}:${line.msg}`;
                const occurrence = (seenLines.get(lineSig) ?? 0) + 1;
                seenLines.set(lineSig, occurrence);
                const s = LOG_STYLE[line.type] || LOG_STYLE.info;
                return (
                  <div
                    key={`${lineSig}::${occurrence}`}
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
                );
              });
            })()}
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
