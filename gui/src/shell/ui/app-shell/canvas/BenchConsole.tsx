import { APP_ROUTE } from "@core/app-shell/pages";
import { appendLine } from "@core/ree/logEntry";
import type { LogEntry } from "@core/ree/ReeTypes";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeRuntime } from "@shell/data/apiRuntime";
import { useReeClient } from "@shell/data/ree/client";
import { useWorkbenchImageRef } from "@shell/data/workbench/images";
import { useState } from "react";
import { useNavigate } from "react-router";
import { Ic } from "../../shared/components/Icon";
import styles from "./BenchConsole.module.css";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";

interface BenchConsoleProps {
  provisioned: boolean;
  reeName?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The persistent footer bar owns the closed-state trigger. */
  externallyTriggered?: boolean;
}

// The workbench is the lab this whole hub lives in, so it reads as an ambient
// console pinned to the bench corner rather than a node on the ring. The footer
// bar carries its resting state and opens it here — no separate panel — to
// surface live bench status and the one action that matters here: release,
// with a terminal-style readout.
export function BenchConsole({
  provisioned,
  reeName,
  open,
  onOpenChange,
  externallyTriggered = false,
}: BenchConsoleProps) {
  const { reeId } = useReeRuntime();
  const reeClient = useReeClient();
  const imageRef = useWorkbenchImageRef();
  const navigate = useNavigate();
  const [releasing, setReleasing] = useState(false);
  const [log, setLog] = useState<LogEntry | null>(null);

  async function handleReleaseWorkbench() {
    setReleasing(true);
    try {
      await reeClient.releaseRee(reeId);
    } catch (err) {
      // The workbench is still up, so stay on it with the reason in the console
      // rather than spinning on "Releasing…" forever.
      setLog(
        appendLine(
          null,
          "err",
          err instanceof Error ? err.message : "Release failed",
          appShellPorts.clock.nowIso(),
        ),
      );
      setReleasing(false);
      return;
    }
    navigate(APP_ROUTE.ROOT);
  }

  if (externallyTriggered && !open) return null;

  return (
    <HudConsole
      open={open}
      onToggle={() => onOpenChange(!open)}
      widthOpen={320}
      widthCollapsed={212}
      className={hud.benchPlacement}
      icon={Ic.package(16)}
      iconTint="var(--chrome-text-muted)"
      title="Workbench"
      subtitle={open ? `The lab hosting ${reeName || "this REE"}` : (imageRef ?? "Workbench")}
      on={provisioned}
      expandLabel="Expand workbench console"
      collapseLabel="Collapse workbench console"
      bodyMaxHeight={420}
    >
      <div className={styles.spacer} />
      <StatRow label="Image" value={imageRef ?? "—"} mono />
      <StatRow label="Location" value="Local" />
      <StatRow label="Isolation" value="Docker-in-docker sandbox" />

      <Terminal log={log} running={releasing} />

      <button
        type="button"
        onClick={handleReleaseWorkbench}
        disabled={releasing}
        className={styles.action}
        data-kind="release"
      >
        {releasing ? Ic.loader(14) : Ic.x(14)}
        <span>{releasing ? "Releasing…" : "Release workbench"}</span>
      </button>
      <span className={styles.actionNote}>Ends the REE session and removes this workbench.</span>
    </HudConsole>
  );
}

function StatRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue} data-flavor={mono ? "code" : undefined}>
        {value}
      </span>
    </div>
  );
}

function Terminal({ log, running }: { log: LogEntry | null; running: boolean }) {
  if (!log) return null;
  return (
    <div className={styles.terminal}>
      {log.lines.map((line, i) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: append-only log, never reordered
          key={i}
          className={styles.line}
          data-kind={line.type}
        >
          <span className={styles.gutter}>{line.type === "err" ? "✗ " : "› "}</span>
          {line.msg}
        </div>
      ))}
      {running && <span className={styles.cursor}>▋</span>}
    </div>
  );
}
