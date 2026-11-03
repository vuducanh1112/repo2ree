import { APP_ROUTE } from "@core/app-shell/pages";
import { appendLine } from "@core/ree/logEntry";
import type { LogEntry } from "@core/ree/ReeTypes";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeRuntime } from "@shell/data/apiRuntime";
import { useReeClient } from "@shell/data/ree/client";
import { useReeQuery } from "@shell/data/ree/queries";
import { placementReadout } from "@shell/ui/labs/labPresentation";
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
// surface where the REE is kept and the one action that matters here: deleting
// it from its lab's store, confirmed first, with a terminal-style readout.
export function BenchConsole({
  provisioned,
  reeName,
  open,
  onOpenChange,
  externallyTriggered = false,
}: BenchConsoleProps) {
  const { reeId } = useReeRuntime();
  const reeClient = useReeClient();
  const reeQuery = useReeQuery();
  const placement = placementReadout(reeQuery.data?.workbenchLocation);
  const [confirming, setConfirming] = useState(false);
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [log, setLog] = useState<LogEntry | null>(null);

  async function handleDelete() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setDeleting(true);
    try {
      await reeClient.deleteRee(reeId);
    } catch (err) {
      // The REE is still there, so stay on it with the reason in the console
      // rather than spinning on "Deleting…" forever.
      setLog(
        appendLine(
          null,
          "err",
          err instanceof Error ? err.message : "Delete failed",
          appShellPorts.clock.nowIso(),
        ),
      );
      setDeleting(false);
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
      subtitle={open ? `The lab hosting ${reeName || "this REE"}` : placement}
      on={provisioned}
      expandLabel="Expand workbench console"
      collapseLabel="Collapse workbench console"
      bodyMaxHeight={420}
    >
      <div className={styles.spacer} />
      <StatRow label="Placement" value={placement} mono />

      <Terminal log={log} running={deleting} />

      <button
        type="button"
        onClick={handleDelete}
        disabled={deleting}
        className={styles.action}
        data-kind="release"
      >
        {deleting ? Ic.loader(14) : Ic.x(14)}
        <span>{actionLabel(confirming, deleting)}</span>
      </button>
      <span className={styles.actionNote}>Deletes the REE and its files from the lab's store.</span>
    </HudConsole>
  );
}

function actionLabel(confirming: boolean, busy: boolean): string {
  if (busy) return "Deleting…";
  return confirming ? "Confirm: delete this REE" : "Delete REE";
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
