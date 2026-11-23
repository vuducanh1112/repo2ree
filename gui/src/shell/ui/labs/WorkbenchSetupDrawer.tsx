import { APP_ROUTE } from "@core/app-shell/pages";
import type { Lab } from "@core/lab/Lab";
import { appendLine } from "@core/ree/logEntry";
import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import { runFailurePresentation } from "@core/runs/runFailurePresentation";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeRunsClient } from "@shell/data/runs/client";
import { observeReeRun } from "@shell/data/runs/queries";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { CollapsibleLogCard } from "../app-shell/components/CollapsibleLogCard";
import { Button } from "../shared/components/Button";
import { Ic } from "../shared/components/Icon";
import { Notice } from "../shared/components/Notice";
import styles from "./WorkbenchSetupDrawer.module.css";

interface WorkbenchSetupDrawerProps {
  lab: Lab;
  loadRequested: boolean;
}

export function WorkbenchSetupDrawer({ lab, loadRequested }: WorkbenchSetupDrawerProps) {
  const navigate = useNavigate();
  const runsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry | null>(null);
  const [bundle, setBundle] = useState<File | null>(null);

  async function handleProvision() {
    setLoading(true);
    setError(null);
    const startedTs = appShellPorts.clock.nowIso();
    const preamble: LogLine[] = [
      { type: "info", msg: "Powering up the workbench…", ts: startedTs },
      { type: "out", msg: `Location: ${lab.label}`, ts: startedTs },
    ];
    setLog({ lines: preamble, ts: startedTs });
    try {
      const { reeId, run } = await runsClient.createWorkspace("REE", lab.id);
      const result = await observeReeRun(queryClient, runsClient, {
        reeId,
        runId: run.runId,
        onUpdate: ({ lines, ts }) => setLog({ lines: [...preamble, ...lines], ts }),
      });
      if (result.status !== "succeeded") {
        const reason = result.failure
          ? runFailurePresentation(result.failure).label
          : `Provisioning ${result.status}`;
        throw new Error(reason);
      }
      setLog((l) =>
        appendLine(l, "ok", "Lab online — seating the specimen", appShellPorts.clock.nowIso()),
      );
      if (bundle) await loadBundleOnto(reeId, bundle);
      navigate(`${APP_ROUTE.WORKSPACE}?reeId=${encodeURIComponent(reeId)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Provisioning failed";
      setError(msg);
      setLog((l) => appendLine(l, "err", msg, appShellPorts.clock.nowIso()));
    } finally {
      setLoading(false);
    }
  }

  async function loadBundleOnto(reeId: string, file: File) {
    setLog((l) =>
      appendLine(
        l,
        "info",
        `Loading ${file.name} onto the workbench…`,
        appShellPorts.clock.nowIso(),
      ),
    );
    const preamble = log?.lines ?? [];
    const run = await runsClient.loadReeBundle(reeId, file);
    const result = await observeReeRun(queryClient, runsClient, {
      reeId,
      runId: run.runId,
      onUpdate: ({ lines, ts }) => setLog({ lines: [...preamble, ...lines], ts }),
    });
    if (result.status !== "succeeded") {
      throw new Error(
        result.failure ? runFailurePresentation(result.failure).label : `Load ${result.status}`,
      );
    }
    setLog((l) => appendLine(l, "ok", "REE loaded — opening it", appShellPorts.clock.nowIso()));
  }

  return (
    <div className={styles.setup}>
      <p className={styles.lede}>
        The REE is kept at <b>{lab.label}</b> for its whole life.
      </p>

      <SectionLabel icon={Ic.package(14)}>Contents</SectionLabel>
      <BundleChoice
        bundle={bundle}
        disabled={loading}
        required={loadRequested}
        onChange={setBundle}
      />

      {error && (
        <Notice tone="danger" icon={Ic.x(14)}>
          {error}
        </Notice>
      )}

      {log && <CollapsibleLogCard log={log} running={loading} title="Provisioning log" />}

      <Button
        variant="primary"
        fullWidth
        busy={loading}
        icon={loading ? Ic.loader(15) : Ic.package(15)}
        onClick={handleProvision}
        disabled={loading || !lab.available || (loadRequested && !bundle)}
      >
        {loading ? "Powering up…" : bundle ? "Provision and load REE" : "Provision workbench"}
      </Button>
      <span className={styles.note}>
        Brings the lab online — this can take a moment on first run.
      </span>
    </div>
  );
}

function BundleChoice({
  bundle,
  disabled,
  required,
  onChange,
}: {
  bundle: File | null;
  disabled: boolean;
  required: boolean;
  onChange: (file: File | null) => void;
}) {
  return (
    <div className={styles.bundle} data-required={required && !bundle ? true : undefined}>
      <div className={styles.bundleCopy}>
        {bundle
          ? "This workbench will be loaded with the uploaded REE."
          : required
            ? "Choose the downloaded REE bundle (.zip) to load onto this workbench."
            : "Start blank, or load a downloaded REE bundle (.zip) onto this workbench."}
      </div>
      <div className={styles.bundleRow}>
        <label className={styles.chooser}>
          {Ic.upload(14)}
          <span>{bundle ? "Choose another" : "Choose REE bundle"}</span>
          <input
            type="file"
            accept=".zip,application/zip"
            disabled={disabled}
            aria-label="REE bundle"
            className={styles.hiddenFileInput}
            onChange={(event) => onChange(event.target.files?.[0] ?? null)}
          />
        </label>
        <div className={styles.bundleName} data-chosen={bundle ? true : undefined}>
          {bundle
            ? bundle.name
            : required
              ? "No bundle selected yet"
              : "No bundle selected — blank REE"}
        </div>
        {bundle && (
          <button
            type="button"
            onClick={() => onChange(null)}
            disabled={disabled}
            className={styles.clear}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className={styles.sectionLabel}>
      <span aria-hidden className={styles.sectionIcon}>
        {icon}
      </span>
      <span className={styles.sectionText}>{children}</span>
    </div>
  );
}
