import type { LogEntry, LogLine } from "./ReeTypes";

export function appendLine(
  prev: LogEntry | null,
  type: LogLine["type"],
  msg: string,
  ts: string,
): LogEntry {
  return { lines: [...(prev?.lines ?? []), { type, msg, ts }], ts };
}
