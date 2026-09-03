import { APP_ROUTE } from "@core/app-shell/pages";
import {
  CUSTOM_IMAGE_ID,
  DEFAULT_IMAGE_SELECTION,
  resolveWorkbenchImage,
  type WorkbenchImageSelection,
} from "@core/lab/imageSelection";
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
import { WorkbenchImageSelector } from "./WorkbenchImageSelector";
import styles from "./WorkbenchSetupDrawer.module.css";

interface WorkbenchSetupDrawerProps {
  /** The lab the bench will be built on — already chosen in the grid. */
  lab: Lab;
  /** Arrived from "Load existing REE": a bundle is required before provisioning. */
  loadRequested: boolean;
}

/**
 * Everything between choosing a lab and having a workbench: the base image, what
 * the bench starts with, and the run that brings it online. It lives in the
 * canvas's drawer because that is what the drawer is for — the surface where
 * one chosen thing is configured and acted on.
 *
 * The image is shown, not hidden behind a label: it is the base of everything
 * this REE will later claim to reproduce, so the author should be able to read
 * the ref they are committing to — and, where the lab allows it, type their own.
 */
export function WorkbenchSetupDrawer({ lab, loadRequested }: WorkbenchSetupDrawerProps) {
  const navigate = useNavigate();
  const runsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry | null>(null);
  const [imageSelection, setImageSelection] =
    useState<WorkbenchImageSelection>(DEFAULT_IMAGE_SELECTION);
  // An externally managed lab was provisioned outside this control plane, so
  // there is no image left to choose.
  const choosesImage = lab.lifecycleMode === "provider_managed";
  const chosenRef = choosesImage ? resolveWorkbenchImage(imageSelection, lab.images) : "";
  // Custom picked but left blank would silently provision the lab default —
  // the one case where the button must wait for the author.
  const awaitingCustomRef = imageSelection.selectedId === CUSTOM_IMAGE_ID && !chosenRef;
  // An REE can start blank or be a downloaded bundle restored onto the bench.
  // The bundle is chosen here rather than on the landing screen because the
  // load runs on the workbench this step provisions.
  const [bundle, setBundle] = useState<File | null>(null);

  async function handleProvision() {
    setLoading(true);
    setError(null);
    const startedTs = appShellPorts.clock.nowIso();
    // Preamble lines we own locally; the run's streamed log lines are appended
    // after these on every poll update.
    const preamble: LogLine[] = [
      { type: "info", msg: "Powering up the workbench…", ts: startedTs },
      {
        type: "out",
        msg: choosesImage
          ? `Image: ${chosenRef || "lab default"}`
          : "Environment: operator managed",
        ts: startedTs,
      },
      { type: "out", msg: `Location: ${lab.label}`, ts: startedTs },
    ];
    setLog({ lines: preamble, ts: startedTs });
    try {
      // The REE's display name is owned by the Metadata page; provision with a
      // neutral default and let the user rename it there. Provisioning runs in
      // the background so the image pull streams live — observeReeRun tails the
      // run's log feed into this drawer until it finishes.
      const { reeId, run } = await runsClient.createWorkspace("REE", lab.id, chosenRef);
      const result = await observeReeRun(queryClient, runsClient, {
        reeId,
        runId: run.runId,
        onUpdate: ({ lines, ts }) => setLog({ lines: [...preamble, ...lines], ts }),
      });
      if (result.status !== "succeeded") {
        // Prefer the typed failure reason over a bare status, so the user sees
        // *why* provisioning failed (e.g. "Workbench unavailable").
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

  // Restore a downloaded REE onto the workbench just provisioned. Its log feed
  // is tailed into the same console, appended after the provisioning lines the
  // user has been watching.
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
        The bench is built at <b>{lab.label}</b> and stays there for this REE's whole life.
      </p>

      {choosesImage && (
        <>
          <SectionLabel icon={Ic.layers(14)}>Base image</SectionLabel>
          <WorkbenchImageSelector
            images={lab.images}
            acceptsCustomImage={lab.acceptsCustomImage}
            selection={imageSelection}
            onChange={setImageSelection}
            disabled={loading}
          />
        </>
      )}

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
        disabled={loading || awaitingCustomRef || !lab.available || (loadRequested && !bundle)}
      >
        {loading ? "Powering up…" : bundle ? "Provision and load REE" : "Provision workbench"}
      </Button>
      <span className={styles.note}>
        Brings the lab online — this can take a moment on first run.
      </span>
    </div>
  );
}

// Blank vs. loaded: the REE either starts empty or *is* a downloaded bundle
// (sealed or draft) restored onto this workbench — intent, source, and the
// author's receipts, the baseline a review reproduces against.
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
