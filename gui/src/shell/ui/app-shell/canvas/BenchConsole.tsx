import { APP_ROUTE } from "@core/app-shell/pages";
import { appendLine } from "@core/ree/logEntry";
import type { LogEntry } from "@core/ree/ReeTypes";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeRuntime } from "@shell/data/apiRuntime";
import { useReeClient } from "@shell/data/ree/client";
import { useReeQuery } from "@shell/data/ree/queries";
import { defaultImageRef, useWorkbenchImageCatalog } from "@shell/data/workbench/images";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Ic } from "../../shared/components/Icon";
import styles from "./BenchConsole.module.css";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";

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
  const { reeId, reeApi } = useReeRuntime();
  const { data: reeProject } = useReeQuery();
  const reeClient = useReeClient();
  const { data: imageCatalog } = useWorkbenchImageCatalog();
  // The REE's actual provisioned image, falling back to the catalog default
  // until the REE detail has loaded.
  const imageRef = reeProject?.workbenchImage ?? defaultImageRef(imageCatalog);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [reprovisioning, setReprovisioning] = useState(false);
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

  async function handleReprovision() {
    setReprovisioning(true);
    setLog(appendLine(null, "info", "Reprovisioning workbench…", appShellPorts.clock.nowIso()));
    setLog((l) =>
      appendLine(
        l,
        "out",
        `Replacing container from ${imageRef ?? "the current image"}`,
        appShellPorts.clock.nowIso(),
      ),
    );
    setLog((l) =>
      appendLine(l, "out", "Preserving /ree workspace volume", appShellPorts.clock.nowIso()),
    );
    try {
      await reeApi.reprovisionWorkbench(reeId);
      setLog((l) =>
        appendLine(
          l,
          "ok",
          "Workbench reprovisioned — lab back online",
          appShellPorts.clock.nowIso(),
        ),
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Reprovision failed";
      setLog((l) => appendLine(l, "err", msg, appShellPorts.clock.nowIso()));
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

      <Terminal log={log} running={reprovisioning} />

      <button
        type="button"
        onClick={handleReprovision}
        disabled={reprovisioning}
        className={styles.action}
        data-kind="reprovision"
      >
        {reprovisioning ? Ic.loader(14) : Ic.refresh(14)}
        <span>{reprovisioning ? "Reprovisioning…" : "Reprovision workbench"}</span>
      </button>
      <span className={styles.actionNote}>Replaces the container, keeping the /ree volume.</span>
      <div className={styles.divider} />
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
