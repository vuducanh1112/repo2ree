import { useState } from "react";
import { appendLine } from "../../../../core/ree/logEntry";
import type { LogEntry, LogLine } from "../../../../core/ree/ReeTypes";
import { useApiRuntime } from "../../../data/apiRuntime";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { STANDARD_IMAGE } from "../pages/workbench/WorkbenchPageSections";

const DONE = "#10b981";

const LOG_COLOR: Record<LogLine["type"], string> = {
  info: "#93c5fd",
  out: "#cbd5e1",
  ok: "#6ee7b7",
  warn: "#fcd34d",
  err: "#fca5a5",
};

interface BenchConsoleProps {
  provisioned: boolean;
  reeName?: string;
}

// The workbench is the lab this whole hub lives in, so it reads as an ambient
// console pinned to the bench corner rather than a node on the ring. Clicking
// the header grows it open in place (and shrinks it back) — no separate panel —
// to surface live bench status and the one action that matters here:
// reprovision, with a terminal-style readout.
export function BenchConsole({ provisioned, reeName }: BenchConsoleProps) {
  const { reeId, reeApi } = useApiRuntime();
  const [open, setOpen] = useState(false);
  const [reprovisioning, setReprovisioning] = useState(false);
  const [log, setLog] = useState<LogEntry | null>(null);

  async function handleReprovision() {
    setReprovisioning(true);
    setLog(appendLine(null, "info", "Reprovisioning workbench…"));
    setLog((l) => appendLine(l, "out", `Replacing container from ${STANDARD_IMAGE.ref}`));
    setLog((l) => appendLine(l, "out", "Preserving /ree workspace volume"));
    try {
      await reeApi.reprovisionWorkbench(reeId);
      setLog((l) => appendLine(l, "ok", "Workbench reprovisioned — lab back online"));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Reprovision failed";
      setLog((l) => appendLine(l, "err", msg));
    } finally {
      setReprovisioning(false);
    }
  }

  return (
    <div
      data-canvas-hud
      style={{
        position: "absolute",
        left: 16,
        bottom: 16,
        width: open ? 320 : 212,
        background: "rgba(255,255,255,0.92)",
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        boxShadow: open ? "0 18px 48px rgba(13,17,23,0.16)" : "0 4px 14px rgba(13,17,23,0.08)",
        backdropFilter: "blur(4px)",
        overflow: "hidden",
        transition: "width 0.26s cubic-bezier(0.4,0,0.2,1), box-shadow 0.26s",
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-label={open ? "Collapse workbench console" : "Expand workbench console"}
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          width: "100%",
          padding: "9px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span style={{ color: "#64748b", display: "flex" }}>{Ic.package(16)}</span>
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            lineHeight: 1.3,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 650, color: C.text }}>Workbench</span>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 9.5,
              color: C.textMuted,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {open ? `The lab hosting ${reeName || "this REE"}` : STANDARD_IMAGE.ref}
          </span>
        </div>
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            flexShrink: 0,
            background: provisioned ? DONE : C.borderMid,
            boxShadow: provisioned ? `0 0 7px ${DONE}88` : "none",
          }}
        />
        <span
          style={{
            display: "flex",
            color: C.textMuted,
            flexShrink: 0,
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform 0.26s",
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <title>toggle</title>
            <path
              d="M6 15l6-6 6 6"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>

      {/* body grows/shrinks the panel in place */}
      <div
        style={{
          maxHeight: open ? 420 : 0,
          opacity: open ? 1 : 0,
          overflow: "hidden",
          transition: "max-height 0.28s cubic-bezier(0.4,0,0.2,1), opacity 0.2s",
        }}
      >
        <div
          style={{
            padding: "2px 12px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 7,
            borderTop: `1px solid ${C.border}`,
          }}
        >
          <div style={{ height: 6 }} />
          <StatRow label="Image" value={STANDARD_IMAGE.ref} mono />
          <StatRow label="Location" value="Local" />
          <StatRow label="Isolation" value="Docker-in-docker sandbox" />

          <Terminal log={log} running={reprovisioning} />

          <button
            type="button"
            onClick={handleReprovision}
            disabled={reprovisioning}
            style={reprovisionBtn(reprovisioning)}
          >
            {reprovisioning ? Ic.loader(14) : Ic.refresh(14)}
            <span>{reprovisioning ? "Reprovisioning…" : "Reprovision workbench"}</span>
          </button>
          <span style={{ fontSize: 11, color: C.textMuted, textAlign: "center", lineHeight: 1.4 }}>
            Replaces the container, keeping the /ree volume.
          </span>
        </div>
      </div>
    </div>
  );
}

function StatRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "7px 10px",
        borderRadius: 8,
        background: C.surfaceAlt,
        border: `1px solid ${C.border}`,
      }}
    >
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: C.textMuted,
          fontFamily: F.mono,
          minWidth: 62,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 12,
          color: C.text,
          fontFamily: mono ? F.mono : F.sans,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </span>
    </div>
  );
}

function Terminal({ log, running }: { log: LogEntry | null; running: boolean }) {
  if (!log) return null;
  return (
    <div
      style={{
        background: "#0d1117",
        border: "1px solid #1f2733",
        borderRadius: 9,
        padding: "9px 11px",
        maxHeight: 150,
        overflow: "auto",
        fontFamily: F.mono,
        fontSize: 11,
        lineHeight: 1.6,
      }}
    >
      {log.lines.map((line, i) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: append-only log, never reordered
          key={i}
          style={{ color: LOG_COLOR[line.type], whiteSpace: "pre-wrap", wordBreak: "break-word" }}
        >
          <span style={{ color: "#475569" }}>{line.type === "err" ? "✗ " : "› "}</span>
          {line.msg}
        </div>
      ))}
      {running && <span style={{ color: "#6ee7b7" }}>▋</span>}
    </div>
  );
}

function reprovisionBtn(busy: boolean): React.CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    width: "100%",
    marginTop: 2,
    padding: "9px 14px",
    borderRadius: 9,
    border: `1px solid ${C.border}`,
    background: C.surfaceAlt,
    color: C.text,
    fontSize: 13,
    fontWeight: 600,
    fontFamily: F.sans,
    cursor: busy ? "default" : "pointer",
    opacity: busy ? 0.6 : 1,
  };
}
