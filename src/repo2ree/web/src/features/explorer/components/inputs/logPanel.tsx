import { Ic } from "../../../../components/Icon";
import { C, F } from "../../../../constants/theme";
import type { LogEntry, LogLine } from "../../../../types";

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
export function LogPanel({ log }: LogPanelProps) {
  return (
    <div
      style={{
        flex: 1,
        overflow: "auto",
        background: "#f8fafc",
        borderRadius: 10,
        border: `1px solid ${C.border}`,
        minHeight: 200,
      }}
    >
      {!log ? (
        <div
          style={{
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
        <div style={{ padding: "12px 0" }}>
          <div
            style={{
              padding: "6px 18px 12px",
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.mono,
              borderBottom: `1px solid ${C.border}`,
              marginBottom: 4,
            }}
          >
            Last run:{" "}
            {new Date(log.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
          </div>
          {(() => {
            const seenLines = new Map<string, number>();
            return log.lines.map((line) => {
              const lineSig = `${line.type}:${line.msg}`;
              const occurrence = (seenLines.get(lineSig) ?? 0) + 1;
              seenLines.set(lineSig, occurrence);
              const s = LOG_STYLE[line.type] || LOG_STYLE.info;
              return (
                <div
                  key={`${lineSig}::${occurrence}`}
                  style={{
                    display: "flex",
                    padding: "3px 18px",
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
                  <span style={{ color: s.color }}>{line.msg}</span>
                </div>
              );
            });
          })()}
        </div>
      )}
    </div>
  );
}
