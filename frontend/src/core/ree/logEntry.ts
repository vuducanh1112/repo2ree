import type { LogEntry, LogLine } from "./ReeTypes";

export function appendLine(prev: LogEntry | null, type: LogLine["type"], msg: string): LogEntry {
  const ts = new Date().toISOString();
  return { lines: [...(prev?.lines ?? []), { type, msg, ts }], ts };
}
