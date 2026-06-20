import { appendLine } from "@core/ree/logEntry";
import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { STANDARD_IMAGE } from "../pages/workbench/WorkbenchPageSections";
import { APP_ROUTE } from "../state/pages";
import { HudConsole } from "./HudConsole";

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
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [reprovisioning, setReprovisioning] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const [log, setLog] = useState<LogEntry | null>(null);

  async function handleReleaseWorkbench() {
    setReleasing(true);
    await reeApi.deleteRee(reeId);
    navigate(APP_ROUTE.ROOT);
  }

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
    <HudConsole
      open={open}
      onToggle={() => setOpen((v) => !v)}
      widthOpen={320}
      widthCollapsed={212}
      outerStyle={{ left: 16, bottom: 16 }}
      icon={Ic.package(16)}
      iconColor="#64748b"
      title="Workbench"
      subtitle={open ? `The lab hosting ${reeName || "this REE"}` : STANDARD_IMAGE.ref}
      on={provisioned}
      expandLabel="Expand workbench console"
      collapseLabel="Collapse workbench console"
      bodyMaxHeight={420}
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
      <div style={{ height: 2, background: C.border, borderRadius: 99, margin: "4px 0" }} />
      <button
        type="button"
        onClick={handleReleaseWorkbench}
        disabled={releasing}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 7,
          width: "100%",
          padding: "9px 14px",
          borderRadius: 9,
          border: "1px solid rgba(202, 138, 4, 0.38)",
          background: "rgba(254, 249, 195, 0.72)",
          color: "#92400e",
          fontSize: 13,
          fontWeight: 600,
          fontFamily: F.sans,
          cursor: releasing ? "default" : "pointer",
          opacity: releasing ? 0.6 : 1,
        }}
      >
        {releasing ? Ic.loader(14) : Ic.x(14)}
        <span>{releasing ? "Releasing…" : "Release workbench"}</span>
      </button>
      <span style={{ fontSize: 11, color: C.textMuted, textAlign: "center", lineHeight: 1.4 }}>
        Ends the REE session and removes this workbench.
      </span>
    </HudConsole>
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
